import base64
import logging
import re
from functools import wraps
from io import BytesIO
from itertools import islice

import freetype
import pdfminer.pdfinterp
import pymupdf
from pdfminer.layout import LTChar
from pdfminer.layout import LTFigure
from pdfminer.pdffont import PDFCIDFont
from pdfminer.pdffont import PDFFont
from pdfminer.pdfpage import PDFPage as PDFMinerPDFPage
from pdfminer.pdftypes import PDFObjRef as PDFMinerPDFObjRef
from pdfminer.pdftypes import resolve1 as pdftypes_resolve1
from pdfminer.psparser import PSLiteral

from babeldoc.document_il import il_version_1
from babeldoc.document_il.utils.style_helper import YELLOW
from babeldoc.translation_config import TranslationConfig


def batched(iterable, n, *, strict=False):
    # batched('ABCDEFG', 3) → ABC DEF G
    if n < 1:
        raise ValueError("n must be at least one")
    iterator = iter(iterable)
    while batch := tuple(islice(iterator, n)):
        if strict and len(batch) != n:
            raise ValueError("batched(): incomplete batch")
        yield batch


logger = logging.getLogger(__name__)


def create_hook(func, hook):
    @wraps(func)
    def wrapper(*args, **kwargs):
        hook(*args, **kwargs)
        return func(*args, **kwargs)

    return wrapper


def hook_pdfminer_pdf_page_init(*args):
    attrs = args[3]
    while isinstance(attrs["MediaBox"], PDFMinerPDFObjRef):
        attrs["MediaBox"] = pdftypes_resolve1(attrs["MediaBox"])


PDFMinerPDFPage.__init__ = create_hook(
    PDFMinerPDFPage.__init__, hook_pdfminer_pdf_page_init
)


def indirect(obj):
    if isinstance(obj, tuple) and obj[0] == "xref":
        return int(obj[1].split(" ")[0])


def get_glyph_cbox(face, g):
    face.load_glyph(g, freetype.FT_LOAD_NO_SCALE)
    cbox = face.glyph.outline.get_bbox()
    return cbox.xMin, cbox.yMin, cbox.xMax, cbox.yMax


def get_char_cbox(face, idx):
    g = face.get_char_index(idx)
    return get_glyph_cbox(face, g)


def get_name_cbox(face, name):
    g = face.get_name_index(name)
    return get_glyph_cbox(face, g)


def parse_font_file(doc, idx, encoding):
    bbox_list = []
    data = doc.xref_stream(idx)
    face = freetype.Face(BytesIO(data))
    for charmap in face.charmaps:
        if charmap.encoding_name == "FT_ENCODING_ADOBE_CUSTOM":
            face.select_charmap(freetype.FT_ENCODING_ADOBE_CUSTOM)
            break
    bbox_list = [get_char_cbox(face, x) for x in range(0, 256)]
    if encoding:
        for code, name in encoding:
            bbox_list[code] = get_name_cbox(face, name.encode("U8"))
    return bbox_list


def parse_encoding(obj_str):
    delta = []
    current = 0
    for x in re.finditer(
        r"(?P<p>[\[\]])|(?P<c>\d+)|(?P<n>/[a-zA-Z0-9]+)|(?P<s>.)", obj_str
    ):
        key = x.lastgroup
        val = x.group()
        if key == "c":
            current = int(val)
        if key == "n":
            delta.append((current, val[1:]))
            current += 1
    return delta


def parse_mapping(text):
    mapping = []
    for x in re.finditer(r"<(?P<num>[a-fA-F0-9]+)>", text):
        mapping.append(int(x.group("num"), 16))
    return mapping


def update_cmap_pair(cmap, data):
    for start, stop, value in batched(data, 3):
        for code in range(start, stop + 1):
            cmap[code] = value


def update_cmap_code(cmap, data):
    for code, value in batched(data, 2):
        cmap[code] = value


def parse_cmap(cmap_str):
    cmap = {}
    for x in re.finditer(
        r"\s+beginbfrange\s*(?P<r>(<[0-9a-fA-F]+>\s*)+)endbfrange\s+", cmap_str
    ):
        update_cmap_pair(cmap, parse_mapping(x.group("r")))
    for x in re.finditer(
        r"\s+beginbfchar\s*(?P<c>(<[0-9a-fA-F]+>\s*)+)endbfchar", cmap_str
    ):
        update_cmap_code(cmap, parse_mapping(x.group("c")))
    return cmap


def get_code(cmap, c):
    for k, v in cmap.items():
        if v == c:
            return k
    return -1


def get_bbox(bbox, size, c, x, y):
    x_min, y_min, x_max, y_max = bbox[c]
    factor = 1 / 1000 * size
    x_min = x_min * factor
    y_min = -y_min * factor
    x_max = x_max * factor
    y_max = -y_max * factor
    ll = (x + x_min, y + y_min)
    lr = (x + x_max, y + y_min)
    ul = (x + x_min, y + y_max)
    ur = (x + x_max, y + y_max)
    return pymupdf.Quad(ll, lr, ul, ur)


class ILCreater:
    stage_name = "Parse PDF and Create Intermediate Representation"

    def __init__(self, translation_config: TranslationConfig):
        self.progress = None
        self.current_page: il_version_1.Page = None
        self.mupdf: pymupdf.Document = None
        self.model = translation_config.doc_layout_model
        self.docs = il_version_1.Document(page=[])
        self.stroking_color_space_name = None
        self.non_stroking_color_space_name = None
        self.passthrough_per_char_instruction: list[tuple[str, str]] = []
        self.translation_config = translation_config
        self.passthrough_per_char_instruction_stack: list[list[tuple[str, str]]] = []
        self.xobj_id = 0
        self.xobj_inc = 0
        self.xobj_map: dict[int, il_version_1.PdfXobject] = {}
        self.xobj_stack = []
        self.current_page_font_name_id_map = {}
        self.current_page_font_char_bounding_box_map = {}

    def on_finish(self):
        self.progress.__exit__(None, None, None)

    def is_passthrough_per_char_operation(self, operator: str):
        return re.match("^(sc|scn|g|rg|k|cs|gs|ri)$", operator, re.IGNORECASE)

    def on_passthrough_per_char(self, operator: str, args: list[str]):
        if not self.is_passthrough_per_char_operation(operator):
            logger.error("Unknown passthrough_per_char operation: %s", operator)
            return
        # logger.debug("xobj_id: %d, on_passthrough_per_char: %s ( %s )", self.xobj_id, operator, args)
        args = [self.parse_arg(arg) for arg in args]
        for _i, value in enumerate(self.passthrough_per_char_instruction.copy()):
            op, arg = value
            if op == operator:
                self.passthrough_per_char_instruction.remove(value)
                break
        self.passthrough_per_char_instruction.append((operator, " ".join(args)))
        pass

    def remove_latest_passthrough_per_char_instruction(self):
        if self.passthrough_per_char_instruction:
            self.passthrough_per_char_instruction.pop()

    def parse_arg(self, arg: str):
        if isinstance(arg, PSLiteral):
            return f"/{arg.name}"
        if not isinstance(arg, str):
            return str(arg)
        return arg

    def pop_passthrough_per_char_instruction(self):
        if self.passthrough_per_char_instruction_stack:
            self.passthrough_per_char_instruction = (
                self.passthrough_per_char_instruction_stack.pop()
            )
        else:
            self.passthrough_per_char_instruction = []
            logging.error(
                "pop_passthrough_per_char_instruction error on page: %s",
                self.current_page.page_number,
            )

    def push_passthrough_per_char_instruction(self):
        self.passthrough_per_char_instruction_stack.append(
            self.passthrough_per_char_instruction.copy(),
        )

    # pdf32000 page 171
    def on_stroking_color_space(self, color_space_name):
        self.stroking_color_space_name = color_space_name

    def on_non_stroking_color_space(self, color_space_name):
        self.non_stroking_color_space_name = color_space_name

    def on_new_stream(self):
        self.stroking_color_space_name = None
        self.non_stroking_color_space_name = None
        self.passthrough_per_char_instruction = []

    def push_xobj(self):
        self.xobj_stack.append(
            (
                self.current_page_font_name_id_map.copy(),
                self.current_page_font_char_bounding_box_map.copy(),
                self.xobj_id,
            ),
        )
        self.current_page_font_name_id_map = {}
        self.current_page_font_char_bounding_box_map = {}

    def pop_xobj(self):
        (
            self.current_page_font_name_id_map,
            self.current_page_font_char_bounding_box_map,
            self.xobj_id,
        ) = self.xobj_stack.pop()

    def on_xobj_begin(self, bbox, xref_id):
        self.push_passthrough_per_char_instruction()
        self.push_xobj()
        self.xobj_inc += 1
        self.xobj_id = self.xobj_inc
        xobject = il_version_1.PdfXobject(
            box=il_version_1.Box(
                x=float(bbox[0]),
                y=float(bbox[1]),
                x2=float(bbox[2]),
                y2=float(bbox[3]),
            ),
            xobj_id=self.xobj_id,
            xref_id=xref_id,
        )
        self.current_page.pdf_xobject.append(xobject)
        self.xobj_map[self.xobj_id] = xobject
        return self.xobj_id

    def on_xobj_end(self, xobj_id, base_op):
        self.pop_passthrough_per_char_instruction()
        self.pop_xobj()
        xobj = self.xobj_map[xobj_id]
        xobj.base_operations = il_version_1.BaseOperations(value=base_op)
        self.xobj_inc += 1

    def on_page_start(self):
        self.current_page = il_version_1.Page(
            pdf_font=[],
            pdf_character=[],
            page_layout=[],
            # currently don't support UserUnit page parameter
            # pdf32000 page 79
            unit="point",
        )
        self.current_page_font_name_id_map = {}
        self.current_page_font_char_bounding_box_map = {}
        self.passthrough_per_char_instruction_stack = []
        self.xobj_stack = []
        self.non_stroking_color_space_name = None
        self.stroking_color_space_name = None
        self.docs.page.append(self.current_page)

    def on_page_end(self):
        self.progress.advance(1)

    def on_page_crop_box(
        self,
        x0: float | int,
        y0: float | int,
        x1: float | int,
        y1: float | int,
    ):
        box = il_version_1.Box(x=float(x0), y=float(y0), x2=float(x1), y2=float(y1))
        self.current_page.cropbox = il_version_1.Cropbox(box=box)

    def on_page_media_box(
        self,
        x0: float | int,
        y0: float | int,
        x1: float | int,
        y1: float | int,
    ):
        box = il_version_1.Box(x=float(x0), y=float(y0), x2=float(x1), y2=float(y1))
        self.current_page.mediabox = il_version_1.Mediabox(box=box)

    def on_page_number(self, page_number: int):
        assert isinstance(page_number, int)
        assert page_number >= 0
        self.current_page.page_number = page_number

    def on_page_base_operation(self, operation: str):
        self.current_page.base_operations = il_version_1.BaseOperations(value=operation)

    def on_page_resource_font(self, font: PDFFont, xref_id: int, font_id: str):
        font_name = font.fontname
        if isinstance(font_name, bytes):
            try:
                font_name = font_name.decode("utf-8")
            except UnicodeDecodeError:
                font_name = "BASE64:" + base64.b64encode(font_name).decode("utf-8")
        encoding_length = 1
        if isinstance(font, PDFCIDFont):
            try:
                # pdf 32000:2008 page 273
                # Table 118 - Predefined CJK CMap names
                _, encoding = self.mupdf.xref_get_key(xref_id, "Encoding")
                if encoding == "/Identity-H" or encoding == "/Identity-V":
                    encoding_length = 2
                else:
                    _, to_unicode_id = self.mupdf.xref_get_key(xref_id, "ToUnicode")
                    to_unicode_bytes = self.mupdf.xref_stream(
                        int(to_unicode_id.split(" ")[0]),
                    )
                    code_range = re.search(
                        b"begincodespacerange\n?.*<(\\d+?)>.*",
                        to_unicode_bytes,
                    ).group(1)
                    encoding_length = len(code_range) // 2
            except Exception:
                if max(font.unicode_map.cid2unichr.keys()) > 255:
                    encoding_length = 2
                else:
                    encoding_length = 1
        try:
            mupdf_font = pymupdf.Font(fontbuffer=self.mupdf.extract_font(xref_id)[3])
            bold = mupdf_font.is_bold
            italic = mupdf_font.is_italic
            monospaced = mupdf_font.is_monospaced
            serif = mupdf_font.is_serif
        except Exception:
            bold = None
            italic = None
            monospaced = None
            serif = None
        il_font_metadata = il_version_1.PdfFont(
            name=font_name,
            xref_id=xref_id,
            font_id=font_id,
            encoding_length=encoding_length,
            bold=bold,
            italic=italic,
            monospace=monospaced,
            serif=serif,
            ascent=font.ascent,
            descent=font.descent,
            pdf_font_char_bounding_box=[],
        )
        try:
            bbox_list, cmap = self.parse_font_xobj_id(xref_id)
            font_char_bounding_box_map = {}
            if not cmap:
                cmap = {x: x for x in range(257)}
            for char_id in cmap:
                if char_id < 0 or char_id >= len(bbox_list):
                    continue
                bbox = bbox_list[char_id]
                x, y, x2, y2 = bbox
                if (
                    x == 0
                    and y == 0
                    and x2 == 500
                    and y2 == 698
                    or x == 0
                    and y == 0
                    and x2 == 0
                    and y2 == 0
                ):
                    # ignore default bounding box
                    continue
                il_font_metadata.pdf_font_char_bounding_box.append(
                    il_version_1.PdfFontCharBoundingBox(
                        x=x,
                        y=y,
                        x2=x2,
                        y2=y2,
                        char_id=char_id,
                    )
                )
                font_char_bounding_box_map[char_id] = bbox
            if self.xobj_id in self.xobj_map:
                if self.xobj_id not in self.current_page_font_char_bounding_box_map:
                    self.current_page_font_char_bounding_box_map[self.xobj_id] = {}
                self.current_page_font_char_bounding_box_map[self.xobj_id][font_id] = (
                    font_char_bounding_box_map
                )
            else:
                self.current_page_font_char_bounding_box_map[font_id] = (
                    font_char_bounding_box_map
                )
        except Exception:
            pass
        self.current_page_font_name_id_map[font_name] = font_id
        if self.xobj_id in self.xobj_map:
            self.xobj_map[self.xobj_id].pdf_font.append(il_font_metadata)
        else:
            self.current_page.pdf_font.append(il_font_metadata)

    def parse_font_xobj_id(self, xobj_id: int):
        encoding = []
        font_encoding = self.mupdf.xref_get_key(xobj_id, "Encoding/Differences")
        if font_encoding:
            encoding = parse_encoding(font_encoding[1])
        bbox_list = []
        font_file = self.mupdf.xref_get_key(xobj_id, "FontDescriptor/FontFile")
        if file_idx := indirect(font_file):
            bbox_list = parse_font_file(self.mupdf, file_idx, encoding)
        cmap = {}
        to_unicode = self.mupdf.xref_get_key(xobj_id, "ToUnicode")
        if to_unicode_idx := indirect(to_unicode):
            cmap = parse_cmap(self.mupdf.xref_stream(to_unicode_idx).decode("U8"))
        return bbox_list, cmap

    def create_graphic_state(self, gs: pdfminer.pdfinterp.PDFGraphicState):
        graphic_state = il_version_1.GraphicState()
        for k, v in gs.__dict__.items():
            if v is None:
                continue
            if k in ["scolor", "ncolor"]:
                if isinstance(v, tuple):
                    v = list(v)
                else:
                    v = [v]
                setattr(graphic_state, k, v)
                continue
            if k == "linewidth":
                graphic_state.linewidth = float(v)
                continue
            continue
            raise NotImplementedError

        graphic_state.stroking_color_space_name = self.stroking_color_space_name
        graphic_state.non_stroking_color_space_name = self.non_stroking_color_space_name

        graphic_state.passthrough_per_char_instruction = " ".join(
            f"{arg} {op}" for op, arg in gs.passthrough_instruction
        )

        return graphic_state

    def on_lt_char(self, char: LTChar):
        if char.aw_font_id is None:
            return
        gs = self.create_graphic_state(char.graphicstate)
        # Get font from current page or xobject
        font = None
        for pdf_font in self.xobj_map.get(self.xobj_id, self.current_page).pdf_font:
            if pdf_font.font_id == char.aw_font_id:
                font = pdf_font
                break

        # Get descent from font
        descent = 0
        if font and hasattr(font, "descent"):
            descent = font.descent * char.size / 1000

        char_id = char.cid

        try:
            if (
                font_bounding_box_map
                := self.current_page_font_char_bounding_box_map.get(
                    self.xobj_id, self.current_page_font_char_bounding_box_map
                ).get(font.font_id)
            ):
                char_bounding_box = font_bounding_box_map.get(char_id, None)
            else:
                char_bounding_box = None
        except Exception:
            logger.debug(
                "Failed to get font bounding box for char %s",
                char.get_text(),
            )
            char_bounding_box = None

        char_unicode = char.get_text()
        if "(cid:" not in char_unicode and len(char_unicode) > 1:
            return
        advance = char.adv
        bbox = il_version_1.Box(
            x=char.bbox[0],
            y=char.bbox[1],
            x2=char.bbox[2],
            y2=char.bbox[3],
        )
        if char.matrix[0] == 0 and char.matrix[3] == 0:
            vertical = True
            visual_bbox = il_version_1.Box(
                x=char.bbox[0] - descent,
                y=char.bbox[1],
                x2=char.bbox[2] - descent,
                y2=char.bbox[3],
            )
        else:
            vertical = False
            # Add descent to y coordinates
            visual_bbox = il_version_1.Box(
                x=char.bbox[0],
                y=char.bbox[1] + descent,
                x2=char.bbox[2],
                y2=char.bbox[3] + descent,
            )
        visual_bbox = il_version_1.VisualBbox(box=visual_bbox)
        pdf_style = il_version_1.PdfStyle(
            font_id=char.aw_font_id,
            font_size=char.size,
            graphic_state=gs,
        )
        pdf_char = il_version_1.PdfCharacter(
            box=bbox,
            pdf_character_id=char_id,
            advance=advance,
            char_unicode=char_unicode,
            vertical=vertical,
            pdf_style=pdf_style,
            xobj_id=char.xobj_id,
            visual_bbox=visual_bbox,
        )
        if pdf_style.font_size == 0.0:
            logger.warning(
                "Font size is 0.0 for character %s. Skip it.",
                char_unicode,
            )
            return

        if char_bounding_box:
            x_min, y_min, x_max, y_max = char_bounding_box
            factor = 1 / 1000 * pdf_style.font_size
            x_min = x_min * factor
            y_min = y_min * factor
            x_max = x_max * factor
            y_max = y_max * factor
            ll = (char.bbox[0] + x_min, char.bbox[1] + y_min)
            ur = (char.bbox[0] + x_max, char.bbox[1] + y_max)
            pdf_char.visual_bbox = il_version_1.VisualBbox(
                il_version_1.Box(ll[0], ll[1], ur[0], ur[1])
            )

        self.current_page.pdf_character.append(pdf_char)

        if self.translation_config.show_char_box:
            self.current_page.pdf_rectangle.append(
                il_version_1.PdfRectangle(
                    box=pdf_char.visual_bbox.box,
                    graphic_state=YELLOW,
                    debug_info=True,
                )
            )

    def create_il(self):
        pages = [
            page
            for page in self.docs.page
            if self.translation_config.should_translate_page(page.page_number + 1)
        ]
        self.docs.page = pages
        return self.docs

    def on_total_pages(self, total_pages: int):
        assert isinstance(total_pages, int)
        assert total_pages > 0
        self.docs.total_pages = total_pages
        total = 0
        for page in range(total_pages):
            if self.translation_config.should_translate_page(page + 1) is False:
                continue
            total += 1
        self.progress = self.translation_config.progress_monitor.stage_start(
            self.stage_name,
            total,
        )

    def on_pdf_figure(self, figure: LTFigure):
        box = il_version_1.Box(
            figure.bbox[0],
            figure.bbox[1],
            figure.bbox[2],
            figure.bbox[3],
        )
        self.current_page.pdf_figure.append(il_version_1.PdfFigure(box=box))
