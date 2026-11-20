"""Export ordered scanner pages as a lossless image-only PDF."""

from collections.abc import Iterable

import cv2
import numpy as np
from fpdf import FPDF

from .binarize import binarizePage


PAGE_MODES = ("color", "grayscale", "black-and-white")


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


def exportPdf(pages: Iterable[np.ndarray], mode: str = "color") -> bytes:
    """Return a PDF at 300 dpi using color, grayscale, or black-and-white pages.

    Each uint8 grayscale, BGR, or BGRA page retains its own pixel dimensions.
    Color conversion ignores alpha, matching the binarization stage.
    """
    if not isinstance(mode, str) or mode not in PAGE_MODES:
        raise ValueError("Expected mode 'color', 'grayscale' or 'black-and-white'")
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
        height, width = (dimension * 72 / 300 for dimension in pixels.shape[:2])
        document.add_page(format=(width, height))
        # PNG includes dimensions in fpdf2's cache key for differently shaped pages.
        success, png = cv2.imencode(".png", pixels)
        if not success:
            raise ValueError("Could not encode the document page")
        document.image(png.tobytes(), x=0, y=0, w=width, h=height)
    if not document.pages:
        raise ValueError("Select at least one document page")
    return bytes(document.output())
