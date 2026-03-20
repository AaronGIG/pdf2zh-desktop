import json
import logging
import re
from pathlib import Path

import tiktoken
from tqdm import tqdm

from babeldoc.document_il import Document
from babeldoc.document_il import Page
from babeldoc.document_il import PdfFont
from babeldoc.document_il import PdfFormula
from babeldoc.document_il import PdfParagraph
from babeldoc.document_il import PdfParagraphComposition
from babeldoc.document_il import PdfSameStyleCharacters
from babeldoc.document_il import PdfSameStyleUnicodeCharacters
from babeldoc.document_il import PdfStyle
from babeldoc.document_il.translator.translator import BaseTranslator
from babeldoc.document_il.utils.fontmap import FontMapper
from babeldoc.document_il.utils.layout_helper import get_char_unicode_string
from babeldoc.document_il.utils.layout_helper import is_same_style
from babeldoc.document_il.utils.layout_helper import is_same_style_except_font
from babeldoc.document_il.utils.layout_helper import is_same_style_except_size
from babeldoc.document_il.utils.priority_thread_pool_executor import (
    PriorityThreadPoolExecutor,
)
from babeldoc.translation_config import TranslationConfig

logger = logging.getLogger(__name__)


class RichTextPlaceholder:
    def __init__(
        self,
        placeholder_id: int,
        composition: PdfSameStyleCharacters,
        left_placeholder: str,
        right_placeholder: str,
    ):
        self.id = placeholder_id
        self.composition = composition
        self.left_placeholder = left_placeholder
        self.right_placeholder = right_placeholder


class FormulaPlaceholder:
    def __init__(self, placeholder_id: int, formula: PdfFormula, placeholder: str):
        self.id = placeholder_id
        self.formula = formula
        self.placeholder = placeholder


class PbarContext:
    def __init__(self, pbar):
        self.pbar = pbar

    def __enter__(self):
        return self.pbar

    def __exit__(self, exc_type, exc_value, traceback):
        self.pbar.advance()


class DocumentTranslateTracker:
    def __init__(self):
        self.page = []

    def new_page(self):
        page = PageTranslateTracker()
        self.page.append(page)
        return page

    def to_json(self):
        pages = []
        for page in self.page:
            paragraphs = []
            for para in page.paragraph:
                i_str = getattr(para, "input", None)
                o_str = getattr(para, "output", None)
                pdf_unicode = getattr(para, "pdf_unicode", None)
                if pdf_unicode is None or i_str is None:
                    continue
                paragraphs.append(
                    {
                        "input": i_str,
                        "output": o_str,
                        "pdf_unicode": pdf_unicode,
                    },
                )
            pages.append({"paragraph": paragraphs})
        return json.dumps({"page": pages}, ensure_ascii=False, indent=2)


class PageTranslateTracker:
    def __init__(self):
        self.paragraph = []

    def new_paragraph(self):
        paragraph = ParagraphTranslateTracker()
        self.paragraph.append(paragraph)
        return paragraph


class ParagraphTranslateTracker:
    def __init__(self):
        pass

    def set_pdf_unicode(self, unicode: str):
        self.pdf_unicode = unicode

    def set_input(self, input_text: str):
        self.input = input_text

    def set_output(self, output: str):
        self.output = output


class ILTranslator:
    stage_name = "Translate Paragraphs"

    def __init__(
        self,
        translate_engine: BaseTranslator,
        translation_config: TranslationConfig,
        tokenizer=None,
    ):
        self.translate_engine = translate_engine
        self.translation_config = translation_config
        self.font_mapper = FontMapper(translation_config)

        if tokenizer is None:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o")
        else:
            self.tokenizer = tokenizer

    def calc_token_count(self, text: str) -> int:
        try:
            return len(self.tokenizer.encode(text, disallowed_special=()))
        except Exception:
            return 0

    def translate(self, docs: Document):
        tracker = DocumentTranslateTracker()
        # count total paragraph
        total = sum(len(page.pdf_paragraph) for page in docs.page)
        with self.translation_config.progress_monitor.stage_start(
            self.stage_name,
            total,
        ) as pbar:
            with PriorityThreadPoolExecutor(
                max_workers=min(
                    self.translation_config.qps * 2,
                    self.translation_config.qps + 5,
                ),
            ) as executor:
                for page in docs.page:
                    self.process_page(page, executor, pbar, tracker.new_page())

        path = self.translation_config.get_working_file_path("translate_tracking.json")

        if self.translation_config.debug:
            logger.debug(f"save translate tracking to {path}")
            with Path(path).open("w", encoding="utf-8") as f:
                f.write(tracker.to_json())

    def process_page(
        self,
        page: Page,
        executor: PriorityThreadPoolExecutor,
        pbar: tqdm | None = None,
        tracker: PageTranslateTracker = None,
    ):
        self.translation_config.raise_if_cancelled()
        for paragraph in page.pdf_paragraph:
            page_font_map = {}
            for font in page.pdf_font:
                page_font_map[font.font_id] = font
            page_xobj_font_map = {}
            for xobj in page.pdf_xobject:
                page_xobj_font_map[xobj.xobj_id] = page_font_map.copy()
                for font in xobj.pdf_font:
                    page_xobj_font_map[xobj.xobj_id][font.font_id] = font
            # self.translate_paragraph(paragraph, pbar,tracker.new_paragraph(), page_font_map, page_xobj_font_map)
            executor.submit(
                self.translate_paragraph,
                paragraph,
                pbar,
                tracker.new_paragraph(),
                page_font_map,
                page_xobj_font_map,
                priority=1048576 - self.calc_token_count(paragraph.unicode),
            )

    class TranslateInput:
        def __init__(
            self,
            unicode: str,
            placeholders: list[RichTextPlaceholder | FormulaPlaceholder],
            base_style: PdfStyle = None,
        ):
            self.unicode = unicode
            self.placeholders = placeholders
            self.base_style = base_style

    def create_formula_placeholder(
        self,
        formula: PdfFormula,
        formula_id: int,
        paragraph: PdfParagraph,
    ):
        placeholder = self.translate_engine.get_formular_placeholder(formula_id)
        if placeholder in paragraph.unicode:
            return self.create_formula_placeholder(formula, formula_id + 1, paragraph)

        return FormulaPlaceholder(formula_id, formula, placeholder)

    def create_rich_text_placeholder(
        self,
        composition: PdfSameStyleCharacters,
        composition_id: int,
        paragraph: PdfParagraph,
    ):
        left_placeholder = self.translate_engine.get_rich_text_left_placeholder(
            composition_id,
        )
        right_placeholder = self.translate_engine.get_rich_text_right_placeholder(
            composition_id,
        )
        if (
            left_placeholder in paragraph.unicode
            or right_placeholder in paragraph.unicode
        ):
            return self.create_rich_text_placeholder(
                composition,
                composition_id + 1,
                paragraph,
            )

        return RichTextPlaceholder(
            composition_id,
            composition,
            left_placeholder,
            right_placeholder,
        )

    def get_translate_input(
        self,
        paragraph: PdfParagraph,
        page_font_map: dict[str, PdfFont] = None,
        disable_rich_text_translate: bool | None = None,
    ):
        if not paragraph.pdf_paragraph_composition:
            return
        if len(paragraph.pdf_paragraph_composition) == 1:
            # 如果整个段落只有一个组成部分，那么直接返回，不需要套占位符等
            composition = paragraph.pdf_paragraph_composition[0]
            if (
                composition.pdf_line
                or composition.pdf_same_style_characters
                or composition.pdf_character
            ):
                return self.TranslateInput(paragraph.unicode, [], paragraph.pdf_style)
            elif composition.pdf_formula:
                # 不需要翻译纯公式
                return None
            elif composition.pdf_same_style_unicode_characters:
                # DEBUG INSERT CHAR, NOT TRANSLATE
                return None
            else:
                logger.error(
                    f"Unknown composition type. "
                    f"Composition: {composition}. "
                    f"Paragraph: {paragraph}. ",
                )
                return None

        # 如果没有指定 disable_rich_text_translate，使用配置中的值
        if disable_rich_text_translate is None:
            disable_rich_text_translate = (
                self.translation_config.disable_rich_text_translate
            )

        placeholder_id = 1
        placeholders = []
        chars = []
        for composition in paragraph.pdf_paragraph_composition:
            if composition.pdf_line:
                chars.extend(composition.pdf_line.pdf_character)
            elif composition.pdf_formula:
                formula_placeholder = self.create_formula_placeholder(
                    composition.pdf_formula,
                    placeholder_id,
                    paragraph,
                )
                placeholders.append(formula_placeholder)
                # 公式只需要一个占位符，所以 id+1
                placeholder_id = formula_placeholder.id + 1
                chars.extend(formula_placeholder.placeholder)
            elif composition.pdf_character:
                chars.append(composition.pdf_character)
            elif composition.pdf_same_style_characters:
                if disable_rich_text_translate:
                    # 如果禁用富文本翻译，直接添加字符
                    chars.extend(composition.pdf_same_style_characters.pdf_character)
                    continue

                fonta = self.font_mapper.map(
                    page_font_map[
                        composition.pdf_same_style_characters.pdf_style.font_id
                    ],
                    "1",
                )
                fontb = self.font_mapper.map(
                    page_font_map[paragraph.pdf_style.font_id],
                    "1",
                )
                if (
                    # 样式和段落基准样式一致，无需占位符
                    is_same_style(
                        composition.pdf_same_style_characters.pdf_style,
                        paragraph.pdf_style,
                    )
                    # 字号差异在 0.7-1.3 之间，可能是首字母变大效果，无需占位符
                    or is_same_style_except_size(
                        composition.pdf_same_style_characters.pdf_style,
                        paragraph.pdf_style,
                    )
                    or (
                        # 除了字体以外样式都和基准一样，并且字体都映射到同一个字体。无需占位符
                        is_same_style_except_font(
                            composition.pdf_same_style_characters.pdf_style,
                            paragraph.pdf_style,
                        )
                        and fonta
                        and fontb
                        and fonta.font_id == fontb.font_id
                    )
                    # or len(composition.pdf_same_style_characters.pdf_character) == 1
                ):
                    chars.extend(composition.pdf_same_style_characters.pdf_character)
                    continue
                placeholder = self.create_rich_text_placeholder(
                    composition.pdf_same_style_characters,
                    placeholder_id,
                    paragraph,
                )
                placeholders.append(placeholder)
                # 样式需要一左一右两个占位符，所以 id+2
                placeholder_id = placeholder.id + 2
                chars.append(placeholder.left_placeholder)
                chars.extend(composition.pdf_same_style_characters.pdf_character)
                chars.append(placeholder.right_placeholder)
            else:
                logger.error(
                    "Unexpected PdfParagraphComposition type "
                    "in PdfParagraph during translation. "
                    f"Composition: {composition}. "
                    f"Paragraph: {paragraph}. ",
                )
                return None

            # 如果占位符数量超过阈值，且未禁用富文本翻译，则递归调用并禁用富文本翻译
            if len(placeholders) > 40 and not disable_rich_text_translate:
                logger.warning(
                    f"Too many placeholders ({len(placeholders)}) in paragraph[{paragraph.debug_id}], "
                    "disabling rich text translation for this paragraph",
                )
                return self.get_translate_input(paragraph, page_font_map, True)

        text = get_char_unicode_string(chars)
        return self.TranslateInput(text, placeholders, paragraph.pdf_style)

    def process_formula(
        self,
        formula: PdfFormula,
        formula_id: int,
        paragraph: PdfParagraph,
    ):
        placeholder = self.create_formula_placeholder(formula, formula_id, paragraph)
        if placeholder.placeholder in paragraph.unicode:
            return self.process_formula(formula, formula_id + 1, paragraph)

        return placeholder

    def process_composition(
        self,
        composition: PdfSameStyleCharacters,
        composition_id: int,
        paragraph: PdfParagraph,
    ):
        placeholder = self.create_rich_text_placeholder(
            composition,
            composition_id,
            paragraph,
        )
        if (
            placeholder.left_placeholder in paragraph.unicode
            or placeholder.right_placeholder in paragraph.unicode
        ):
            return self.process_composition(
                composition,
                composition_id + 1,
                paragraph,
            )

        return placeholder

    def parse_translate_output(
        self,
        input_text: TranslateInput,
        output: str,
    ) -> [PdfParagraphComposition]:
        import re

        result = []

        # 如果没有占位符，直接返回整个文本
        if not input_text.placeholders:
            comp = PdfParagraphComposition()
            comp.pdf_same_style_unicode_characters = PdfSameStyleUnicodeCharacters()
            comp.pdf_same_style_unicode_characters.unicode = output
            comp.pdf_same_style_unicode_characters.pdf_style = input_text.base_style
            return [comp]

        # 构建正则表达式模式
        patterns = []
        placeholder_patterns = []
        placeholder_map = {}

        for placeholder in input_text.placeholders:
            if isinstance(placeholder, FormulaPlaceholder):
                # 转义特殊字符
                pattern = re.escape(placeholder.placeholder)
                patterns.append(f"({pattern})")
                placeholder_patterns.append(f"({pattern})")
                placeholder_map[placeholder.placeholder] = placeholder
            else:
                left = re.escape(placeholder.left_placeholder)
                right = re.escape(placeholder.right_placeholder)
                patterns.append(f"({left}.*?{right})")
                placeholder_patterns.append(f"({left})")
                placeholder_patterns.append(f"({right})")
                placeholder_map[placeholder.left_placeholder] = placeholder

        # 合并所有模式
        combined_pattern = "|".join(patterns)
        combined_placeholder_pattern = "|".join(placeholder_patterns)

        def remove_placeholder(text: str):
            return re.sub(combined_placeholder_pattern, "", text)

        # 找到所有匹配
        last_end = 0
        for match in re.finditer(combined_pattern, output):
            # 处理匹配之前的普通文本
            if match.start() > last_end:
                text = output[last_end : match.start()]
                if text:
                    comp = PdfParagraphComposition()
                    comp.pdf_same_style_unicode_characters = (
                        PdfSameStyleUnicodeCharacters()
                    )
                    comp.pdf_same_style_unicode_characters.unicode = remove_placeholder(
                        text,
                    )
                    comp.pdf_same_style_unicode_characters.pdf_style = (
                        input_text.base_style
                    )
                    result.append(comp)

            matched_text = match.group(0)

            # 处理占位符
            if any(
                isinstance(p, FormulaPlaceholder) and matched_text == p.placeholder
                for p in input_text.placeholders
            ):
                # 处理公式占位符
                placeholder = next(
                    p
                    for p in input_text.placeholders
                    if isinstance(p, FormulaPlaceholder)
                    and matched_text == p.placeholder
                )
                comp = PdfParagraphComposition()
                comp.pdf_formula = placeholder.formula
                result.append(comp)
            else:
                # 处理富文本占位符
                placeholder = next(
                    p
                    for p in input_text.placeholders
                    if not isinstance(p, FormulaPlaceholder)
                    and matched_text.startswith(p.left_placeholder)
                )
                text = matched_text[
                    len(placeholder.left_placeholder) : -len(
                        placeholder.right_placeholder,
                    )
                ]

                if isinstance(
                    placeholder.composition,
                    PdfSameStyleCharacters,
                ) and text.replace(" ", "") == "".join(
                    x.char_unicode for x in placeholder.composition.pdf_character
                ).replace(
                    " ",
                    "",
                ):
                    comp = PdfParagraphComposition(
                        pdf_same_style_characters=placeholder.composition,
                    )
                else:
                    comp = PdfParagraphComposition()
                    comp.pdf_same_style_unicode_characters = (
                        PdfSameStyleUnicodeCharacters()
                    )
                    comp.pdf_same_style_unicode_characters.pdf_style = (
                        placeholder.composition.pdf_style
                    )
                    comp.pdf_same_style_unicode_characters.unicode = remove_placeholder(
                        text,
                    )
                result.append(comp)

            last_end = match.end()

        # 处理最后的普通文本
        if last_end < len(output):
            text = output[last_end:]
            if text:
                comp = PdfParagraphComposition()
                comp.pdf_same_style_unicode_characters = PdfSameStyleUnicodeCharacters()
                comp.pdf_same_style_unicode_characters.unicode = remove_placeholder(
                    text,
                )
                comp.pdf_same_style_unicode_characters.pdf_style = input_text.base_style
                result.append(comp)

        return result

    def pre_translate_paragraph(
        self,
        paragraph: PdfParagraph,
        tracker: ParagraphTranslateTracker,
        page_font_map: dict[str, PdfFont],
        xobj_font_map: dict[int, dict[str, PdfFont]],
    ):
        """Pre-translation processing: prepare text for translation."""
        if paragraph.vertical:
            return None, None
        tracker.set_pdf_unicode(paragraph.unicode)
        if paragraph.xobj_id in xobj_font_map:
            page_font_map = xobj_font_map[paragraph.xobj_id]
        translate_input = self.get_translate_input(paragraph, page_font_map)
        if not translate_input:
            return None, None
        tracker.set_input(translate_input.unicode)
        text = translate_input.unicode
        if len(text) < self.translation_config.min_text_length:
            logger.debug(
                f"Text too short to translate, skip. Text: {text}. Paragraph id: {paragraph.debug_id}."
            )
            return None, None
        return text, translate_input

    def post_translate_paragraph(
        self,
        paragraph: PdfParagraph,
        tracker: ParagraphTranslateTracker,
        translate_input,
        translated_text: str,
    ):
        """Post-translation processing: update paragraph with translated text."""
        tracker.set_output(translated_text)
        if translated_text == translate_input.unicode:
            return False
        paragraph.unicode = translated_text
        paragraph.pdf_paragraph_composition = self.parse_translate_output(
            translate_input, translated_text
        )
        for composition in paragraph.pdf_paragraph_composition:
            if (
                composition.pdf_same_style_unicode_characters
                and composition.pdf_same_style_unicode_characters.pdf_style is None
            ):
                composition.pdf_same_style_unicode_characters.pdf_style = (
                    paragraph.pdf_style
                )
        return True

    def translate_paragraph(
        self,
        paragraph: PdfParagraph,
        pbar: tqdm | None = None,
        tracker: ParagraphTranslateTracker = None,
        page_font_map: dict[str, PdfFont] = None,
        xobj_font_map: dict[int, dict[str, PdfFont]] = None,
    ):
        """Translate a paragraph using pre and post processing functions."""
        self.translation_config.raise_if_cancelled()
        with PbarContext(pbar):
            try:
                # Pre-translation processing
                text, translate_input = self.pre_translate_paragraph(
                    paragraph, tracker, page_font_map, xobj_font_map
                )
                if text is None:
                    return

                # Perform translation
                translated_text = self.translate_engine.translate(text)
                translated_text = re.sub(r"[. 。…，]{20,}", ".", translated_text)

                # Post-translation processing
                self.post_translate_paragraph(
                    paragraph, tracker, translate_input, translated_text
                )
            except Exception as e:
                logger.exception(
                    f"Error translating paragraph. Paragraph: {paragraph.debug_id} ({paragraph.unicode}). Error: {e}. ",
                )
                # ignore error and continue
                return
