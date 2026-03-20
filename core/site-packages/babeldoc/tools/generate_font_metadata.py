# This script is used to automatically generate the following files:
# https://github.com/funstory-ai/BabelDOC-Assets/blob/main/font_metadata.json


import argparse
import hashlib
import io
import logging
from pathlib import Path

import babeldoc.high_level
import babeldoc.translation_config
import orjson
import pymupdf
from babeldoc.document_il import PdfFont
from rich.logging import RichHandler

logger = logging.getLogger(__name__)


def get_font_metadata(font_path) -> PdfFont:
    doc = pymupdf.open()
    page = doc.new_page(width=1000, height=1000)
    page.insert_font("test_font", font_path)
    translation_config = babeldoc.translation_config.TranslationConfig(
        *[None for _ in range(4)], doc_layout_model=1
    )
    translation_config.progress_monitor = babeldoc.high_level.ProgressMonitor(
        babeldoc.high_level.TRANSLATE_STAGES
    )
    translation_config.font = font_path
    il_creater = babeldoc.high_level.ILCreater(translation_config)
    il_creater.mupdf = doc
    buffer = io.BytesIO()
    doc.save(buffer)
    babeldoc.high_level.start_parse_il(
        buffer,
        doc_zh=doc,
        resfont="test_font",
        il_creater=il_creater,
        translation_config=translation_config,
    )

    il = il_creater.create_il()
    il_page = il.page[0]
    font_metadata = il_page.pdf_font[0]
    return font_metadata


def main():
    logging.basicConfig(level=logging.INFO, handlers=[RichHandler()])
    parser = argparse.ArgumentParser(description="Get font metadata.")
    parser.add_argument("assets_repo_path", type=str, help="Path to the font file.")
    args = parser.parse_args()
    repo_path = Path(args.assets_repo_path)
    assert repo_path.exists(), f"Assets repo path {repo_path} does not exist."
    assert (repo_path / "README.md").exists(), (
        f"Assets repo path {repo_path} does not contain a README.md file."
    )
    assert (repo_path / "fonts").exists(), (
        f"Assets repo path {repo_path} does not contain a fonts folder."
    )
    logger.info(f"Getting font metadata for {repo_path}")

    metadatas = {}
    for font_path in list((repo_path / "fonts").glob("**/*.ttf")):
        logger.info(f"Getting font metadata for {font_path}")
        with Path(font_path).open("rb") as f:
            # Read the file in chunks to handle large files efficiently
            hash_ = hashlib.sha3_256()
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                hash_.update(chunk)
        extracted_metadata = get_font_metadata(font_path)
        metadata = {
            "file_name": font_path.name,
            "font_name": extracted_metadata.name,
            "encoding_length": extracted_metadata.encoding_length,
            "bold": extracted_metadata.bold,
            "italic": extracted_metadata.italic,
            "monospace": extracted_metadata.monospace,
            "serif": extracted_metadata.serif,
            "ascent": extracted_metadata.ascent,
            "descent": extracted_metadata.descent,
            "sha3_256": hash_.hexdigest(),
            "size": font_path.stat().st_size,
        }
        metadatas[font_path.name] = metadata
    metadatas = orjson.dumps(
        metadatas,
        option=orjson.OPT_APPEND_NEWLINE | orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
    ).decode()
    print(f"FONT METADATA: {metadatas}")
    with (repo_path / "font_metadata.json").open("w") as f:
        f.write(metadatas)


if __name__ == "__main__":
    main()
