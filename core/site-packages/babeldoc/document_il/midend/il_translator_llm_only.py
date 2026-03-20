import json
import logging
import re
from pathlib import Path

import Levenshtein
import tiktoken
from tqdm import tqdm

from babeldoc.document_il import Document
from babeldoc.document_il import Page
from babeldoc.document_il import PdfFont
from babeldoc.document_il import PdfParagraph
from babeldoc.document_il.midend.il_translator import DocumentTranslateTracker
from babeldoc.document_il.midend.il_translator import ILTranslator
from babeldoc.document_il.midend.il_translator import PageTranslateTracker
from babeldoc.document_il.translator.translator import BaseTranslator
from babeldoc.document_il.utils.fontmap import FontMapper
from babeldoc.document_il.utils.priority_thread_pool_executor import (
    PriorityThreadPoolExecutor,
)
from babeldoc.translation_config import TranslationConfig

logger = logging.getLogger(__name__)


class BatchParagraph:
    def __init__(
        self, paragraphs: list[PdfParagraph], page_tracker: PageTranslateTracker
    ):
        self.paragraphs = paragraphs
        self.trackers = [page_tracker.new_paragraph() for _ in paragraphs]


class ILTranslatorLLMOnly:
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
        self.shared_context_cross_split_part = (
            translation_config.shared_context_cross_split_part
        )

        if tokenizer is None:
            self.tokenizer = tiktoken.encoding_for_model("gpt-4o")
        else:
            self.tokenizer = tokenizer

        self.il_translator = ILTranslator(
            translate_engine=translate_engine,
            translation_config=translation_config,
            tokenizer=self.tokenizer,
        )

        try:
            self.translate_engine.do_llm_translate(None)
        except NotImplementedError as e:
            raise ValueError("LLM translator not supported") from e

    def calc_token_count(self, text: str) -> int:
        try:
            return len(self.tokenizer.encode(text, disallowed_special=()))
        except Exception:
            return 0

    def find_title_paragraph(self, docs: Document) -> PdfParagraph | None:
        """Find the first paragraph with layout_label 'title' in the document.

        Args:
            docs: The document to search in

        Returns:
            The first title paragraph found, or None if no title paragraph exists
        """
        for page in docs.page:
            for paragraph in page.pdf_paragraph:
                if paragraph.layout_label == "title":
                    logger.info(f"Found title paragraph: {paragraph.unicode}")
                    return paragraph
        return None

    def translate(self, docs: Document) -> None:
        tracker = DocumentTranslateTracker()

        if not self.translation_config.shared_context_cross_split_part.first_paragraph:
            # Try to find the first title paragraph
            title_paragraph = self.find_title_paragraph(docs)
            self.translation_config.shared_context_cross_split_part.first_paragraph = (
                title_paragraph
            )
            self.translation_config.shared_context_cross_split_part.recent_title_paragraph = title_paragraph
            if title_paragraph:
                logger.info(f"Found first title paragraph: {title_paragraph.unicode}")

        # count total paragraph
        total = sum(
            [
                len(
                    [
                        p
                        for p in page.pdf_paragraph
                        if p.debug_id is not None and p.unicode is not None
                    ]
                )
                for page in docs.page
            ]
        )
        with self.translation_config.progress_monitor.stage_start(
            self.stage_name,
            total,
        ) as pbar:
            with PriorityThreadPoolExecutor(
                max_workers=self.translation_config.qps,
            ) as executor2:
                with PriorityThreadPoolExecutor(
                    max_workers=self.translation_config.qps,
                ) as executor:
                    for page in docs.page:
                        self.process_page(
                            page,
                            executor,
                            pbar,
                            tracker.new_page(),
                            executor2,
                        )

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
        executor2: PriorityThreadPoolExecutor | None = None,
    ):
        self.translation_config.raise_if_cancelled()
        page_font_map = {}
        for font in page.pdf_font:
            page_font_map[font.font_id] = font
        page_xobj_font_map = {}
        for xobj in page.pdf_xobject:
            page_xobj_font_map[xobj.xobj_id] = page_font_map.copy()
            for font in xobj.pdf_font:
                page_xobj_font_map[xobj.xobj_id][font.font_id] = font

        paragraphs = []

        total_token_count = 0
        for paragraph in page.pdf_paragraph:
            if paragraph.debug_id is None or paragraph.unicode is None:
                continue
            # self.translate_paragraph(paragraph, pbar,tracker.new_paragraph(), page_font_map, page_xobj_font_map)
            total_token_count += self.calc_token_count(paragraph.unicode)
            paragraphs.append(paragraph)
            if paragraph.layout_label == "title":
                self.shared_context_cross_split_part.recent_title_paragraph = paragraph

            if total_token_count > 400 or len(paragraphs) > 5:
                executor.submit(
                    self.translate_paragraph,
                    BatchParagraph(paragraphs, tracker),
                    pbar,
                    page_font_map,
                    page_xobj_font_map,
                    self.translation_config.shared_context_cross_split_part.first_paragraph,
                    self.translation_config.shared_context_cross_split_part.recent_title_paragraph,
                    executor2,
                    priority=1048576 - total_token_count,
                )
                paragraphs = []
                total_token_count = 0

        if paragraphs:
            executor.submit(
                self.translate_paragraph,
                BatchParagraph(paragraphs, tracker),
                pbar,
                page_font_map,
                page_xobj_font_map,
                self.translation_config.shared_context_cross_split_part.first_paragraph,
                self.translation_config.shared_context_cross_split_part.recent_title_paragraph,
                executor2,
                priority=1048576 - total_token_count,
            )

    def translate_paragraph(
        self,
        batch_paragraph: BatchParagraph,
        pbar: tqdm | None = None,
        page_font_map: dict[str, PdfFont] = None,
        xobj_font_map: dict[int, dict[str, PdfFont]] = None,
        title_paragraph: PdfParagraph | None = None,
        local_title_paragraph: PdfParagraph | None = None,
        executor: PriorityThreadPoolExecutor | None = None,
    ):
        """Translate a paragraph using pre and post processing functions."""
        self.translation_config.raise_if_cancelled()
        should_translate_paragraph = []
        try:
            inputs = []

            for i in range(len(batch_paragraph.paragraphs)):
                paragraph = batch_paragraph.paragraphs[i]
                tracker = batch_paragraph.trackers[i]
                text, translate_input = self.il_translator.pre_translate_paragraph(
                    paragraph, tracker, page_font_map, xobj_font_map
                )
                if text is None:
                    pbar.advance(1)
                    continue
                should_translate_paragraph.append(i)
                inputs.append((text, translate_input, paragraph, tracker))
            if not inputs:
                return
            json_format_input = []

            for id_, input_text in enumerate(inputs):
                json_format_input.append(
                    {
                        "id": id_,
                        "input": input_text[0],
                        "layout_label": input_text[2].layout_label,
                    }
                )
            json_format_input = json.dumps(
                json_format_input, ensure_ascii=False, indent=2
            )
            llm_input = [
                "You are a professional, authentic machine translation engine."
            ]

            if title_paragraph:
                llm_input.append(
                    f"The first title in the full text: {title_paragraph.unicode}"
                )
            if (
                local_title_paragraph
                and local_title_paragraph.debug_id != title_paragraph.debug_id
            ):
                llm_input.append(
                    f"The most similar title in the full text: {local_title_paragraph.unicode}"
                )
            # Create a structured prompt template for LLM translation
            prompt_template = (
                f"""
    You will be given a JSON formatted input containing entries with "id" and "input" fields. Here is the input:
    
    ```json
    {json_format_input}
    ```
    
    For each entry in the JSON, translate the contents of the "input" field into {self.translation_config.lang_out}.
    Write the translation back into the "output" field for that entry.
    
    """
                + """
    Here is an example of the expected format:
    
    <example>
    ```json
    Input:
    {
        "id": 1,
        "input": "Source",
        "layout_label": "plain text"
    }
    ```
    Output:
    ```json
    {
        "id": 1,
        "output": "Translation"
    }
    ```
    </example>
    
    Please return the translated json directly without wrapping ```json``` tag or include any additional information.
    """
            )
            llm_input.append(prompt_template)

            final_input = "\n".join(llm_input).strip()
            llm_output = self.translate_engine.llm_translate(final_input)
            llm_output = llm_output.strip()

            llm_output = self._clean_json_output(llm_output)

            parsed_output = json.loads(llm_output)

            translation_results = {item["id"]: item["output"] for item in parsed_output}

            if len(translation_results) != len(inputs):
                raise Exception(
                    f"Translation results length mismatch. Expected: {len(inputs)}, Got: {len(translation_results)}"
                )

            for id_, output in translation_results.items():
                should_fallback = True
                try:
                    if not isinstance(output, str):
                        logger.warning(
                            f"Translation result is not a string. Output: {output}"
                        )
                        continue

                    id_ = int(id_)  # Ensure id is an integer
                    if id_ >= len(inputs):
                        logger.warning(f"Invalid id {id_}, skipping")
                        continue

                    # Clean up any excessive punctuation in the translated text
                    translated_text = re.sub(r"[. 。…，]{20,}", ".", output)

                    # Get the original input for this translation
                    translate_input = inputs[id_][1]

                    input_unicode = inputs[id_][2].unicode
                    output_unicode = translated_text

                    input_token_count = self.calc_token_count(input_unicode)
                    output_token_count = self.calc_token_count(output_unicode)

                    if not (0.3 < output_token_count / input_token_count < 3):
                        logger.warning(
                            f"Translation result is too long or too short. Input: {input_token_count}, Output: {output_token_count}"
                        )
                        continue

                    edit_distance = Levenshtein.distance(input_unicode, output_unicode)
                    if edit_distance < 5 and input_token_count > 20:
                        logger.warning(
                            f"Translation result edit distance is too small. distance: {edit_distance}, input: {input_unicode}, output: {output_unicode}"
                        )
                        continue
                    # Apply the translation to the paragraph
                    self.il_translator.post_translate_paragraph(
                        inputs[id_][2],
                        inputs[id_][3],
                        translate_input,
                        translated_text,
                    )
                    should_fallback = False
                    if pbar:
                        pbar.advance(1)
                except Exception as e:
                    logger.exception(f"Error translating paragraph. Error: {e}.")
                    # Ignore error and continue
                    continue
                finally:
                    if should_fallback:
                        logger.warning(
                            f"Fallback to simple translation. paragraph id: {inputs[id_][2].debug_id}"
                        )
                        executor.submit(
                            self.il_translator.translate_paragraph,
                            inputs[id_][2],
                            pbar,
                            inputs[id_][3],
                            page_font_map,
                            xobj_font_map,
                            priority=1048576 - self.calc_token_count(paragraph.unicode),
                        )

        except Exception as e:
            logger.warning(f"Error {e} during translation. try fallback")
            if not should_translate_paragraph:
                should_translate_paragraph = list(
                    range(len(batch_paragraph.paragraphs))
                )
            for i in should_translate_paragraph:
                paragraph = batch_paragraph.paragraphs[i]
                tracker = batch_paragraph.trackers[i]
                if paragraph.debug_id is None:
                    continue
                executor.submit(
                    self.il_translator.translate_paragraph,
                    paragraph,
                    pbar,
                    tracker,
                    page_font_map,
                    xobj_font_map,
                    priority=1048576 - self.calc_token_count(paragraph.unicode),
                )

    def _clean_json_output(self, llm_output: str) -> str:
        # Clean up JSON output by removing common wrapper tags
        llm_output = llm_output.strip()
        if llm_output.startswith("<json>"):
            llm_output = llm_output[6:]
        if llm_output.endswith("</json>"):
            llm_output = llm_output[:-7]
        if llm_output.startswith("```json"):
            llm_output = llm_output[7:]
        if llm_output.startswith("```"):
            llm_output = llm_output[3:]
        if llm_output.endswith("```"):
            llm_output = llm_output[:-3]
        return llm_output.strip()
