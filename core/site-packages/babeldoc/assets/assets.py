import asyncio
import hashlib
import logging
import threading
import zipfile
from pathlib import Path

import httpx
from babeldoc.assets import embedding_assets_metadata
from babeldoc.assets.embedding_assets_metadata import DOC_LAYOUT_ONNX_MODEL_URL
from babeldoc.assets.embedding_assets_metadata import (
    DOCLAYOUT_YOLO_DOCSTRUCTBENCH_IMGSZ1024ONNX_SHA3_256,
)
from babeldoc.assets.embedding_assets_metadata import EMBEDDING_FONT_METADATA
from babeldoc.assets.embedding_assets_metadata import FONT_METADATA_URL
from babeldoc.assets.embedding_assets_metadata import FONT_URL_BY_UPSTREAM
from babeldoc.assets.embedding_assets_metadata import (
    TABLE_DETECTION_RAPIDOCR_MODEL_SHA3_256,
)
from babeldoc.assets.embedding_assets_metadata import TABLE_DETECTION_RAPIDOCR_MODEL_URL
from babeldoc.assets.embedding_assets_metadata import TIKTOKEN_CACHES
from babeldoc.const import get_cache_file_path
from tenacity import retry
from tenacity import stop_after_attempt
from tenacity import wait_exponential

logger = logging.getLogger(__name__)


class ResultContainer:
    def __init__(self):
        self.result = None

    def set_result(self, result):
        self.result = result


def run_in_another_thread(coro):
    result_container = ResultContainer()

    def _wrapper():
        result_container.set_result(asyncio.run(coro))

    thread = threading.Thread(target=_wrapper)
    thread.start()
    thread.join()
    return result_container.result


def run_coro(coro):
    return run_in_another_thread(coro)


def _retry_if_not_cancelled_and_failed(retry_state):
    """Only retry if the exception is not CancelledError and the attempt failed."""
    if retry_state.outcome.failed:
        exception = retry_state.outcome.exception()
        # Don't retry on CancelledError
        if isinstance(exception, asyncio.CancelledError):
            logger.debug("Operation was cancelled, not retrying")
            return False
        # Retry on network related errors
        if isinstance(
            exception, httpx.HTTPError | ConnectionError | ValueError | TimeoutError
        ):
            logger.warning(f"Network error occurred: {exception}, will retry")
            return True
    # Don't retry on success
    return False


def verify_file(path: Path, sha3_256: str):
    if not path.exists():
        return False
    hash_ = hashlib.sha3_256()
    with path.open("rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            hash_.update(chunk)
    return hash_.hexdigest() == sha3_256


@retry(
    retry=_retry_if_not_cancelled_and_failed,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    before_sleep=lambda retry_state: logger.warning(
        f"Download file failed, retrying in {retry_state.next_action.sleep} seconds... "
        f"(Attempt {retry_state.attempt_number}/3)"
    ),
)
async def download_file(
    client: httpx.AsyncClient | None = None,
    url: str = None,
    path: Path = None,
    sha3_256: str = None,
):
    if client is None:
        async with httpx.AsyncClient() as client:
            response = await client.get(url, follow_redirects=True)
    else:
        response = await client.get(url, follow_redirects=True)

    response.raise_for_status()
    with path.open("wb") as f:
        f.write(response.content)
    if not verify_file(path, sha3_256):
        path.unlink(missing_ok=True)
        raise ValueError(f"File {path} is corrupted")


@retry(
    retry=_retry_if_not_cancelled_and_failed,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=15),
    before_sleep=lambda retry_state: logger.warning(
        f"Get font metadata failed, retrying in {retry_state.next_action.sleep} seconds... "
        f"(Attempt {retry_state.attempt_number}/3)"
    ),
)
async def get_font_metadata(
    client: httpx.AsyncClient | None = None, upstream: str = None
):
    if upstream not in FONT_METADATA_URL:
        logger.critical(f"Invalid upstream: {upstream}")
        exit(1)

    if client is None:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                FONT_METADATA_URL[upstream], follow_redirects=True
            )
    else:
        response = await client.get(FONT_METADATA_URL[upstream], follow_redirects=True)

    response.raise_for_status()
    logger.debug(f"Get font metadata from {upstream} success")
    return upstream, response.json()


async def get_fastest_upstream_for_font(
    client: httpx.AsyncClient | None = None, exclude_upstream: list[str] = None
):
    tasks: list[asyncio.Task[tuple[str, dict]]] = []
    for upstream in FONT_METADATA_URL:
        if exclude_upstream and upstream in exclude_upstream:
            continue
        tasks.append(asyncio.create_task(get_font_metadata(client, upstream)))
    for future in asyncio.as_completed(tasks):
        try:
            result = await future
            for task in tasks:
                if not task.done():
                    task.cancel()
            return result
        except Exception as e:
            logger.exception(f"Error getting font metadata: {e}")
    logger.error("All upstreams failed")
    return None, None


async def get_fastest_upstream_for_model(client: httpx.AsyncClient | None = None):
    return await get_fastest_upstream_for_font(client, exclude_upstream=["github"])


async def get_fastest_upstream(client: httpx.AsyncClient | None = None):
    (
        fastest_upstream_for_font,
        online_font_metadata,
    ) = await get_fastest_upstream_for_font(client)
    if fastest_upstream_for_font is None:
        logger.error("Failed to get fastest upstream")
        exit(1)

    if fastest_upstream_for_font == "github":
        # since github is only store font, we need to get the fastest upstream for model
        fastest_upstream_for_model, _ = await get_fastest_upstream_for_model(client)
        if fastest_upstream_for_model is None:
            logger.error("Failed to get fastest upstream")
            exit(1)
    else:
        fastest_upstream_for_model = fastest_upstream_for_font

    return online_font_metadata, fastest_upstream_for_font, fastest_upstream_for_model


async def get_doclayout_onnx_model_path_async(client: httpx.AsyncClient | None = None):
    onnx_path = get_cache_file_path(
        "doclayout_yolo_docstructbench_imgsz1024.onnx", "models"
    )
    if verify_file(onnx_path, DOCLAYOUT_YOLO_DOCSTRUCTBENCH_IMGSZ1024ONNX_SHA3_256):
        return onnx_path

    logger.info("doclayout onnx model not found or corrupted, downloading...")
    fastest_upstream, _ = await get_fastest_upstream_for_model(client)
    if fastest_upstream is None:
        logger.error("Failed to get fastest upstream")
        exit(1)

    url = DOC_LAYOUT_ONNX_MODEL_URL[fastest_upstream]

    await download_file(
        client, url, onnx_path, DOCLAYOUT_YOLO_DOCSTRUCTBENCH_IMGSZ1024ONNX_SHA3_256
    )
    logger.info(f"Download doclayout onnx model from {fastest_upstream} success")
    return onnx_path


async def get_table_detection_rapidocr_model_path_async(
    client: httpx.AsyncClient | None = None,
):
    onnx_path = get_cache_file_path("ch_PP-OCRv4_det_infer.onnx", "models")
    if verify_file(onnx_path, TABLE_DETECTION_RAPIDOCR_MODEL_SHA3_256):
        return onnx_path

    logger.info("table detection rapidocr model not found or corrupted, downloading...")
    fastest_upstream, _ = await get_fastest_upstream_for_model(client)
    if fastest_upstream is None:
        logger.error("Failed to get fastest upstream")
        exit(1)

    url = TABLE_DETECTION_RAPIDOCR_MODEL_URL[fastest_upstream]

    await download_file(client, url, onnx_path, TABLE_DETECTION_RAPIDOCR_MODEL_SHA3_256)
    logger.info(
        f"Download table detection rapidocr model from {fastest_upstream} success"
    )
    return onnx_path


def get_doclayout_onnx_model_path():
    return run_coro(get_doclayout_onnx_model_path_async())


def get_table_detection_rapidocr_model_path():
    return run_coro(get_table_detection_rapidocr_model_path_async())


def get_font_url_by_name_and_upstream(font_file_name: str, upstream: str):
    if upstream not in FONT_URL_BY_UPSTREAM:
        logger.critical(f"Invalid upstream: {upstream}")
        exit(1)

    return FONT_URL_BY_UPSTREAM[upstream](font_file_name)


async def get_font_and_metadata_async(
    font_file_name: str,
    client: httpx.AsyncClient | None = None,
    fastest_upstream: str | None = None,
    font_metadata: dict | None = None,
):
    cache_file_path = get_cache_file_path(font_file_name, "fonts")
    if font_file_name in EMBEDDING_FONT_METADATA and verify_file(
        cache_file_path, EMBEDDING_FONT_METADATA[font_file_name]["sha3_256"]
    ):
        return cache_file_path, EMBEDDING_FONT_METADATA[font_file_name]

    logger.info(f"Font {cache_file_path} not found or corrupted, downloading...")
    if fastest_upstream is None:
        fastest_upstream, font_metadata = await get_fastest_upstream_for_font(client)
        if fastest_upstream is None:
            logger.critical("Failed to get fastest upstream")
            exit(1)

        if font_file_name not in font_metadata:
            logger.critical(f"Font {font_file_name} not found in {font_metadata}")
            exit(1)

        if verify_file(cache_file_path, font_metadata[font_file_name]["sha3_256"]):
            return cache_file_path, font_metadata[font_file_name]

    assert font_metadata is not None

    url = get_font_url_by_name_and_upstream(font_file_name, fastest_upstream)
    if "sha3_256" not in font_metadata[font_file_name]:
        logger.critical(f"Font {font_file_name} not found in {font_metadata}")
        exit(1)
    await download_file(
        client, url, cache_file_path, font_metadata[font_file_name]["sha3_256"]
    )
    return cache_file_path, font_metadata[font_file_name]


def get_font_and_metadata(font_file_name: str):
    return run_coro(get_font_and_metadata_async(font_file_name))


def get_font_family(lang_code: str):
    font_family = embedding_assets_metadata.get_font_family(lang_code)
    return font_family


async def download_all_fonts_async(client: httpx.AsyncClient | None = None):
    for font_file_name in EMBEDDING_FONT_METADATA:
        if not verify_file(
            get_cache_file_path(font_file_name, "fonts"),
            EMBEDDING_FONT_METADATA[font_file_name]["sha3_256"],
        ):
            break
    else:
        logger.debug("All fonts are already downloaded")
        return

    fastest_upstream, font_metadata = await get_fastest_upstream_for_font(client)
    if fastest_upstream is None:
        logger.error("Failed to get fastest upstream")
        exit(1)
    logger.info(f"Downloading fonts from {fastest_upstream}")

    font_tasks = [
        asyncio.create_task(
            get_font_and_metadata_async(
                font_file_name, client, fastest_upstream, font_metadata
            )
        )
        for font_file_name in EMBEDDING_FONT_METADATA
    ]
    await asyncio.gather(*font_tasks)


async def async_warmup():
    logger.info("Downloading all assets...")
    from tiktoken import encoding_for_model

    _ = encoding_for_model("gpt-4o")
    async with httpx.AsyncClient() as client:
        onnx_task = asyncio.create_task(get_doclayout_onnx_model_path_async(client))
        onnx_task2 = asyncio.create_task(
            get_table_detection_rapidocr_model_path_async(client)
        )
        font_tasks = asyncio.create_task(download_all_fonts_async(client))
        await asyncio.gather(onnx_task, onnx_task2, font_tasks)


def warmup():
    run_coro(async_warmup())


def generate_all_assets_file_list():
    result = {}
    result["fonts"] = []
    result["models"] = []
    result["tiktoken"] = []
    for font_file_name in EMBEDDING_FONT_METADATA:
        result["fonts"].append(
            {
                "name": font_file_name,
                "sha3_256": EMBEDDING_FONT_METADATA[font_file_name]["sha3_256"],
            }
        )
    for tiktoken_file, sha3_256 in TIKTOKEN_CACHES.items():
        result["tiktoken"].append(
            {
                "name": tiktoken_file,
                "sha3_256": sha3_256,
            }
        )
    result["models"].append(
        {
            "name": "doclayout_yolo_docstructbench_imgsz1024.onnx",
            "sha3_256": DOCLAYOUT_YOLO_DOCSTRUCTBENCH_IMGSZ1024ONNX_SHA3_256,
        },
    )
    result["models"].append(
        {
            "name": "ch_PP-OCRv4_det_infer.onnx",
            "sha3_256": TABLE_DETECTION_RAPIDOCR_MODEL_SHA3_256,
        },
    )
    return result


async def generate_offline_assets_package_async(output_directory: Path | None = None):
    await async_warmup()
    logger.info("Generating offline assets package...")
    file_list = generate_all_assets_file_list()
    offline_assets_tag = get_offline_assets_tag(file_list)
    if output_directory is None:
        output_path = get_cache_file_path(
            f"offline_assets_{offline_assets_tag}.zip", "assets"
        )
    else:
        output_directory.mkdir(parents=True, exist_ok=True)
        output_path = output_directory / f"offline_assets_{offline_assets_tag}.zip"
    with zipfile.ZipFile(
        output_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as zipf:
        for file_type, file_descs in file_list.items():
            # zipf.mkdir(file_type)
            for file_desc in file_descs:
                file_name = file_desc["name"]
                sha3_256 = file_desc["sha3_256"]
                file_path = get_cache_file_path(file_name, file_type)
                if not verify_file(file_path, sha3_256):
                    logger.error(f"File {file_path} is corrupted")
                    exit(1)

                with file_path.open("rb") as f:
                    zipf.writestr(f"{file_type}/{file_name}", f.read())
    logger.info(f"Offline assets package generated at {output_path}")


async def restore_offline_assets_package_async(input_path: Path | None = None):
    file_list = generate_all_assets_file_list()
    offline_assets_tag = get_offline_assets_tag(file_list)
    if input_path is None:
        input_path = get_cache_file_path(
            f"offline_assets_{offline_assets_tag}.zip", "assets"
        )
    else:
        if input_path.exists() and input_path.is_dir():
            input_path = input_path / f"offline_assets_{offline_assets_tag}.zip"
        if not input_path.exists():
            logger.critical(f"Offline assets package not found: {input_path}")
            exit(1)

        import re

        offline_assets_tag_from_input_path = re.match(
            r"offline_assets_(.*)\.zip", input_path.name
        ).group(1)
        if offline_assets_tag != offline_assets_tag_from_input_path:
            logger.critical(
                f"Offline assets tag mismatch: {offline_assets_tag} != {offline_assets_tag_from_input_path}"
            )
            exit(1)
    nothing_changed = True
    with zipfile.ZipFile(input_path, "r") as zipf:
        for file_type, file_descs in file_list.items():
            for file_desc in file_descs:
                file_name = file_desc["name"]
                file_path = get_cache_file_path(file_name, file_type)

                if verify_file(file_path, file_desc["sha3_256"]):
                    continue
                nothing_changed = False
                with zipf.open(f"{file_type}/{file_name}", "r") as f:
                    with file_path.open("wb") as f2:
                        f2.write(f.read())
                if not verify_file(file_path, file_desc["sha3_256"]):
                    logger.critical(
                        "Offline assets package is corrupted, please delete it and try again"
                    )
                    exit(1)
    if not nothing_changed:
        logger.info(f"Offline assets package restored from {input_path}")


def get_offline_assets_tag(file_list: dict | None = None):
    if file_list is None:
        file_list = generate_all_assets_file_list()
    import orjson

    # noinspection PyTypeChecker
    offline_assets_tag = hashlib.sha3_256(
        orjson.dumps(
            file_list,
            option=orjson.OPT_APPEND_NEWLINE
            | orjson.OPT_INDENT_2
            | orjson.OPT_SORT_KEYS,
        )
    ).hexdigest()
    return offline_assets_tag


def generate_offline_assets_package(output_directory: Path | None = None):
    return run_coro(generate_offline_assets_package_async(output_directory))


def restore_offline_assets_package(input_path: Path | None = None):
    return run_coro(restore_offline_assets_package_async(input_path))


if __name__ == "__main__":
    from rich.logging import RichHandler

    logging.basicConfig(level=logging.DEBUG, handlers=[RichHandler()])
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    # warmup()
    # generate_offline_assets_package()
    # restore_offline_assets_package(Path(
    #     '/Users/aw/.cache/babeldoc/assets/offline_assets_33971e4940e90ba0c35baacda44bbe83b214f4703a7bdb8b837de97d0383508c.zip'))
    # warmup()
