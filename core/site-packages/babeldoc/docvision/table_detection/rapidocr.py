import logging
import re
from collections.abc import Generator

import cv2
import numpy as np
from babeldoc.assets.assets import get_table_detection_rapidocr_model_path
from babeldoc.docvision.doclayout import YoloBox
from babeldoc.docvision.doclayout import YoloResult
from rapidocr_onnxruntime import RapidOCR

try:
    import onnxruntime
except ImportError as e:
    if "DLL load failed" in str(e):
        raise OSError(
            "Microsoft Visual C++ Redistributable is not installed. "
            "Download it at https://aka.ms/vs/17/release/vc_redist.x64.exe"
        ) from e
    raise
import babeldoc.document_il.il_version_1
import pymupdf

logger = logging.getLogger(__name__)


def convert_to_yolo_result(predictions):
    """
    Convert RapidOCR predictions to YoloResult format.

    Args:
        predictions (list): List of predictions, where each prediction is a list of coordinates
                           in format [[x1, y1], [x2, y2], [x3, y3], [x4, y4], (text, confidence)]
                           or a numpy array of format [x1, y1, x2, y2, ...]

    Returns:
        YoloResult: Converted predictions in YoloResult format
    """
    boxes = []

    for pred in predictions:
        # Check if the prediction is in the format of 4 corner points
        if isinstance(pred, list) and len(pred) >= 5 and isinstance(pred[0], list):
            # Convert 4 corner points to xyxy format (min x, min y, max x, max y)
            points = np.array(pred[:4])
            x1, y1 = points[:, 0].min(), points[:, 1].min()
            x2, y2 = points[:, 0].max(), points[:, 1].max()
            xyxy = [x1, y1, x2, y2]
            box = YoloBox(xyxy=xyxy, conf=1.0, cls="text")
        # Check if the prediction is already in xyxy format
        elif isinstance(pred, list | np.ndarray) and len(pred) >= 4:
            if isinstance(pred, np.ndarray):
                pred = pred.tolist()
            xyxy = pred[:4]
            box = YoloBox(xyxy=xyxy, conf=1.0, cls="text")
        else:
            continue

        boxes.append(box)

    return YoloResult(names=["text"], boxes=boxes)


def create_yolo_result_from_nested_coords(nested_coords: np.ndarray, names: dict):
    boxes = []

    for quad in nested_coords.tolist():
        if len(quad) != 4:
            continue

        # Convert quad coordinates to xyxy format (min x, min y, max x, max y)
        x1, y1, x2, y2 = quad

        # Create YoloBox with confidence 1.0 and class 'text'
        box = YoloBox(
            xyxy=[float(x1), float(y1), float(x2), float(y2)], conf=np.array(1.0), cls=0
        )
        boxes.append(box)

    return YoloResult(names=names, boxes=boxes)


class RapidOCRModel:
    def __init__(self):
        self.use_cuda = False
        self.use_dml = False
        available_providers = onnxruntime.get_available_providers()
        for provider in available_providers:
            if re.match(r"dml", provider, re.IGNORECASE):
                self.use_dml = True
            elif re.match(r"cuda", provider, re.IGNORECASE):
                self.use_cuda = True

        self.model = RapidOCR(
            det_model_path=get_table_detection_rapidocr_model_path(),
            det_use_cuda=self.use_cuda,
            det_use_dml=self.use_dml,
        )
        self.names = {0: "table_text"}

    @property
    def stride(self):
        return 32

    def resize_and_pad_image(self, image, new_shape):
        """
        Resize and pad the image to the specified size, ensuring dimensions are multiples of stride.

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
            image,
            (resized_w, resized_h),
            interpolation=cv2.INTER_LINEAR,
        )

        # Calculate padding size and align to stride multiple
        pad_w = (new_w - resized_w) % self.stride
        pad_h = (new_h - resized_h) % self.stride
        top, bottom = pad_h // 2, pad_h - pad_h // 2
        left, right = pad_w // 2, pad_w - pad_w // 2

        # Add padding
        image = cv2.copyMakeBorder(
            image,
            top,
            bottom,
            left,
            right,
            cv2.BORDER_CONSTANT,
            value=(114, 114, 114),
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
        boxes[..., :4] = (boxes[..., :4] - [pad_x, pad_y, pad_x, pad_y]) / gain
        return boxes

    def predict(self, image, imgsz=800, batch_size=16, **kwargs):
        """
        Predict the layout of document pages.

        Args:
            image: A single image or a list of images of document pages.
            imgsz: Resize the image to this size. Must be a multiple of the stride.
            batch_size: Number of images to process in one batch.
            **kwargs: Additional arguments.

        Returns:
            A YoloResult object containing the detected boxes.
        """
        # Handle single image input
        assert isinstance(image, np.ndarray) and len(image.shape) == 3

        # Calculate target size based on the maximum height in the batch
        target_imgsz = 1024

        orig_shape = (image.shape[0], image.shape[1])

        pix = self.resize_and_pad_image(image, new_shape=target_imgsz)
        # pix = np.transpose(pix, (2, 0, 1))  # CHW
        # pix = pix.astype(np.float32) / 255.0  # Normalize to [0, 1]
        input_ = pix

        new_h, new_w = input_.shape[:2]

        # Run inference
        preds = self.model(input_, use_det=True, use_cls=False, use_rec=False)

        # Process each prediction in the batch
        if len(preds) > 0:
            preds_np = np.array(preds[0])[:, [0, 2], :].reshape([-1, 4])
            preds_np[..., :4] = self.scale_boxes(
                (new_h, new_w),
                preds_np[..., :4],
                orig_shape,
            )

            # Convert predictions to YoloResult format
            return create_yolo_result_from_nested_coords(preds_np, self.names)
        else:
            # Return empty YoloResult if no predictions
            return YoloResult(names=self.names, boxes=[])

    def handle_document(
        self,
        pages: list[babeldoc.document_il.il_version_1.Page],
        mupdf_doc: pymupdf.Document,
        translate_config,
        save_debug_image,
    ) -> Generator[
        tuple[babeldoc.document_il.il_version_1.Page, YoloResult], None, None
    ]:
        for page in pages:
            translate_config.raise_if_cancelled()
            pix = mupdf_doc[page.page_number].get_pixmap(dpi=72)
            image = np.fromstring(pix.samples, np.uint8).reshape(
                pix.height,
                pix.width,
                3,
            )[:, :, ::-1]

            table_boxes = []
            for layout in page.page_layout:
                if layout.class_name == "table":
                    table_boxes.append(layout.box)

            predict_result = self.predict(image)

            ok_boxes = []
            for box in predict_result.boxes:
                # Convert the box coordinates to float for proper comparison
                box_xyxy = [float(coord) for coord in box.xyxy]

                # Check if this box is inside any of the table boxes
                for table_box in table_boxes:
                    # Determine if box is inside or overlapping with table_box with image dimensions
                    if self._is_box_in_table(
                        box_xyxy, table_box, page, image.shape[1], image.shape[0]
                    ):
                        ok_boxes.append(box)
                        break

            yolo_result = YoloResult(names=self.names, boxes=ok_boxes)
            save_debug_image(
                image,
                yolo_result,
                page.page_number + 1,
            )
            yield page, yolo_result

    def _is_box_in_table(self, box_xyxy, table_box, page, img_width, img_height):
        """
        Check if a box from image coordinates is inside a table box from PDF coordinates.

        Args:
            box_xyxy (list): Box coordinates in image coordinate system [x1, y1, x2, y2]
            table_box (Box): Table box in PDF coordinate system
            page: The page object containing information for coordinate conversion
            img_width: Width of the image
            img_height: Height of the image

        Returns:
            bool: True if the box is inside or significantly overlapping with the table box
        """

        # Get table box coordinates in PDF coordinate system
        table_pdf_x1 = table_box.x
        table_pdf_y1 = table_box.y
        table_pdf_x2 = table_box.x2
        table_pdf_y2 = table_box.y2

        # Convert table box to image coordinates
        table_img_x1 = table_pdf_x1
        table_img_y1 = img_height - table_pdf_y2
        table_img_x2 = table_pdf_x2
        table_img_y2 = img_height - table_pdf_y1

        # Now check for overlap between the boxes
        # Calculate the area of overlap
        x_overlap = max(
            0, min(box_xyxy[2], table_img_x2) - max(box_xyxy[0], table_img_x1)
        )
        y_overlap = max(
            0, min(box_xyxy[3], table_img_y2) - max(box_xyxy[1], table_img_y1)
        )
        overlap_area = x_overlap * y_overlap

        # Calculate area of the detected box
        box_area = (box_xyxy[2] - box_xyxy[0]) * (box_xyxy[3] - box_xyxy[1])

        # If overlap area is significant relative to the box area, consider it inside
        if box_area > 0 and overlap_area / box_area > 0.5:
            return True

        return False
