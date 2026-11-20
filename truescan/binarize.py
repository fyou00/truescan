"""Convert an enhanced document to a single black-and-white channel."""

import cv2
import numpy as np


def binarizePage(image: np.ndarray, method: str = "adaptive") -> np.ndarray:
    """Return a uint8 page with black ink (0) and white paper (255).

    Accepts grayscale, BGR, or BGRA pixels. Threshold the visible color
    channels using local Gaussian thresholds or a global Otsu threshold.
    """
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        raise ValueError("Expected a uint8 image")
    if image.ndim not in (2, 3) or min(image.shape[:2]) < 1:
        raise ValueError("Expected a nonempty document image")
    if image.ndim == 3 and image.shape[2] not in (3, 4):
        raise ValueError("Expected a grayscale, BGR or BGRA image")
    if not isinstance(method, str) or method not in ("adaptive", "otsu"):
        raise ValueError("Expected method 'adaptive' or 'otsu'")

    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if image.ndim == 3 else image
    if method == "otsu":
        _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        return binary

    # OpenCV replicates border pixels, including for pages smaller than the window.
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 14
    )
