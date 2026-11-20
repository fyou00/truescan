import unittest

import cv2
import numpy as np

from truescan.enhance import enhancePage


def make_shadowed_page():
    """Render a clean reference and apply a smooth, side-to-side shadow."""
    reference = np.full((240, 360, 3), 240, np.uint8)
    for y in (60, 115, 170):
        cv2.putText(reference, "Fine print 123", (22, y), cv2.FONT_HERSHEY_SIMPLEX,
                    0.7, (65, 65, 65), 1, cv2.LINE_8)
    cv2.line(reference, (30, 195), (320, 195), (180, 65, 40), 3)
    illumination = np.linspace(0.48, 1.0, reference.shape[1])[None, :, None]
    shadowed = np.rint(reference * illumination).astype(np.uint8)
    return reference, shadowed


class EnhanceTests(unittest.TestCase):
    def test_shadow_reduction_against_clean_reference(self):
        reference, shadowed = make_shadowed_page()
        result = enhancePage(shadowed)
        background = np.all(reference == 240, axis=2)
        before = cv2.cvtColor(shadowed, cv2.COLOR_BGR2GRAY)
        after = cv2.cvtColor(result, cv2.COLOR_BGR2GRAY)
        self.assertLess(after[background].std(), before[background].std() / 2)
        self.assertGreater(cv2.PSNR(reference, result), cv2.PSNR(reference, shadowed))

    def test_thin_lettering_and_colored_ink_survive(self):
        reference, shadowed = make_shadowed_page()
        result = enhancePage(shadowed)
        ink = np.all(reference == 65, axis=2)
        text_contrast = np.median(result[reference == 240]) - np.median(result[ink])
        self.assertGreater(text_contrast, 100)
        blue, green, red = np.median(result[195, 40:310], axis=0)
        self.assertGreater(blue - max(green, red), 50)

    def test_image_modes_and_alpha(self):
        _, bgr = make_shadowed_page()
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        alpha = np.resize(np.arange(256, dtype=np.uint8), gray.shape)
        bgra = np.dstack([bgr, alpha])
        for image in (gray, bgr, bgra):
            with self.subTest(shape=image.shape):
                original = image.copy()
                result = enhancePage(image)
                self.assertEqual(result.shape, image.shape)
                self.assertEqual(result.dtype, np.uint8)
                np.testing.assert_array_equal(original, image)
        np.testing.assert_array_equal(enhancePage(bgra)[:, :, 3], alpha)

    def test_reject_invalid_page(self):
        for image in (None, np.empty((0, 8), np.uint8), np.zeros((8, 8), np.float32),
                      np.zeros((8, 8, 2), np.uint8)):
            with self.subTest(shape=np.shape(image)), self.assertRaises(ValueError):
                enhancePage(image)
