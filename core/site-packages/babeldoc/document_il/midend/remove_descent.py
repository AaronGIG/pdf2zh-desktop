import logging
from collections import Counter
from functools import cache

from babeldoc.document_il import il_version_1
from babeldoc.translation_config import TranslationConfig

logger = logging.getLogger(__name__)


class RemoveDescent:
    stage_name = "Remove Char Descent"

    def __init__(self, translation_config: TranslationConfig):
        self.translation_config = translation_config

    def _remove_char_descent(
        self,
        char: il_version_1.PdfCharacter,
        font: il_version_1.PdfFont,
    ) -> float | None:
        """Remove descent from a single character and return the descent value.

        Args:
            char: The character to process
            font: The font used by this character

        Returns:
            The descent value if it was removed, None otherwise
        """
        if (
            char.box
            and char.box.y is not None
            and char.box.y2 is not None
            and font
            and hasattr(font, "descent")
        ):
            descent = font.descent * char.pdf_style.font_size / 1000
            if char.vertical:
                # For vertical text, remove descent from x coordinates
                char.box.x += descent
                char.box.x2 += descent
            else:
                # For horizontal text, remove descent from y coordinates
                char.box.y -= descent
                char.box.y2 -= descent
            return descent
        return None

    def process(self, document: il_version_1.Document):
        """Process the document to remove descent adjustments from character boxes.

        Args:
            document: The document to process
        """
        with self.translation_config.progress_monitor.stage_start(
            self.stage_name,
            len(document.page),
        ) as pbar:
            for page in document.page:
                self.translation_config.raise_if_cancelled()
                self.process_page(page)
                pbar.advance()

    def process_page(self, page: il_version_1.Page):
        """Process a single page to remove descent adjustments.

        Args:
            page: The page to process
        """
        # Build font map including xobjects
        fonts: dict[
            str | int,
            il_version_1.PdfFont | dict[str, il_version_1.PdfFont],
        ] = {f.font_id: f for f in page.pdf_font}
        page_fonts = {f.font_id: f for f in page.pdf_font}

        # Add xobject fonts
        for xobj in page.pdf_xobject:
            fonts[xobj.xobj_id] = page_fonts.copy()
            for font in xobj.pdf_font:
                fonts[xobj.xobj_id][font.font_id] = font

        @cache
        def get_font(
            font_id: str,
            xobj_id: int | None = None,
        ) -> il_version_1.PdfFont | None:
            if xobj_id is not None and xobj_id in fonts:
                font_map = fonts[xobj_id]
                if isinstance(font_map, dict) and font_id in font_map:
                    return font_map[font_id]
            return (
                fonts.get(font_id)
                if isinstance(fonts.get(font_id), il_version_1.PdfFont)
                else None
            )

        # Process all standalone characters in the page
        for char in page.pdf_character:
            if font := get_font(char.pdf_style.font_id, char.xobj_id):
                self._remove_char_descent(char, font)

        # Process all paragraphs
        for paragraph in page.pdf_paragraph:
            descent_values = []
            vertical_chars = []

            # Process all characters in paragraph compositions
            for comp in paragraph.pdf_paragraph_composition:
                # Handle direct characters
                if comp.pdf_character:
                    font = get_font(
                        comp.pdf_character.pdf_style.font_id,
                        comp.pdf_character.xobj_id,
                    )
                    if font:
                        descent = self._remove_char_descent(comp.pdf_character, font)
                        if descent is not None:
                            descent_values.append(descent)
                            vertical_chars.append(comp.pdf_character.vertical)

                # Handle characters in PdfLine
                elif comp.pdf_line:
                    for char in comp.pdf_line.pdf_character:
                        if font := get_font(char.pdf_style.font_id, char.xobj_id):
                            descent = self._remove_char_descent(char, font)
                            if descent is not None:
                                descent_values.append(descent)
                                vertical_chars.append(char.vertical)

                # Handle characters in PdfFormula
                elif comp.pdf_formula:
                    for char in comp.pdf_formula.pdf_character:
                        if font := get_font(char.pdf_style.font_id, char.xobj_id):
                            descent = self._remove_char_descent(char, font)
                            if descent is not None:
                                descent_values.append(descent)
                                vertical_chars.append(char.vertical)

                # Handle characters in PdfSameStyleCharacters
                elif comp.pdf_same_style_characters:
                    for char in comp.pdf_same_style_characters.pdf_character:
                        if font := get_font(char.pdf_style.font_id, char.xobj_id):
                            descent = self._remove_char_descent(char, font)
                            if descent is not None:
                                descent_values.append(descent)
                                vertical_chars.append(char.vertical)

            # Adjust paragraph box based on most common descent value
            if descent_values and paragraph.box:
                # Calculate mode of descent values
                descent_counter = Counter(descent_values)
                most_common_descent = descent_counter.most_common(1)[0][0]

                # Check if paragraph is vertical (all characters are vertical)
                is_vertical = all(vertical_chars) if vertical_chars else False

                # Adjust paragraph box
                if paragraph.box.y is not None and paragraph.box.y2 is not None:
                    if is_vertical:
                        # For vertical paragraphs, adjust x coordinates
                        paragraph.box.x += most_common_descent
                        paragraph.box.x2 += most_common_descent
                    else:
                        # For horizontal paragraphs, adjust y coordinates
                        paragraph.box.y -= most_common_descent
                        paragraph.box.y2 -= most_common_descent
