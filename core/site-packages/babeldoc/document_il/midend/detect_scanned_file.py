import logging

import cv2
import numpy as np
import pymupdf
from skimage.metrics import structural_similarity

from babeldoc.document_il import il_version_1
from babeldoc.document_il.babeldoc_exception.BabelDOCException import ScannedPDFError
from babeldoc.document_il.utils.style_helper import GREEN
from babeldoc.translation_config import TranslationConfig

logger = logging.getLogger(__name__)


class DetectScannedFile:
    stage_name = "DetectScannedFile"

    def __init__(self, translation_config: TranslationConfig):
        self.translation_config = translation_config

    def _save_debug_box_to_page(self, page: il_version_1.Page, similarity: float):
        """Save debug boxes and text labels to the PDF page."""
        if not self.translation_config.debug:
            return

        color = GREEN

        # Create text label at top-left corner
        # Note: PDF coordinates are from bottom-left,
        # so we use y2 for top position
        style = il_version_1.PdfStyle(
            font_id="china-ss",
            font_size=4,
            graphic_state=color,
        )
        page_width = page.cropbox.box.x2 - page.cropbox.box.x
        page_height = page.cropbox.box.y2 - page.cropbox.box.y
        unicode = f"scanned score: {similarity * 100:.2f} %"
        page.pdf_paragraph.append(
            il_version_1.PdfParagraph(
                first_line_indent=False,
                box=il_version_1.Box(
                    x=page.cropbox.box.x + page_width * 0.03,
                    y=page.cropbox.box.y,
                    x2=page.cropbox.box.x2,
                    y2=page.cropbox.box.y2 - page_height * 0.03,
                ),
                vertical=False,
                pdf_style=style,
                unicode=unicode,
                pdf_paragraph_composition=[
                    il_version_1.PdfParagraphComposition(
                        pdf_same_style_unicode_characters=il_version_1.PdfSameStyleUnicodeCharacters(
                            unicode=unicode,
                            pdf_style=style,
                            debug_info=True,
                        ),
                    ),
                ],
                xobj_id=-1,
            ),
        )

    def process(self, docs: il_version_1.Document):
        """Generate layouts for all pages that need to be translated."""
        # Get pages that need to be translated
        pages_to_translate = [
            page
            for page in docs.page
            if self.translation_config.should_translate_page(page.page_number + 1)
        ]
        mupdf = pymupdf.open(self.translation_config.get_working_file_path("input.pdf"))
        total = len(pages_to_translate)
        threshold = 0.8 * total
        threshold = max(threshold, 1)
        scanned = 0
        non_scanned = 0
        non_scanned_threshold = total - threshold
        with self.translation_config.progress_monitor.stage_start(
            self.stage_name,
            total,
        ) as progress:
            for page in pages_to_translate:
                if scanned < threshold and non_scanned < non_scanned_threshold:
                    # Only continue detection if both counts are below thresholds
                    is_scanned = self.detect_page_is_scanned(page, mupdf)
                    if is_scanned:
                        scanned += 1
                    else:
                        non_scanned += 1
                else:
                    # We have enough information to determine document type
                    non_scanned += 1
                progress.advance(1)

        if scanned > threshold:
            logger.warning(
                f"Detected {scanned} scanned pages, which is more than 80% of the total pages. "
                "Please check the input PDF file.",
            )
            raise ScannedPDFError("Scanned PDF detected.")

    @staticmethod
    def detect_page_is_scanned(page: il_version_1.Page, pdf: pymupdf.Document) -> bool:
        before_page_image = pdf[page.page_number].get_pixmap()
        before_page_image = np.frombuffer(before_page_image.samples, np.uint8).reshape(
            before_page_image.height,
            before_page_image.width,
            3,
        )[:, :, ::-1]
        new_xref = pdf.get_new_xref()
        pdf.update_object(new_xref, "<<>>")
        pdf.update_stream(new_xref, page.base_operations.value.encode("utf-8"))
        pdf[page.page_number].set_contents(new_xref)

        for xobj in page.pdf_xobject:
            pdf.update_stream(xobj.xref_id, xobj.base_operations.value.encode("utf-8"))

        after_page_image = pdf[page.page_number].get_pixmap()
        after_page_image = np.frombuffer(after_page_image.samples, np.uint8).reshape(
            after_page_image.height,
            after_page_image.width,
            3,
        )[:, :, ::-1]
        before_page_image = cv2.cvtColor(before_page_image, cv2.COLOR_RGB2GRAY)
        after_page_image = cv2.cvtColor(after_page_image, cv2.COLOR_RGB2GRAY)
        return structural_similarity(before_page_image, after_page_image) > 0.9
