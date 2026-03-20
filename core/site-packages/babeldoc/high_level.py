import asyncio
import copy
import hashlib
import io
import logging
import pathlib
import threading
import time
from asyncio import CancelledError
from pathlib import Path
from typing import Any
from typing import BinaryIO

from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfparser import PDFParser
from pymupdf import Document
from pymupdf import Font

from babeldoc import asynchronize
from babeldoc.assets.assets import warmup
from babeldoc.const import CACHE_FOLDER
from babeldoc.converter import TranslateConverter
from babeldoc.document_il import il_version_1
from babeldoc.document_il.backend.pdf_creater import SAVE_PDF_STAGE_NAME
from babeldoc.document_il.backend.pdf_creater import SUBSET_FONT_STAGE_NAME
from babeldoc.document_il.backend.pdf_creater import PDFCreater
from babeldoc.document_il.frontend.il_creater import ILCreater
from babeldoc.document_il.midend.add_debug_information import AddDebugInformation
from babeldoc.document_il.midend.detect_scanned_file import DetectScannedFile
from babeldoc.document_il.midend.il_translator import ILTranslator
from babeldoc.document_il.midend.il_translator_llm_only import ILTranslatorLLMOnly
from babeldoc.document_il.midend.layout_parser import LayoutParser
from babeldoc.document_il.midend.paragraph_finder import ParagraphFinder
from babeldoc.document_il.midend.styles_and_formulas import StylesAndFormulas
from babeldoc.document_il.midend.table_parser import TableParser
from babeldoc.document_il.midend.typesetting import Typesetting
from babeldoc.document_il.utils.fontmap import FontMapper
from babeldoc.document_il.xml_converter import XMLConverter
from babeldoc.pdfinterp import PDFPageInterpreterEx
from babeldoc.progress_monitor import ProgressMonitor
from babeldoc.result_merger import ResultMerger
from babeldoc.split_manager import SplitManager
from babeldoc.translation_config import TranslateResult
from babeldoc.translation_config import TranslationConfig
from babeldoc.translation_config import WatermarkOutputMode

logger = logging.getLogger(__name__)

TRANSLATE_STAGES = [
    (ILCreater.stage_name, 14.12),  # Parse PDF and Create IR
    (DetectScannedFile.stage_name, 2.45),  # DetectScannedFile
    (LayoutParser.stage_name, 14.03),  # Parse Page Layout
    (TableParser.stage_name, 1.0),  # Parse Table
    (ParagraphFinder.stage_name, 6.26),  # Parse Paragraphs
    (StylesAndFormulas.stage_name, 1.66),  # Parse Formulas and Styles
    # (RemoveDescent.stage_name, 0.15),  # Remove Char Descent
    (ILTranslator.stage_name, 46.96),  # Translate Paragraphs
    (Typesetting.stage_name, 4.71),  # Typesetting
    (FontMapper.stage_name, 0.61),  # Add Fonts
    (PDFCreater.stage_name, 1.96),  # Generate drawing instructions
    (SUBSET_FONT_STAGE_NAME, 0.92),  # Subset font
    (SAVE_PDF_STAGE_NAME, 6.34),  # Save PDF
]

resfont_map = {
    "zh-cn": "china-ss",
    "zh-tw": "china-ts",
    "zh-hans": "china-ss",
    "zh-hant": "china-ts",
    "zh": "china-ss",
    "ja": "japan-s",
    "ko": "korea-s",
}


def verify_file_hash(file_path: str, expected_hash: str) -> bool:
    """Verify the SHA256 hash of a file."""
    sha256_hash = hashlib.sha256()
    with Path(file_path).open("rb") as f:
        # Read the file in chunks to handle large files efficiently
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest() == expected_hash


def start_parse_il(
    inf: BinaryIO,
    pages: list[int] | None = None,
    vfont: str = "",
    vchar: str = "",
    thread: int = 0,
    doc_zh: Document = None,
    lang_in: str = "",
    lang_out: str = "",
    service: str = "",
    resfont: str = "",
    noto: Font = None,
    cancellation_event: asyncio.Event = None,
    il_creater: ILCreater = None,
    translation_config: TranslationConfig = None,
    **kwarg: Any,
) -> None:
    rsrcmgr = PDFResourceManager()
    layout = {}
    device = TranslateConverter(
        rsrcmgr,
        vfont,
        vchar,
        thread,
        layout,
        lang_in,
        lang_out,
        service,
        resfont,
        noto,
        kwarg.get("envs", {}),
        kwarg.get("prompt", []),
        il_creater=il_creater,
    )
    # model = DocLayoutModel.load_available()

    assert device is not None
    assert il_creater is not None
    assert translation_config is not None
    obj_patch = {}
    interpreter = PDFPageInterpreterEx(rsrcmgr, device, obj_patch, il_creater)
    if pages:
        total_pages = len(pages)
    else:
        total_pages = doc_zh.page_count

    il_creater.on_total_pages(total_pages)

    parser = PDFParser(inf)
    doc = PDFDocument(parser)

    for pageno, page in enumerate(PDFPage.create_pages(doc)):
        if cancellation_event and cancellation_event.is_set():
            raise CancelledError("task cancelled")
        if pages and (pageno not in pages):
            continue
        page.pageno = pageno

        if not translation_config.should_translate_page(pageno + 1):
            continue

        height, width = (
            page.cropbox[3] - page.cropbox[1],
            page.cropbox[2] - page.cropbox[0],
        )
        if height > 1200 or width > 2000:
            logger.warning(f"page {pageno + 1} is too large, maybe unable to translate")
            # continue

        translation_config.raise_if_cancelled()
        # The current program no longer relies on
        # the following layout recognition results,
        # but in order to facilitate the migration of pdf2zh,
        # the relevant code is temporarily retained.
        # pix = doc_zh[page.pageno].get_pixmap()
        # image = np.fromstring(pix.samples, np.uint8).reshape(
        #     pix.height, pix.width, 3
        # )[:, :, ::-1]
        # page_layout = model.predict(
        #     image, imgsz=int(pix.height / 32) * 32)[0]
        # # kdtree 是不可能 kdtree 的，不如直接渲染成图片，用空间换时间
        # box = np.ones((pix.height, pix.width))
        # h, w = box.shape
        # vcls = ["abandon", "figure", "table",
        #         "isolate_formula", "formula_caption"]
        # for i, d in enumerate(page_layout.boxes):
        #     if page_layout.names[int(d.cls)] not in vcls:
        #         x0, y0, x1, y1 = d.xyxy.squeeze()
        #         x0, y0, x1, y1 = (
        #             np.clip(int(x0 - 1), 0, w - 1),
        #             np.clip(int(h - y1 - 1), 0, h - 1),
        #             np.clip(int(x1 + 1), 0, w - 1),
        #             np.clip(int(h - y0 + 1), 0, h - 1),
        #         )
        #         box[y0:y1, x0:x1] = i + 2
        # for i, d in enumerate(page_layout.boxes):
        #     if page_layout.names[int(d.cls)] in vcls:
        #         x0, y0, x1, y1 = d.xyxy.squeeze()
        #         x0, y0, x1, y1 = (
        #             np.clip(int(x0 - 1), 0, w - 1),
        #             np.clip(int(h - y1 - 1), 0, h - 1),
        #             np.clip(int(x1 + 1), 0, w - 1),
        #             np.clip(int(h - y0 + 1), 0, h - 1),
        #         )
        #         box[y0:y1, x0:x1] = 0
        # layout[page.pageno] = box
        # 新建一个 xref 存放新指令流
        # page.page_xref = doc_zh.get_new_xref()  # hack 插入页面的新 xref
        # doc_zh.update_object(page.page_xref, "<<>>")
        # doc_zh.update_stream(page.page_xref, b"")
        # doc_zh[page.pageno].set_contents(page.page_xref)
        ops_base = interpreter.process_page(page)
        il_creater.on_page_base_operation(ops_base)
        il_creater.on_page_end()
    il_creater.on_finish()
    device.close()


def translate(translation_config: TranslationConfig) -> TranslateResult:
    with ProgressMonitor(TRANSLATE_STAGES) as pm:
        return do_translate(pm, translation_config)


async def async_translate(translation_config: TranslationConfig):
    """Asynchronously translate a PDF file with real-time progress reporting.

    This function yields progress events that can be used to update progress bars
    or other UI elements. The events are dictionaries with the following structure:

    - progress_start: {
        "type": "progress_start",
        "stage": str,              # Stage name
        "stage_progress": float,   # Always 0.0
        "stage_current": int,      # Current count (0)
        "stage_total": int         # Total items in stage
    }
    - progress_update: {
        "type": "progress_update",
        "stage": str,              # Stage name
        "stage_progress": float,   # Stage progress (0-100)
        "stage_current": int,      # Current items processed
        "stage_total": int,        # Total items in stage
        "overall_progress": float  # Overall progress (0-100)
    }
    - progress_end: {
        "type": "progress_end",
        "stage": str,              # Stage name
        "stage_progress": float,   # Always 100.0
        "stage_current": int,      # Equal to stage_total
        "stage_total": int,        # Total items processed
        "overall_progress": float  # Overall progress (0-100)
    }
    - finish: {
        "type": "finish",
        "translate_result": TranslateResult
    }
    - error: {
        "type": "error",
        "error": str
    }

    Args:
        translation_config: Configuration for the translation process

    Yields:
        dict: Progress events during translation

    Raises:
        CancelledError: If the translation is cancelled
        Exception: Any other errors during translation
    """
    loop = asyncio.get_running_loop()
    callback = asynchronize.AsyncCallback()

    finish_event = asyncio.Event()
    cancel_event = threading.Event()
    with ProgressMonitor(
        TRANSLATE_STAGES,
        progress_change_callback=callback.step_callback,
        finish_callback=callback.finished_callback,
        finish_event=finish_event,
        cancel_event=cancel_event,
        loop=loop,
        report_interval=translation_config.report_interval,
    ) as pm:
        future = loop.run_in_executor(None, do_translate, pm, translation_config)
        try:
            async for event in callback:
                event = event.kwargs
                yield event
                if event["type"] == "error":
                    break
        except CancelledError:
            cancel_event.set()
        except KeyboardInterrupt:
            logger.info("Translation cancelled by user through keyboard interrupt")
            cancel_event.set()
    if cancel_event.is_set():
        future.cancel()
    logger.info("Waiting for translation to finish...")
    await finish_event.wait()


class MemoryMonitor:
    """Monitor memory usage of current process and all child processes."""

    def __init__(self, interval=0.1):
        """Initialize memory monitor.

        Args:
            interval: Monitoring interval in seconds, defaults to 0.1s (100ms)
        """
        self.interval = interval
        self.peak_memory_usage = 0
        self.monitor_thread = None
        self.stop_event = None

        try:
            import psutil

            self.psutil = psutil
        except ImportError:
            logger.warning("psutil not installed, memory monitoring disabled")
            self.psutil = None

    def __enter__(self):
        """Start memory monitoring."""
        if not self.psutil:
            return self

        self.stop_event = threading.Event()
        self.monitor_thread = threading.Thread(
            target=self._monitor_memory_usage, daemon=True
        )
        self.monitor_thread.start()
        logger.debug("Memory monitoring started")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Stop monitoring and log peak memory usage."""
        if not self.psutil or not self.monitor_thread:
            return

        self.stop_event.set()
        self.monitor_thread.join(timeout=2.0)
        logger.info(f"Peak memory usage: {self.peak_memory_usage:.2f} MB")

    def _monitor_memory_usage(self):
        """Background thread that periodically checks memory usage."""
        while not self.stop_event.is_set():
            try:
                current_process = self.psutil.Process()
                # Get memory usage of current process and all children
                total_memory = current_process.memory_info().rss
                for child in current_process.children(recursive=True):
                    try:
                        total_memory += child.memory_info().rss
                    except (self.psutil.NoSuchProcess, self.psutil.AccessDenied):
                        pass

                # Convert to MB for better readability
                total_memory_mb = total_memory / (1024 * 1024)
                if total_memory_mb > self.peak_memory_usage:
                    self.peak_memory_usage = total_memory_mb
            except Exception as e:
                logger.warning(f"Error monitoring memory: {e}")

            time.sleep(self.interval)


def fix_null_xref(doc: Document) -> None:
    """Fix null xref in PDF file by replacing them with empty arrays.

    Args:
        doc: PyMuPDF Document object to fix
    """
    for i in range(1, doc.xref_length()):
        try:
            obj = doc.xref_object(i)
            if obj == "null":
                doc.update_object(i, "[]")
            elif obj and "/ASCII85Decode" in obj:  # make pdfminer happy
                data = doc.xref_stream(i)
                doc.update_stream(i, data)
        except Exception:
            doc.update_object(i, "[]")


def do_translate(
    pm: ProgressMonitor, translation_config: TranslationConfig
) -> TranslateResult:
    try:
        translation_config.progress_monitor = pm
        original_pdf_path = translation_config.input_file
        logger.info(f"start to translate: {original_pdf_path}")
        start_time = time.time()

        with MemoryMonitor() as memory_monitor:
            # Check if split translation is enabled
            if not translation_config.split_strategy:
                result = _do_translate_single(pm, translation_config)
            else:
                # Initialize split manager and determine split points
                split_manager = SplitManager(translation_config)
                split_points = split_manager.determine_split_points(translation_config)

                if not split_points:
                    logger.warning(
                        "No split points determined, falling back to single translation"
                    )
                    result = _do_translate_single(pm, translation_config)
                else:
                    logger.info(f"Split points determined: {len(split_points)} parts")

                    if len(split_points) == 1:
                        logger.info("Only one part, use single translation")
                        result = _do_translate_single(pm, translation_config)
                    else:
                        pm.total_parts = len(split_points)

                        # Process parts serially
                        results: dict[int, TranslateResult] = {}
                        original_watermark_mode = (
                            translation_config.watermark_output_mode
                        )
                        original_doc = Document(original_pdf_path)
                        for i, split_point in enumerate(split_points):
                            try:
                                # Create a copy of config for this part
                                part_config = copy.copy(translation_config)
                                part_config.skip_clean = True
                                should_translate_pages = []
                                for page in range(
                                    split_point.start_page, split_point.end_page + 1
                                ):
                                    if translation_config.should_translate_page(
                                        page + 1
                                    ):
                                        should_translate_pages.append(
                                            page - split_point.start_page + 1
                                        )
                                part_config.pages = None
                                part_config.page_ranges = [
                                    (x, x) for x in should_translate_pages
                                ]

                                # Only first part should do scanned detection if enabled
                                if i > 0:
                                    part_config.skip_scanned_detection = True

                                part_config.working_dir = (
                                    translation_config.get_part_working_dir(i)
                                )
                                part_config.output_dir = (
                                    translation_config.get_part_output_dir(i)
                                )

                                assert id(
                                    part_config.shared_context_cross_split_part
                                ) == id(
                                    translation_config.shared_context_cross_split_part
                                ), "shared_context_cross_split_part must be the same"

                                part_temp_input_path = (
                                    part_config.get_working_file_path(
                                        f"input.part{i}.pdf"
                                    )
                                )
                                part_config.input_file = part_temp_input_path

                                temp_doc = Document()
                                temp_doc.insert_pdf(
                                    original_doc,
                                    from_page=split_point.start_page,
                                    to_page=split_point.end_page,
                                )
                                temp_doc.save(part_temp_input_path)

                                assert (
                                    temp_doc.page_count
                                    == split_point.end_page - split_point.start_page + 1
                                )

                                # Only first part should have watermark
                                if i > 0:
                                    part_config.watermark_output_mode = (
                                        WatermarkOutputMode.NoWatermark
                                    )

                                # Create progress monitor for this part
                                part_monitor = pm.create_part_monitor(
                                    i, len(split_points)
                                )

                                # Process this part
                                result = _do_translate_single(
                                    part_monitor,
                                    part_config,
                                )
                                results[i] = result

                            except Exception as e:
                                logger.error(f"Error in part {i}: {e}")
                                pm.translate_error(e)
                                raise
                            finally:
                                # Clean up part working directory
                                translation_config.cleanup_part_working_dir(i)

                        # Restore original watermark mode
                        translation_config.watermark_output_mode = (
                            original_watermark_mode
                        )

                        # Merge results
                        merger = ResultMerger(translation_config)
                        logger.info("start merge results")
                        result = merger.merge_results(results)
                        logger.info("finish merge results")

        finish_time = time.time()
        result.total_seconds = finish_time - start_time

        logger.info(
            f"finish translate: {original_pdf_path}, cost: {finish_time - start_time} s",
        )
        result.original_pdf_path = translation_config.input_file
        pm.translate_done(result)
        return result

    except Exception as e:
        logger.exception(f"translate error: {e}")
        pm.translate_error(e)
        raise
    finally:
        logger.debug("do_translate finally")
        pm.on_finish()
        translation_config.cleanup_temp_files()


def _do_translate_single(
    pm: ProgressMonitor,
    translation_config: TranslationConfig,
) -> TranslateResult:
    """Original translation logic for a single document or part"""
    translation_config.progress_monitor = pm
    original_pdf_path = translation_config.input_file
    if translation_config.debug:
        doc_input = Document(original_pdf_path)
        logger.debug("debug mode, save decompressed input pdf")
        output_path = translation_config.get_working_file_path(
            "input.decompressed.pdf",
        )
        # Fix null xref in PDF file
        fix_null_xref(doc_input)
        doc_input.save(output_path, expand=True, pretty=True)

    # Continue with original processing
    temp_pdf_path = translation_config.get_working_file_path("input.pdf")
    doc_pdf2zh = Document(original_pdf_path)
    resfont = "china-ss"

    # Fix null xref in PDF file
    fix_null_xref(doc_pdf2zh)

    for page in doc_pdf2zh:
        page.insert_font(resfont, None)

    resfont = None
    doc_pdf2zh.save(temp_pdf_path)
    il_creater = ILCreater(translation_config)
    il_creater.mupdf = doc_pdf2zh
    xml_converter = XMLConverter()
    logger.debug(f"start parse il from {temp_pdf_path}")
    with Path(temp_pdf_path).open("rb") as f:
        start_parse_il(
            f,
            doc_zh=doc_pdf2zh,
            resfont=resfont,
            il_creater=il_creater,
            translation_config=translation_config,
        )
    logger.debug(f"finish parse il from {temp_pdf_path}")
    docs = il_creater.create_il()
    logger.debug(f"finish create il from {temp_pdf_path}")
    if translation_config.debug:
        xml_converter.write_json(
            docs,
            translation_config.get_working_file_path("create_il.debug.json"),
        )

    # Rest of the original translation logic...
    # [Previous implementation of do_translate continues here]

    # 检测是否为扫描文件
    if translation_config.skip_scanned_detection:
        logger.debug("skipping scanned file detection")
    else:
        logger.debug("start detect scanned file")
        DetectScannedFile(translation_config).process(docs)
        logger.debug("finish detect scanned file")
        if translation_config.debug:
            xml_converter.write_json(
                docs,
                translation_config.get_working_file_path("detect_scanned_file.json"),
            )

    # Generate layouts for all pages
    logger.debug("start generating layouts")
    docs = LayoutParser(translation_config).process(docs, doc_pdf2zh)
    logger.debug("finish generating layouts")
    if translation_config.debug:
        xml_converter.write_json(
            docs,
            translation_config.get_working_file_path("layout_generator.json"),
        )

    if translation_config.table_model:
        docs = TableParser(translation_config).process(docs, doc_pdf2zh)
        logger.debug("finish table parser")
        if translation_config.debug:
            xml_converter.write_json(
                docs,
                translation_config.get_working_file_path("table_parser.json"),
            )
    ParagraphFinder(translation_config).process(docs)
    logger.debug(f"finish paragraph finder from {temp_pdf_path}")
    if translation_config.debug:
        xml_converter.write_json(
            docs,
            translation_config.get_working_file_path("paragraph_finder.json"),
        )
    StylesAndFormulas(translation_config).process(docs)
    logger.debug(f"finish styles and formulas from {temp_pdf_path}")
    if translation_config.debug:
        xml_converter.write_json(
            docs,
            translation_config.get_working_file_path("styles_and_formulas.json"),
        )

    translate_engine = translation_config.translator

    support_llm_translate = False
    try:
        if translate_engine and hasattr(translate_engine, "do_llm_translate"):
            translate_engine.do_llm_translate(None)
            support_llm_translate = True
    except NotImplementedError:
        support_llm_translate = False
    il_translator = None
    if support_llm_translate:
        il_translator = ILTranslatorLLMOnly(translate_engine, translation_config)
    else:
        il_translator = ILTranslator(translate_engine, translation_config)

    il_translator.translate(docs)
    logger.debug(f"finish ILTranslator from {temp_pdf_path}")
    if translation_config.debug:
        xml_converter.write_json(
            docs,
            translation_config.get_working_file_path("il_translated.json"),
        )

    if translation_config.debug:
        AddDebugInformation(translation_config).process(docs)
        xml_converter.write_json(
            docs,
            translation_config.get_working_file_path("add_debug_information.json"),
        )
    mono_watermark_first_page_doc_bytes = None
    dual_watermark_first_page_doc_bytes = None
    try:
        if translation_config.watermark_output_mode == WatermarkOutputMode.Both:
            mono_watermark_first_page_doc_bytes, dual_watermark_first_page_doc_bytes = (
                generate_first_page_with_watermark(doc_pdf2zh, translation_config, docs)
            )
    except Exception:
        logger.warning(
            "Failed to generate watermark for first page, using no watermark"
        )
        translation_config.watermark_output_mode = WatermarkOutputMode.NoWatermark
        mono_watermark_first_page_doc_bytes = None
        dual_watermark_first_page_doc_bytes = None

    Typesetting(translation_config).typsetting_document(docs)
    logger.debug(f"finish typsetting from {temp_pdf_path}")
    if translation_config.debug:
        xml_converter.write_json(
            docs,
            translation_config.get_working_file_path("typsetting.json"),
        )

    pdf_creater = PDFCreater(temp_pdf_path, docs, translation_config)
    result = pdf_creater.write(translation_config)
    try:
        if mono_watermark_first_page_doc_bytes:
            mono_watermark_pdf = merge_watermark_doc(
                result.mono_pdf_path,
                mono_watermark_first_page_doc_bytes,
                translation_config,
            )
            result.mono_pdf_path = mono_watermark_pdf
    except Exception:
        result.mono_pdf_path = result.no_watermark_mono_pdf_path
    try:
        if dual_watermark_first_page_doc_bytes:
            dual_watermark_pdf = merge_watermark_doc(
                result.dual_pdf_path,
                dual_watermark_first_page_doc_bytes,
                translation_config,
            )
            result.dual_pdf_path = dual_watermark_pdf
    except Exception:
        result.dual_pdf_path = result.no_watermark_dual_pdf_path

    result.original_pdf_path = translation_config.input_file

    return result


def generate_first_page_with_watermark(
    mupdf: Document,
    translation_config: TranslationConfig,
    doc_il: il_version_1.Document,
) -> (io.BytesIO, io.BytesIO):
    first_page_doc = Document()
    first_page_doc.insert_pdf(mupdf, from_page=0, to_page=0)

    il_only_first_page_doc = il_version_1.Document()
    il_only_first_page_doc.total_pages = 1
    il_only_first_page_doc.page = [copy.deepcopy(doc_il.page[0])]

    watermarked_config = copy.copy(translation_config)
    watermarked_config.watermark_output_mode = WatermarkOutputMode.Watermarked
    try:
        watermarked_config.progress_monitor.disable = True
        watermarked_temp_pdf_path = watermarked_config.get_working_file_path(
            "watermarked_temp_input.pdf"
        )
        first_page_doc.save(watermarked_temp_pdf_path)

        Typesetting(watermarked_config).typsetting_document(il_only_first_page_doc)
        pdf_creater = PDFCreater(
            watermarked_temp_pdf_path.as_posix(),
            il_only_first_page_doc,
            watermarked_config,
        )
        result = pdf_creater.write(watermarked_config)
        mono_pdf_bytes = None
        dual_pdf_bytes = None
        if result.mono_pdf_path:
            mono_pdf_bytes = io.BytesIO()
            with Path(result.mono_pdf_path).open("rb") as f:
                mono_pdf_bytes.write(f.read())
            result.mono_pdf_path.unlink()
            mono_pdf_bytes.seek(0)

        if result.dual_pdf_path:
            dual_pdf_bytes = io.BytesIO()
            with Path(result.dual_pdf_path).open("rb") as f:
                dual_pdf_bytes.write(f.read())
            result.dual_pdf_path.unlink()
            dual_pdf_bytes.seek(0)

        return mono_pdf_bytes, dual_pdf_bytes
    finally:
        watermarked_config.progress_monitor.disable = False


def merge_watermark_doc(
    no_watermark_pdf_path: pathlib.PosixPath,
    watermark_first_page_pdf_bytes: io.BytesIO,
    translation_config: TranslationConfig,
) -> pathlib.PosixPath:
    if not no_watermark_pdf_path.exists():
        raise FileNotFoundError(
            f"no_watermark_pdf_path not found: {no_watermark_pdf_path}"
        )
    if not watermark_first_page_pdf_bytes:
        raise FileNotFoundError(
            f"watermark_first_page_pdf_bytes not found: {watermark_first_page_pdf_bytes}"
        )

    no_watermark_pdf = Document(no_watermark_pdf_path.as_posix())
    no_watermark_pdf.delete_page(0)

    watermark_first_page_pdf = Document("pdf", watermark_first_page_pdf_bytes)
    no_watermark_pdf.insert_pdf(
        watermark_first_page_pdf, from_page=0, to_page=0, start_at=0
    )

    new_save_path = no_watermark_pdf_path.with_name(
        no_watermark_pdf_path.name.replace(".no_watermark", "")
    )

    PDFCreater.save_pdf_with_timeout(
        no_watermark_pdf,
        new_save_path.as_posix(),
        translation_config=translation_config,
        clean=not translation_config.skip_clean,
    )
    return new_save_path


def download_font_assets():
    warmup()


def create_cache_folder():
    try:
        logger.debug(f"create cache folder at {CACHE_FOLDER}")
        Path(CACHE_FOLDER).mkdir(parents=True, exist_ok=True)
    except OSError:
        logger.critical(
            f"Failed to create cache folder at {CACHE_FOLDER}",
            exc_info=True,
        )
        exit(1)


def init():
    create_cache_folder()
