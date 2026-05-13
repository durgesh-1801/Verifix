from __future__ import annotations

import logging
import math

import numpy as np
from PIL import Image, ImageFilter

logger = logging.getLogger(__name__)

try:
    import cv2
except ImportError:  # pragma: no cover - depends on runtime package availability
    cv2 = None


def _to_cv(image: Image.Image) -> np.ndarray:
    return np.array(image.convert("RGB"))


def _to_pil(image: np.ndarray) -> Image.Image:
    if image.ndim == 2:
        return Image.fromarray(image)
    return Image.fromarray(image[:, :, ::-1] if cv2 is not None else image)


def _deskew(image: np.ndarray) -> np.ndarray:
    if cv2 is None:
        return image

    coords = np.column_stack(np.where(image < 250))
    if len(coords) < 10:
        return image

    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    elif angle > 45:
        angle = angle - 90

    if math.isclose(angle, 0.0, abs_tol=0.5):
        return image

    height, width = image.shape[:2]
    center = (width // 2, height // 2)
    matrix = cv2.getRotationMatrix2D(center, angle, 1.0)
    return cv2.warpAffine(
        image,
        matrix,
        (width, height),
        flags=cv2.INTER_CUBIC,
        borderMode=cv2.BORDER_REPLICATE,
    )


def preprocess_image(image: Image.Image) -> Image.Image:
    """Apply a conservative invoice-oriented preprocessing pipeline."""
    working = image.convert("L")

    if cv2 is None:
        enlarged = working.resize(
            (max(working.width * 2, 1), max(working.height * 2, 1)),
            Image.Resampling.LANCZOS,
        )
        return enlarged.filter(ImageFilter.SHARPEN)

    cv_image = np.array(working)
    cv_image = cv2.fastNlMeansDenoising(cv_image, None, 12, 7, 21)
    cv_image = cv2.resize(cv_image, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC)
    cv_image = cv2.adaptiveThreshold(
        cv_image,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )
    cv_image = _deskew(cv_image)
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    cv_image = cv2.filter2D(cv_image, -1, kernel)
    return _to_pil(cv_image)
