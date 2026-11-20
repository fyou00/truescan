"""Detect a visible, planar document outline."""

import cv2
import numpy as np


def _prepare_detection_image(image):
    height, width = image.shape[:2]
    scale = min(1.0, 800 / max(width, height))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    if size != (width, height):
        image = cv2.resize(image, size, interpolation=cv2.INTER_AREA)
    if image.ndim == 3:
        image = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    return cv2.GaussianBlur(image, (5, 5), 0)


def _order_corners(vertices):
    # approxPolyDP preserves contour order. Keep that adjacency even when
    # two corners have the same x+y (a diamond viewed straight on).
    if cv2.contourArea(vertices, oriented=True) < 0:
        vertices = vertices[::-1]
    x, y = vertices.T
    start = np.lexsort((x, y, x + y))[0]
    return np.roll(vertices, -start, axis=0)


def detectCorners(image: np.ndarray) -> np.ndarray | None:
    """Return four float32 (x, y) points in original pixels, TL/TR/BR/BL.

    Accepts an OpenCV uint8 grayscale, BGR, or BGRA image. Returns None
    when there is no sufficiently large, closed, convex four-sided outline.
    """
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        return None
    if image.ndim not in (2, 3) or min(image.shape[:2]) < 5:
        return None
    if image.ndim == 3 and image.shape[2] not in (3, 4):
        return None

    gray = _prepare_detection_image(image)
    edges = cv2.Canny(gray, 40, 120)
    closed = cv2.morphologyEx(edges, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    minimum_area = 0.05 * gray.size
    for contour in sorted(contours, key=cv2.contourArea, reverse=True):
        if cv2.contourArea(contour) < minimum_area:
            break
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.02 * perimeter, True)
        if len(polygon) == 4 and cv2.isContourConvex(polygon):
            points = _order_corners(polygon.reshape(4, 2)).astype(np.float32)
            # Map pixel centers using each actual, rounded resize dimension.
            ratios = np.array(image.shape[1::-1]) / np.array(gray.shape[::-1])
            return ((points + 0.5) * ratios - 0.5).astype(np.float32)
    return None
