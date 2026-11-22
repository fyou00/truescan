"""Export ordered scanner pages as a lossless image-only PDF."""

from collections.abc import Iterable

import cv2
import numpy as np
from fpdf import FPDF

from .binarize import binarizePage


PAGE_MODES = ("color", "grayscale", "black-and-white")
PAGE_SIZES = ("original", "a4")


def renderPageMode(page: np.ndarray, mode: str) -> np.ndarray:
    """Convert a page for PDF output or a matching browser preview."""
    if not isinstance(mode, str) or mode not in PAGE_MODES:
        raise ValueError("Expected mode 'color', 'grayscale' or 'black-and-white'")
    if not isinstance(page, np.ndarray) or page.dtype != np.uint8:
        raise ValueError("Expected a uint8 image")
    if page.ndim not in (2, 3) or min(page.shape[:2]) < 1:
        raise ValueError("Expected a nonempty document image")
    if page.ndim == 3 and page.shape[2] not in (3, 4):
        raise ValueError("Expected a grayscale, BGR or BGRA image")

    if mode == "color":
        return cv2.cvtColor(page, cv2.COLOR_GRAY2BGR) if page.ndim == 2 else page[:, :, :3]
    if mode == "grayscale":
        return cv2.cvtColor(page, cv2.COLOR_BGR2GRAY) if page.ndim == 3 else page
    if page.ndim == 2 and np.all((page == 0) | (page == 255)):
        return page
    return binarizePage(page)


def exportPdf(pages: Iterable[np.ndarray], mode: str = "color", *, page_size: str = "original") -> bytes:
    """Return a PDF using original page sizes at 300 dpi or centered images on A4.

    Each uint8 grayscale, BGR, or BGRA page retains its own pixel dimensions.
    Color conversion ignores alpha, matching the binarization stage.
    """
    if not isinstance(mode, str) or mode not in PAGE_MODES:
        raise ValueError("Expected mode 'color', 'grayscale' or 'black-and-white'")
    if not isinstance(page_size, str) or page_size not in PAGE_SIZES:
        raise ValueError("Expected page_size 'original' or 'a4'")
    if isinstance(pages, np.ndarray):
        raise ValueError("Pass a sequence of pages, such as [image]")
    try:
        iterator = iter(pages)
    except TypeError as exc:
        raise ValueError("Expected an iterable of document pages") from exc
    document = FPDF(unit="pt")
    document.set_auto_page_break(False)
    document.set_image_filter("FlateDecode")
    for page in iterator:
        pixels = renderPageMode(page, mode)
        pixel_height, pixel_width = pixels.shape[:2]
        if page_size == "original":
            scale = 72 / 300
            width, height = pixel_width * scale, pixel_height * scale
        else:
            mm = 72 / 25.4
            width, height = 210 * mm, 297 * mm
            if pixel_width > pixel_height:
                width, height = height, width
            margin = 10 * mm
            scale = min((width - 2 * margin) / pixel_width, (height - 2 * margin) / pixel_height)
        image_width, image_height = pixel_width * scale, pixel_height * scale
        document.add_page(format=(width, height))
        # PNG includes dimensions in fpdf2's cache key for differently shaped pages.
        success, png = cv2.imencode(".png", pixels)
        if not success:
            raise ValueError("Could not encode the document page")
        document.image(png.tobytes(), x=(width - image_width) / 2, y=(height - image_height) / 2,
                       w=image_width, h=image_height)
    if not document.pages:
        raise ValueError("Select at least one document page")
    return bytes(document.output())
