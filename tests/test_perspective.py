import unittest

import cv2
import numpy as np

from truescan.corners import detectCorners
from truescan.perspective import correctPerspective


class PerspectiveTests(unittest.TestCase):
    def test_rectify_detected_page_with_colored_markers(self):
        page = np.full((601, 1001, 3), 240, np.uint8)
        markers = [
            ((150, 120), (230, 30, 30)), ((800, 90), (30, 230, 30)),
            ((850, 480), (30, 30, 230)), ((200, 510), (210, 30, 210)),
        ]
        for location, color in markers:
            cv2.circle(page, location, 12, color, -1)
        reference = np.float32([[0, 0], [1000, 0], [1000, 600], [0, 600]])
        outline = np.float32([[254, 278], [1410, 98], [1550, 882], [432, 1012]])
        photo = cv2.warpPerspective(
            page, cv2.getPerspectiveTransform(reference, outline), (1801, 1133)
        )
        corners = detectCorners(photo)
        self.assertIsNotNone(corners)
        result = correctPerspective(photo, corners)
        height, width = result.shape[:2]
        self.assertGreater(width, 1100)
        self.assertGreater(height, 750)
        for (x, y), color in markers:
            expected_x = x * (width - 1) / 1000
            expected_y = y * (height - 1) / 600
            rows, columns = np.where(np.all(result == color, axis=2))
            self.assertGreater(len(rows), 0)
            self.assertLess(np.hypot(columns.mean() - expected_x, rows.mean() - expected_y), 5)

    def test_full_frame_manual_selection_preserves_pixels(self):
        for shape in ((20, 30), (20, 30, 3), (20, 30, 4)):
            image = np.arange(np.prod(shape)).astype(np.uint8).reshape(shape)
            result = correctPerspective(image, [[0, 0], [29, 0], [29, 19], [0, 19]])
            np.testing.assert_array_equal(result, image)

    def test_invalid_selections(self):
        image = np.zeros((30, 30), np.uint8)
        for corners in (
            None, [[0, 0]] * 4, [[0, 0], [10, 0], [20, 0], [0, 20]],
            [[0, 0], [10, 10], [10, 0], [0, 10]],
            [[0, 0], [0, 10], [10, 10], [10, 0]],
            [[0, 0], [30, 0], [29, 29], [0, 29]],
            [[0, 0], [29, 0], [np.nan, 29], [0, 29]],
        ):
            with self.subTest(corners=corners), self.assertRaises(ValueError):
                correctPerspective(image, corners)
