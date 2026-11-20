import unittest

import cv2
import numpy as np

from truescan.binarize import binarizePage


def make_uneven_page():
    """Render reference ink and a grayscale capture under a lighting gradient."""
    reference = np.full((160, 320), 255, np.uint8)
    for y in (40, 85, 130):
        cv2.putText(reference, "Scan 123    Scan 123", (12, y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 1, cv2.LINE_8)
    brightness = np.linspace(0.45, 1, reference.shape[1])
    page = np.rint(np.where(reference == 0, 85, 235) * brightness).astype(np.uint8)
    return reference, page


class BinarizeTests(unittest.TestCase):
    def test_default_adaptive_threshold_separates_ink_under_uneven_light(self):
        reference, page = make_uneven_page()
        result = binarizePage(page)
        np.testing.assert_array_equal(result, binarizePage(page, method="adaptive"))
        self.assertGreater(np.mean(result[reference == 0] == 0), 0.97)
        self.assertGreater(np.mean(result[reference == 255] == 255), 0.97)

    def test_minor_paper_variations_remain_white(self):
        page = np.full((80, 120), 220, np.uint8)
        page[10::10, 10::10] = 210
        page[40, 30:90] = 120
        expected = np.full_like(page, 255)
        expected[40, 30:90] = 0
        np.testing.assert_array_equal(binarizePage(page), expected)

    def test_otsu_comparison_matches_global_threshold(self):
        _, page = make_uneven_page()
        _, expected = cv2.threshold(page, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        np.testing.assert_array_equal(binarizePage(page, method="otsu"), expected)

    def test_color_and_alpha_produce_a_single_binary_channel(self):
        _, page = make_uneven_page()
        color = np.dstack([page // 2, page, page // 3])
        gray = cv2.cvtColor(color, cv2.COLOR_BGR2GRAY)
        alpha = np.resize(np.arange(256, dtype=np.uint8), gray.shape)
        for method in ("adaptive", "otsu"):
            expected = binarizePage(gray, method=method)
            for image in (gray, color, np.dstack([color, alpha])):
                with self.subTest(method=method, shape=image.shape):
                    original = image.copy()
                    result = binarizePage(image, method=method)
                    self.assertEqual(result.shape, gray.shape)
                    self.assertEqual(result.dtype, np.uint8)
                    np.testing.assert_array_equal(np.unique(result), [0, 255])
                    np.testing.assert_array_equal(result, expected)
                    np.testing.assert_array_equal(original, image)

    def test_invalid_input_or_method(self):
        for image in (None, np.empty((0, 8), np.uint8), np.zeros((8, 8), np.float32),
                      np.zeros((8, 8, 2), np.uint8)):
            with self.subTest(shape=np.shape(image)), self.assertRaises(ValueError):
                binarizePage(image)
        with self.assertRaises(ValueError):
            binarizePage(np.full((32, 32), 255, np.uint8), method="unknown")
