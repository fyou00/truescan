"""Local OCR and character-level scoring for the synthetic evaluation pages."""

import subprocess
import unicodedata
from dataclasses import dataclass

import cv2
import numpy as np


def recognize(image: np.ndarray) -> str:
    """Read a single English text block locally with Tesseract's LSTM engine."""
    success, png = cv2.imencode(".png", image)
    if not success:
        raise ValueError("Could not encode the OCR input")
    try:
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "-l", "eng", "--oem", "1", "--psm", "6"],
            input=png.tobytes(), capture_output=True, check=True, timeout=60,
        )
    except FileNotFoundError as error:
        raise RuntimeError("Install the Tesseract CLI and its English language data") from error
    except subprocess.CalledProcessError as error:
        raise RuntimeError(error.stderr.decode("utf-8", errors="replace").strip()) from error
    return result.stdout.decode("utf-8")


@dataclass(frozen=True)
class OcrScore:
    errors: int
    characters: int

    @property
    def cer(self) -> float:
        return self.errors / self.characters

    @property
    def accuracy(self) -> float:
        return max(0.0, 1.0 - self.cer)


def score_text(reference: str, observed: str) -> OcrScore:
    """Count unit-cost Levenshtein edits after NFKC and whitespace normalization.

    Cases and punctuation count. Empty OCR output deletes every reference character.
    Excess insertions can put CER above 1. Reported character accuracy bottoms at 0.
    """
    reference, observed = (
        " ".join(unicodedata.normalize("NFKC", text).split()) for text in (reference, observed)
    )
    if not reference:
        raise ValueError("OCR scoring requires a nonempty reference transcription")
    previous = list(range(len(observed) + 1))
    for i, expected in enumerate(reference, start=1):
        current = [i]
        for j, actual in enumerate(observed, start=1):
            current.append(min(previous[j] + 1, current[-1] + 1,
                               previous[j - 1] + (actual != expected)))
        previous = current
    return OcrScore(previous[-1], len(reference))
