import unittest

import cv2
import numpy as np

from truescan.corners import detectCorners


class DocumentCornerTests(unittest.TestCase):
    def assert_document(self, shape, vertices):
        image = np.full(shape, 36, dtype=np.uint8)
        expected = np.array(vertices, dtype=np.int32)
        cv2.fillConvexPoly(image, expected, (242, 242, 242))
        detected = detectCorners(image)
        self.assertIsNotNone(detected)
        self.assertEqual(detected.shape, (4, 2))
        np.testing.assert_allclose(detected, expected, atol=5, rtol=0)

    def test_straight_document(self):
        self.assert_document((480, 640), [(90, 55), (535, 55), (535, 415), (90, 415)])

    def test_tilted_document_in_original_pixels(self):
        self.assert_document(
            (1133, 1801, 3), [(254, 278), (1410, 98), (1550, 882), (432, 1012)]
        )

    def test_paper_matching_background(self):
        image = np.full((720, 960, 3), 240, dtype=np.uint8)
        cv2.rectangle(image, (150, 100), (770, 630), (240, 240, 240), -1)
        self.assertIsNone(detectCorners(image))
