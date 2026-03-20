import logging
from pathlib import Path

import cv2
import numpy as np
from pymupdf import Document

from babeldoc.document_il import il_version_1
from babeldoc.document_il.utils.style_helper import GREEN
from babeldoc.translation_config import TranslationConfig

logger = logging.getLogger(__name__)


class LayoutParser:
    stage_name = "Parse Page Layout"

    def __init__(self, translation_config: TranslationConfig):
        self.translation_config = translation_config
        self.model = translation_config.doc_layout_model

    def _save_debug_image(self, image: np.ndarray, layout, page_number: int):
        """Save debug image with drawn boxes if debug mode is enabled."""
        if not self.translation_config.debug:
            return

        debug_dir = Path(self.translation_config.get_working_file_path("ocr-box-image"))
        debug_dir.mkdir(parents=True, exist_ok=True)

        # Draw boxes on the image
        debug_image = image.copy()
        for box in layout.boxes:
            x0, y0, x1, y1 = box.xyxy
            cv2.rectangle(
                debug_image,
                (int(x0), int(y0)),
                (int(x1), int(y1)),
                (0, 255, 0),
                2,
            )
            # Add text label
            cv2.putText(
                debug_image,
                layout.names[box.cls],
                (int(x0), int(y0) - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                1,
            )

        # Save the image
        output_path = debug_dir / f"{page_number}.jpg"
        cv2.imwrite(str(output_path), debug_image)

    def _save_debug_box_to_page(self, page: il_version_1.Page):
        """Save debug boxes and text labels to the PDF page."""
        if not self.translation_config.debug:
            return

        color = GREEN

        for layout in page.page_layout:
            # Create a rectangle box
            rect = il_version_1.PdfRectangle(
                box=il_version_1.Box(
                    x=layout.box.x,
                    y=layout.box.y,
                    x2=layout.box.x2,
                    y2=layout.box.y2,
                ),
                graphic_state=color,
                debug_info=True,
            )
            page.pdf_rectangle.append(rect)

            # Create text label at top-left corner
            # Note: PDF coordinates are from bottom-left,
            # so we use y2 for top position
            style = il_version_1.PdfStyle(
                font_id="china-ss",
                font_size=4,
                graphic_state=color,
            )
            page.pdf_paragraph.append(
                il_version_1.PdfParagraph(
                    first_line_indent=False,
                    box=il_version_1.Box(
                        x=layout.box.x,
                        y=layout.box.y2,
                        x2=layout.box.x2,
                        y2=layout.box.y2 + 5,
                    ),
                    vertical=False,
                    pdf_style=style,
                    unicode=layout.class_name,
                    pdf_paragraph_composition=[
                        il_version_1.PdfParagraphComposition(
                            pdf_same_style_unicode_characters=il_version_1.PdfSameStyleUnicodeCharacters(
                                unicode=layout.class_name,
                                pdf_style=style,
                                debug_info=True,
                            ),
                        ),
                    ],
                    xobj_id=-1,
                ),
            )

    def process(self, docs: il_version_1.Document, mupdf_doc: Document):
        """Generate layouts for all pages that need to be translated."""
        # Get pages that need to be translated
        total = len(docs.page)
        with self.translation_config.progress_monitor.stage_start(
            self.stage_name,
            total,
        ) as progress:
            # Process predictions for each page
            for page, layouts in self.model.handle_document(
                docs.page, mupdf_doc, self.translation_config, self._save_debug_image
            ):
                page_layouts = []
                for layout in layouts.boxes:
                    # Convert coordinate system from picture to il
                    # system to the il coordinate system
                    x0, y0, x1, y1 = layout.xyxy
                    pix = mupdf_doc[page.page_number].get_pixmap()
                    h, w = pix.height, pix.width
                    x0, y0, x1, y1 = (
                        np.clip(int(x0 - 1), 0, w - 1),
                        np.clip(int(h - y1 - 1), 0, h - 1),
                        np.clip(int(x1 + 1), 0, w - 1),
                        np.clip(int(h - y0 + 1), 0, h - 1),
                    )
                    page_layout = il_version_1.PageLayout(
                        id=len(page_layouts) + 1,
                        box=il_version_1.Box(
                            x0.item(),
                            y0.item(),
                            x1.item(),
                            y1.item(),
                        ),
                        conf=layout.conf.item(),
                        class_name=layouts.names[layout.cls],
                    )
                    page_layouts.append(page_layout)

                page.page_layout = page_layouts
                self._save_debug_box_to_page(page)
                progress.advance(1)

        return docs
