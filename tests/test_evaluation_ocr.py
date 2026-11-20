import unittest

from evaluation.ocr import score_text


class OcrMetricTests(unittest.TestCase):
    def test_scoring_normalizes_unicode_and_layout_and_counts_case_and_punctuation(self):
        score = score_text("ＡB\nCD.", "AB   Cd!")
        self.assertEqual((score.errors, score.characters), (2, 6))
        self.assertAlmostEqual(score.accuracy, 2 / 3)

    def test_excess_insertions_and_empty_result(self):
        extra = score_text("X", "XYZA")
        self.assertEqual(extra.cer, 3)
        self.assertEqual(extra.accuracy, 0)
        missing = score_text("AB", "\n ")
        self.assertEqual((missing.errors, missing.cer, missing.accuracy), (2, 1, 0))
        with self.assertRaises(ValueError):
            score_text(" ", "noise")
