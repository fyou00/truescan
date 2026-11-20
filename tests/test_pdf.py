import unittest

import cv2
import numpy as np
import pypdfium2 as pdfium

from truescan.pdf import exportPdf


def render_pages(data):
    """Read exported bytes with PDFium and render in BGR at source resolution."""
    pages = []
    with pdfium.PdfDocument(data) as document:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=300 / 72, rev_byteorder=False)
            pixels = bitmap.to_numpy()
            pages.append((page.get_size(), pixels[:, :, :3].copy()))
            bitmap.close()
            page.close()
    return pages


class PdfTests(unittest.TestCase):
    def test_default_color_and_selected_page_order(self):
        portrait = np.full((150, 100, 3), 245, np.uint8)
        portrait[15:45, 10:40] = (25, 50, 195)
        landscape = np.full((100, 175, 4), 250, np.uint8)
        landscape[:, :, 3] = 0
        landscape[55:85, 115:145, :3] = (205, 100, 20)
        exported = exportPdf([landscape, portrait])
        self.assertIsInstance(exported, bytes)
        pages = render_pages(exported)
        self.assertEqual(len(pages), 2)
        for (size, rendered), source, marker in zip(
            pages, (landscape, portrait), ((70, 130), (30, 25))
        ):
            with self.subTest(marker=marker):
                height, width = source.shape[:2]
                np.testing.assert_allclose(size, [width * 72 / 300, height * 72 / 300],
                                           atol=0.01)
                np.testing.assert_allclose(rendered[marker], source[marker][:3], atol=3)
                np.testing.assert_allclose(rendered[5, 5], source[5, 5, :3], atol=3)

    def test_grayscale_and_black_and_white_appearance(self):
        page = np.full((100, 150, 3), 220, np.uint8)
        page[20:25, 10:130] = (40, 60, 140)
        expected_gray = cv2.cvtColor(page, cv2.COLOR_BGR2GRAY)
        for mode, expected_ink, expected_paper in (
            ("grayscale", expected_gray[22, 50], 220), ("black-and-white", 0, 255)
        ):
            with self.subTest(mode=mode):
                (_, rendered), = render_pages(exportPdf([page], mode=mode))
                np.testing.assert_allclose(rendered[22, 50], expected_ink, atol=2)
                np.testing.assert_allclose(rendered[70, 50], expected_paper, atol=2)

    def test_preserve_already_binary_patches_at_odd_width(self):
        page = np.full((100, 151), 255, np.uint8)
        page[15:85, 10:80] = 0
        (_, rendered), = render_pages(exportPdf([page], mode="black-and-white"))
        np.testing.assert_array_equal(rendered[50, 40], [0, 0, 0])
        np.testing.assert_array_equal(rendered[50, 120], [255, 255, 255])

    def test_identical_pixel_buffers_with_different_dimensions(self):
        first = np.full((100, 150), 235, np.uint8)
        first[:, 25:55] = 45
        second = first.reshape(150, 100)
        pages = render_pages(exportPdf([first, second], mode="grayscale"))
        self.assertEqual(len(pages), 2)
        for (_, rendered), original in zip(pages, (first, second)):
            np.testing.assert_equal(rendered.shape[:2], original.shape)
            # Interior samples identify the different stripe pattern after reshaping.
            np.testing.assert_allclose(rendered[4::9, 8::15, 0], original[4::9, 8::15],
                                       atol=2)

    def test_invalid_page_or_mode(self):
        valid = np.full((100, 150), 255, np.uint8)
        for pages in ([], valid, [valid, None], [valid.astype(np.float32)],
                      [np.empty((0, 10), np.uint8)], [np.zeros((10, 10, 2), np.uint8)]):
            with self.assertRaises(ValueError):
                exportPdf(pages)
        with self.assertRaises(ValueError):
            exportPdf([valid], mode="sepia")
