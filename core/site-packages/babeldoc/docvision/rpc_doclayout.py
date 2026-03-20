import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import httpx
import msgpack
import numpy as np
import pymupdf
from tenacity import retry
from tenacity import retry_if_exception_type
from tenacity import stop_after_attempt
from tenacity import wait_exponential

import babeldoc
from babeldoc.docvision.doclayout import DocLayoutModel
from babeldoc.docvision.doclayout import YoloBox
from babeldoc.docvision.doclayout import YoloResult

logger = logging.getLogger(__name__)


def encode_image(image) -> bytes:
    """Read and encode image to bytes

    Args:
        image: Can be either a file path (str) or numpy array
    """
    if isinstance(image, str):
        if not Path(image).exists():
            raise FileNotFoundError(f"Image file not found: {image}")
        img = cv2.imread(image)
        if img is None:
            raise ValueError(f"Failed to read image: {image}")
    else:
        img = image

    # logger.debug(f"Image shape: {img.shape}")
    encoded = cv2.imencode(".jpg", img)[1].tobytes()
    # logger.debug(f"Encoded image size: {len(encoded)} bytes")
    return encoded


@retry(
    stop=stop_after_attempt(3),  # 最多重试3次
    wait=wait_exponential(
        multiplier=1, min=1, max=10
    ),  # 指数退避策略，初始1秒，最大10秒
    retry=retry_if_exception_type((httpx.HTTPError, Exception)),  # 针对哪些异常重试
    before_sleep=lambda retry_state: logger.warning(
        f"Request failed, retrying in {retry_state.next_action.sleep} seconds... "
        f"(Attempt {retry_state.attempt_number}/3)"
    ),
)
def predict_layout(
    image,
    host: str = "http://localhost:8000",
    imgsz: int = 1024,
):
    """
    Predict document layout using the MOSEC service

    Args:
        image: Can be either a file path (str) or numpy array
        host: Service host URL
        imgsz: Image size for model input

    Returns:
        List of predictions containing bounding boxes and classes
    """
    # Prepare request data
    if not isinstance(image, list):
        image = [image]
    image_data = [encode_image(image) for image in image]
    data = {
        "image": image_data,
        "imgsz": imgsz,
    }

    # Pack data using msgpack
    packed_data = msgpack.packb(data, use_bin_type=True)
    # logger.debug(f"Packed data size: {len(packed_data)} bytes")

    # Send request
    # logger.debug(f"Sending request to {host}/inference")
    response = httpx.post(
        f"{host}/inference",
        data=packed_data,
        headers={
            "Content-Type": "application/msgpack",
            "Accept": "application/msgpack",
        },
        timeout=300,
        follow_redirects=True,
    )

    # logger.debug(f"Response status: {response.status_code}")
    # logger.debug(f"Response headers: {response.headers}")

    if response.status_code == 200:
        try:
            result = msgpack.unpackb(response.content, raw=False)
            return result
        except Exception as e:
            logger.exception(f"Failed to unpack response: {e!s}")
            raise
    else:
        logger.error(f"Request failed with status {response.status_code}")
        logger.error(f"Response content: {response.content}")
        raise Exception(
            f"Request failed with status {response.status_code}: {response.text}",
        )


class ResultContainer:
    def __init__(self):
        self.result = YoloResult(boxes_data=np.array([]), names=[])


class RpcDocLayoutModel(DocLayoutModel):
    """DocLayoutModel implementation that uses RPC service."""

    def __init__(self, host: str = "http://localhost:8000"):
        """Initialize RPC model with host address."""
        self.host = host
        self._stride = 32  # Default stride value
        self._names = ["text", "title", "list", "table", "figure"]

    @property
    def stride(self) -> int:
        """Stride of the model input."""
        return self._stride

    def resize_and_pad_image(self, image, new_shape):
        """
        Resize and pad the image to the specified size,
        ensuring dimensions are multiples of stride.

        Parameters:
        - image: Input image
        - new_shape: Target size (integer or (height, width) tuple)
        - stride: Padding alignment stride, default 32

        Returns:
        - Processed image
        """
        if isinstance(new_shape, int):
            new_shape = (new_shape, new_shape)

        h, w = image.shape[:2]
        new_h, new_w = new_shape

        # Calculate scaling ratio
        r = min(new_h / h, new_w / w)
        resized_h, resized_w = int(round(h * r)), int(round(w * r))

        # Resize image
        image = cv2.resize(
            image, (resized_w, resized_h), interpolation=cv2.INTER_LINEAR
        )

        # Calculate padding size
        pad_h = new_h - resized_h
        pad_w = new_w - resized_w
        top, bottom = pad_h // 2, pad_h - pad_h // 2
        left, right = pad_w // 2, pad_w - pad_w // 2

        # Add padding
        image = cv2.copyMakeBorder(
            image, top, bottom, left, right, cv2.BORDER_CONSTANT, value=(114, 114, 114)
        )

        return image

    def scale_boxes(self, img1_shape, boxes, img0_shape):
        """
        Rescales bounding boxes (in the format of xyxy by default) from the shape of the image they were originally
        specified in (img1_shape) to the shape of a different image (img0_shape).

        Args:
            img1_shape (tuple): The shape of the image that the bounding boxes are for,
                in the format of (height, width).
            boxes (torch.Tensor): the bounding boxes of the objects in the image, in the format of (x1, y1, x2, y2)
            img0_shape (tuple): the shape of the target image, in the format of (height, width).

        Returns:
            boxes (torch.Tensor): The scaled bounding boxes, in the format of (x1, y1, x2, y2)
        """

        # Calculate scaling ratio
        gain = min(img1_shape[0] / img0_shape[0], img1_shape[1] / img0_shape[1])

        # Calculate padding size
        pad_x = round((img1_shape[1] - img0_shape[1] * gain) / 2 - 0.1)
        pad_y = round((img1_shape[0] - img0_shape[0] * gain) / 2 - 0.1)

        # Remove padding and scale boxes
        boxes = (boxes - [pad_x, pad_y, pad_x, pad_y]) / gain
        return boxes

    def predict_image(
        self,
        image,
        host: str = None,
        result_container: ResultContainer | None = None,
        imgsz: int = 1024,
    ) -> ResultContainer:
        """Predict the layout of document pages using RPC service."""
        if result_container is None:
            result_container = ResultContainer()
        target_imgsz = (800, 800)
        orig_h, orig_w = image.shape[:2]
        if image.shape[0] != target_imgsz[0] or image.shape[1] != target_imgsz[1]:
            image = self.resize_and_pad_image(image, new_shape=target_imgsz)
        preds = predict_layout([image], host=self.host, imgsz=800)

        if len(preds) > 0:
            for pred in preds:
                boxes = [
                    YoloBox(
                        None,
                        self.scale_boxes(
                            (800, 800), np.array(x["xyxy"]), (orig_h, orig_w)
                        ),
                        np.array(x["conf"]),
                        x["cls"],
                    )
                    for x in pred["boxes"]
                ]
                result_container.result = YoloResult(
                    boxes=boxes,
                    names={int(k): v for k, v in pred["names"].items()},
                )
        return result_container.result

    def predict(self, image, imgsz=1024, **kwargs) -> list[YoloResult]:
        """Predict the layout of document pages using RPC service."""
        # Handle single image input
        if isinstance(image, np.ndarray) and len(image.shape) == 3:
            image = [image]

        result_containers = [ResultContainer() for _ in image]
        predict_thread = ThreadPoolExecutor(max_workers=len(image))
        for img, result_container in zip(image, result_containers, strict=True):
            predict_thread.submit(
                self.predict_image, img, self.host, result_container, 800
            )
        predict_thread.shutdown(wait=True)
        result = [result_container.result for result_container in result_containers]
        return result

    def predict_page(
        self, page, mupdf_doc: pymupdf.Document, translate_config, save_debug_image
    ):
        translate_config.raise_if_cancelled()
        pix = mupdf_doc[page.page_number].get_pixmap(dpi=72)
        image = np.fromstring(pix.samples, np.uint8).reshape(
            pix.height,
            pix.width,
            3,
        )[:, :, ::-1]
        predict_result = self.predict_image(image, self.host, None, 800)
        save_debug_image(image, predict_result, page.page_number + 1)
        return page, predict_result

    def handle_document(
        self,
        pages: list[babeldoc.document_il.il_version_1.Page],
        mupdf_doc: pymupdf.Document,
        translate_config,
        save_debug_image,
    ):
        with ThreadPoolExecutor(max_workers=16) as executor:
            yield from executor.map(
                self.predict_page,
                pages,
                (mupdf_doc for _ in range(len(pages))),
                (translate_config for _ in range(len(pages))),
                (save_debug_image for _ in range(len(pages))),
            )

    @staticmethod
    def from_host(host: str) -> "RpcDocLayoutModel":
        """Create RpcDocLayoutModel from host address."""
        return RpcDocLayoutModel(host=host)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    # Test the service
    try:
        # Use a default test image if example/1.png doesn't exist
        image_path = "example/1.png"
        if not Path(image_path).exists():
            print(f"Warning: {image_path} not found.")
            print("Please provide the path to a test image:")
            image_path = input("> ")

        logger.info(f"Processing image: {image_path}")
        result = predict_layout(image_path)
        print("Prediction results:")
        print(result)
    except Exception as e:
        print(f"Error: {e!s}")
