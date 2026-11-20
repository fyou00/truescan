"""Correct uneven illumination and sharpen a rectified document."""

import cv2
import numpy as np


def _enhance_brightness(brightness):
    if brightness.min() == brightness.max():
        return brightness.copy()

    height, width = brightness.shape
    scale = min(1, 640 / max(height, width))
    size = (max(1, round(width * scale)), max(1, round(height * scale)))
    small = cv2.resize(brightness, size, interpolation=cv2.INTER_AREA)

    # Closing fills ink strokes so the smoothed field estimates paper brightness.
    radius = max(1, round(min(size) / 32))
    kernel_size = (2 * radius + 1, 2 * radius + 1)
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
    paper = cv2.morphologyEx(small, cv2.MORPH_CLOSE, kernel)
    paper = cv2.blur(paper, kernel_size)
    white_level = float(np.percentile(paper, 95))
    field = cv2.resize(paper, (width, height), interpolation=cv2.INTER_LINEAR)
    normalized = cv2.divide(brightness, np.maximum(field, 1), scale=white_level)

    grid = (max(1, min(8, width // 32)), max(1, min(8, height // 32)))
    contrast = cv2.createCLAHE(clipLimit=2.0, tileGridSize=grid).apply(normalized)
    balanced = cv2.addWeighted(normalized, 0.75, contrast, 0.25, 0)
    blurred = cv2.GaussianBlur(balanced, (0, 0), 1.0)
    return cv2.addWeighted(balanced, 1.4, blurred, -0.4, 0)


def enhancePage(image: np.ndarray) -> np.ndarray:
    """Enhance a rectified uint8 grayscale, BGR or BGRA page at its input size."""
    if not isinstance(image, np.ndarray) or image.dtype != np.uint8:
        raise ValueError("Expected a uint8 image")
    if image.ndim not in (2, 3) or min(image.shape[:2]) < 1:
        raise ValueError("Expected a nonempty document image")
    if image.ndim == 2:
        return _enhance_brightness(image)
    if image.shape[2] not in (3, 4):
        raise ValueError("Expected a grayscale, BGR or BGRA image")

    # Scale the three color channels together, preserving their ratios.
    color = image[:, :, :3]
    brightness = color.max(axis=2)
    enhanced = _enhance_brightness(brightness)
    gain = enhanced.astype(np.float32) / np.maximum(brightness, 1)
    result = image.copy()
    result[:, :, :3] = np.rint(color * gain[:, :, None]).astype(np.uint8)
    return result
