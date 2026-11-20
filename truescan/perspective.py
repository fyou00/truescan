"""Rectify a planar document at source-image resolution."""

import cv2
import numpy as np


def correctPerspective(image: np.ndarray, corners) -> np.ndarray:
    """Warp an original uint8 photo using its ordered TL/TR/BR/BL pixel centers."""
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        raise ValueError("Expected a uint8 image")
    if image.ndim not in (2, 3) or min(image.shape[:2]) < 2:
        raise ValueError("Expected a nonempty document image")
    if image.ndim == 3 and image.shape[2] not in (3, 4):
        raise ValueError("Expected a grayscale, BGR or BGRA image")

    points = np.asarray(corners, dtype=np.float32)
    if points.shape != (4, 2) or not np.isfinite(points).all():
        raise ValueError("Select four finite document corners")
    height, width = image.shape[:2]
    if (points < 0).any() or (points > [width - 1, height - 1]).any():
        raise ValueError("Select corners inside the original image")
    if not cv2.isContourConvex(points) or cv2.contourArea(points, oriented=True) <= 0:
        raise ValueError("Select a convex outline clockwise from the top left")

    # Opposing edge lengths estimate the page dimensions in source pixels.
    top, right, bottom, left = np.linalg.norm(np.roll(points, -1, axis=0) - points, axis=1)
    page_width = round(float(max(top, bottom))) + 1
    page_height = round(float(max(left, right))) + 1
    if min(page_width, page_height) < 2 or cv2.contourArea(points) < 1:
        raise ValueError("The selected page is too small to rectify")
    destination = np.float32([
        [0, 0], [page_width - 1, 0],
        [page_width - 1, page_height - 1], [0, page_height - 1],
    ])
    transform = cv2.getPerspectiveTransform(points, destination)
    return cv2.warpPerspective(image, transform, (page_width, page_height))
