from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

try:
    from babeldoc.translator.translator import BaseTranslator
except ImportError:  # pragma: no cover - legacy development bundle only
    from pdf2zh.translator import BaseTranslator


MIN_PAGES_PER_PART = 50
DEFAULT_MAX_PAGES_PER_PART = 50


class _LocalGGUFTranslator(BaseTranslator):
    """Adapter that lets BabelDOC call the local GGUF OpenAI-compatible server."""

    name = "local-gguf"
    client = None
    cancel_event = None
    temperature = 0.15
    max_tokens = 2048

    def __init__(self, lang_in, lang_out, service_model, envs=None, prompt=None,
                 ignore_cache=False, **kwargs):
        self.model = service_model or "local-gguf"
        try:
            super().__init__(lang_in, lang_out, ignore_cache)
        except TypeError:  # pragma: no cover - legacy pdf2zh fallback
            super().__init__(lang_in, lang_out, service_model, ignore_cache)
        self.prompt_template = prompt

    def prompt(self, text):
        return [
            {
                "role": "system",
                "content": "You are a professional, authentic machine translation engine.",
            },
            {
                "role": "user",
                "content": (
                    f"Translate the following text into {self.lang_out}. "
                    "Output translation only. Preserve formulas, placeholders, "
                    "numbers, units, ordering, and the exact line breaks, tabs, "
                    "and spacing of the input. Translate each line or table-cell "
                    "label independently; never merge, split, reorder, or expand "
                    "short cells into explanations. "
                    "Do not add explanations or notes.\n\n"
                    f"{text}"
                ),
            },
        ]

    def do_translate(self, text, rate_limit_params=None):
        if self.cancel_event and self.cancel_event.is_set():
            raise InterruptedError("翻译已取消")
        if self.client is None:
            raise RuntimeError("本地 GGUF 模型服务未准备好。")

        response = self.client.create_chat_completion(
            messages=self.prompt(text),
            temperature=float(self.temperature),
            max_tokens=max(256, min(int(self.max_tokens), max(256, len(text) * 2))),
        )
        try:
            content = response["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError("本地模型没有返回有效的翻译结果。") from exc
        content = str(content).strip()
        if not content:
            raise RuntimeError("本地模型返回了空翻译结果。")
        return content

    def do_llm_translate(self, text, rate_limit_params=None):
        """Keep local GGUF on BabelDOC's ordinary translation path."""
        raise NotImplementedError


def _make_local_translator(model, cancel, request, model_name, source, target):
    translator = _LocalGGUFTranslator(source, target, model_name, ignore_cache=False)
    translator.client = model
    translator.cancel_event = cancel
    translator.temperature = float(request.get("temperature", 0.15))
    translator.max_tokens = int(request.get("maxTokens", 2048))
    return translator


def _parse_pages(value):
    if not value:
        return None
    pages = []
    try:
        for raw_part in value.split(","):
            part = raw_part.strip()
            if not part:
                continue
            bits = [bit.strip() for bit in part.split("-")]
            if len(bits) == 2:
                start, end = (int(bits[0]), int(bits[1]))
                if start < 1 or end < start:
                    raise ValueError
                pages.extend(range(start - 1, end))
            elif len(bits) == 1:
                page = int(bits[0])
                if page < 1:
                    raise ValueError
                pages.append(page - 1)
            else:
                raise ValueError
    except (TypeError, ValueError):
        raise ValueError("页面范围格式不正确，请使用 1-5 或 1-5, 8。") from None
    if not pages:
        raise ValueError("页面范围不能为空，请使用 1-5 或 1-5, 8。")
    return list(dict.fromkeys(pages))


def _parse_max_pages_per_part(value):
    """Return the upstream page split limit, or None when splitting is off."""
    if value in (None, "", 0, "0"):
        return None
    try:
        max_pages = int(value)
    except (TypeError, ValueError):
        raise ValueError("文档分块页数必须是整数，0 表示不拆分。") from None
    if max_pages < 0:
        raise ValueError("文档分块页数必须大于等于 0。")
    if 0 < max_pages < MIN_PAGES_PER_PART:
        raise ValueError(f"文档分块页数至少为 {MIN_PAGES_PER_PART} 页。")
    return max_pages


def _crop_pdf_file(path: Path, page_indexes: list[int]) -> None:
    """Crop an upstream output in place without keeping another PDF in memory."""
    import fitz

    fd, temp_name = tempfile.mkstemp(prefix=f".{path.stem}-", suffix=".pdf", dir=path.parent)
    os.close(fd)
    temp_path = Path(temp_name)
    try:
        with fitz.open(path) as document:
            if any(index < 0 or index >= document.page_count for index in page_indexes):
                raise ValueError("输出页面范围超出文档范围。")
            document.select(page_indexes)
            document.save(temp_path, garbage=3, deflate=True, use_objstms=1)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def _crop_output(path: Path, page_indexes: list[int], kind: str) -> None:
    """Use the Desktop crop helper when the original source is available."""
    try:
        from pdf2zh.output_util import crop_to_pages
    except ImportError:
        indexes = page_indexes
        if kind == "dual":
            indexes = [page * 2 + offset for page in page_indexes for offset in (0, 1)]
        _crop_pdf_file(path, indexes)
        return
    crop_to_pages(str(path), page_indexes, kind)


def _side_by_side(source: Path, dual_path: Path, target: Path, pages: list[int] | None) -> None:
    import fitz

    with fitz.open(source) as original, fitz.open(dual_path) as dual, fitz.open() as result:
        page_numbers = list(range(len(original))) if pages is None else pages
        for index, number in enumerate(page_numbers):
            left = original[number]
            right = dual[index * 2 + 1]
            page = result.new_page(
                width=left.rect.width + right.rect.width,
                height=max(left.rect.height, right.rect.height),
            )
            page.show_pdf_page(fitz.Rect(0, 0, left.rect.width, left.rect.height), original, number)
            page.show_pdf_page(
                fitz.Rect(left.rect.width, 0, left.rect.width + right.rect.width, right.rect.height),
                dual,
                index * 2 + 1,
            )
        result.save(target, garbage=3, deflate=True)


def translate_pdf(source, model, model_name, request, output_dir, progress, cancel):
    """Run the complete PDFMathTranslate-next/BabelDOC file pipeline."""
    import fitz
    from babeldoc.docvision.doclayout import OnnxModel
    from babeldoc.format.pdf.high_level import do_translate
    from babeldoc.format.pdf.high_level import get_translation_stage
    from babeldoc.progress_monitor import ProgressMonitor
    from babeldoc.format.pdf.translation_config import TranslationConfig
    from babeldoc.format.pdf.translation_config import WatermarkOutputMode

    source = Path(source)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with fitz.open(source) as document:
        page_count = document.page_count
    pages = _parse_pages(request.get("pages", "").strip())
    if pages is not None:
        invalid = [page + 1 for page in pages if page >= page_count]
        if invalid:
            raise ValueError(f"页码超出文档范围：文档共 {page_count} 页。")

    layout_path = (
        Path(sys._MEIPASS) / "resources" / "doclayout.onnx"
        if getattr(sys, "frozen", False)
        else Path(__file__).resolve().parents[1] / "resources" / "doclayout.onnx"
    )

    source_for_translation = source
    ocr_temp_dir = None
    if request.get("ocr", True):
        from pdf2zh.high_level import _ocr_pages

        ocr_temp_dir = tempfile.TemporaryDirectory(
            prefix=f".{source.stem}-ocr-", dir=output_dir
        )
        ocr_source = Path(ocr_temp_dir.name) / source.name
        with fitz.open(source) as ocr_document:
            _ocr_pages(
                ocr_document,
                pages,
                request.get("sourceLanguage", "en"),
                cancel,
                "tesseract",
            )
            ocr_document.save(ocr_source, garbage=3, deflate=True)
        source_for_translation = ocr_source

    max_pages_per_part = _parse_max_pages_per_part(
        request.get("maxPagesPerPart", DEFAULT_MAX_PAGES_PER_PART)
    )
    split_strategy = (
        TranslationConfig.create_max_pages_per_part_split_strategy(
            max_pages_per_part
        )
        if max_pages_per_part
        else None
    )

    translator = _make_local_translator(
        model,
        cancel,
        request,
        model_name,
        request.get("sourceLanguage", "en"),
        request.get("language", "zh"),
    )
    config = TranslationConfig(
        input_file=source_for_translation,
        output_dir=output_dir,
        pages=request.get("pages", "").strip() or None,
        lang_in=request.get("sourceLanguage", "en"),
        lang_out=request.get("language", "zh"),
        doc_layout_model=OnnxModel(str(layout_path)),
        translator=translator,
        no_dual=False,
        no_mono=False,
        watermark_output_mode=WatermarkOutputMode.NoWatermark,
        use_alternating_pages_dual=True,
        only_include_translated_page=pages is not None,
        split_strategy=split_strategy,
        # The OCR pre-stage above already handles image-only pages. Do not
        # rasterize the same pages again in every BabelDOC split part.
        skip_scanned_detection=True,
        ocr_workaround=False,
        auto_enable_ocr_workaround=False,
        auto_extract_glossary=False,
        save_auto_extracted_glossary=False,
        pool_max_workers=max(1, min(int(request.get("threads", 2)), 4)),
        term_pool_max_workers=1,
        # Match PDFMathTranslate-next defaults: clean decorative lines while
        # protecting lines that overlap detected figure/table regions.
        remove_non_formula_lines=bool(request.get("translateTableText", True)),
        non_formula_line_iou_threshold=0.9,
        figure_table_protection_threshold=0.9,
        report_interval=0.1,
    )

    progress_cancel = __import__("threading").Event()

    def report(**event):
        if cancel.is_set():
            progress_cancel.set()
        event_type = event.get("type")
        if event_type in {"progress_start", "progress_update", "progress_end"}:
            overall = event.get("overall_progress")
            if overall is None:
                overall = event.get("stage_progress", 0)
            progress(
                int(max(0, min(100, round(float(overall))))),
                100,
                event.get("stage") or "正在翻译并保留表格排版",
            )

    progress(0, 100, "正在准备 PDFMathTranslate-next 表格排版流程")
    try:
        with ProgressMonitor(
            get_translation_stage(config),
            progress_change_callback=report,
            finish_callback=lambda **_: None,
            report_interval=config.report_interval,
            cancel_event=progress_cancel,
        ) as monitor:
            result = do_translate(monitor, config)
    except asyncio.CancelledError as exc:
        raise InterruptedError("翻译已取消") from exc
    finally:
        if ocr_temp_dir is not None:
            ocr_temp_dir.cleanup()
    if cancel.is_set():
        raise InterruptedError("翻译已取消")
    if result is None:
        raise RuntimeError("原版翻译流程没有生成输出文件。")

    mono_path = Path(result.mono_pdf_path)
    dual_path = Path(result.dual_pdf_path)

    output_format = request.get("format", "dual")
    if output_format == "mono":
        dual_path.unlink(missing_ok=True)
        return [_output("mono", mono_path)]
    if output_format == "dual":
        mono_path.unlink(missing_ok=True)
        return [_output("dual", dual_path)]

    if output_format == "side":
        side_path = output_dir / f"{source.stem}-side-by-side.pdf"
        _side_by_side(source, dual_path, side_path, pages)
        mono_path.unlink(missing_ok=True)
        dual_path.unlink(missing_ok=True)
        return [_output("side", side_path)]

    side_path = output_dir / f"{source.stem}-side-by-side.pdf"
    _side_by_side(source, dual_path, side_path, pages)
    return [_output("mono", mono_path), _output("dual", dual_path), _output("side", side_path)]


def _output(kind: str, path: Path) -> dict:
    return {"kind": kind, "name": path.name, "path": str(path), "size": path.stat().st_size}
