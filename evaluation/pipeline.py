"""Run the synthetic photo-to-PDF benchmark with python -m evaluation.pipeline."""

import argparse
from dataclasses import dataclass
from statistics import median
from time import perf_counter

import cv2
import numpy as np
import pypdfium2 as pdfium

from evaluation.dataset import make_scenes
from evaluation.enhancement import luminance_ssim
from evaluation.ocr import recognize, score_text
from truescan.corners import detectCorners
from truescan.enhance import enhancePage
from truescan.pdf import exportPdf
from truescan.perspective import correctPerspective


@dataclass
class Measurement:
    psnr: float
    ssim: float
    errors: int
    characters: int


def measure(image, scene, mode):
    height, width = scene.reference.shape[:2]
    aligned = cv2.resize(image, (width, height), interpolation=cv2.INTER_LINEAR)
    reference = scene.reference
    if mode != "color":
        reference = cv2.cvtColor(reference, cv2.COLOR_BGR2GRAY)
        if mode == "black-and-white":
            reference = np.where(reference < 128, 0, 255).astype(np.uint8)
        reference = cv2.cvtColor(reference, cv2.COLOR_GRAY2BGR)
        aligned = cv2.cvtColor(cv2.cvtColor(aligned, cv2.COLOR_BGR2GRAY), cv2.COLOR_GRAY2BGR)
    score = score_text(scene.transcript, recognize(aligned))
    return Measurement(
        cv2.PSNR(reference, aligned),
        luminance_ssim(reference, aligned),
        score.errors,
        score.characters,
    )


def render_pdf(pdf):
    with pdfium.PdfDocument(pdf) as document:
        if len(document) != 1:
            raise ValueError("Expected one PDF page per scene")
        page = document[0]
        bitmap = page.render(scale=300 / 72, rev_byteorder=False)
        try:
            return bitmap.to_numpy()[:, :, :3].copy()
        finally:
            bitmap.close()
            page.close()


def scan(scene, mode):
    detected = detectCorners(scene.photo)
    corners = scene.corners
    distance = None
    result = "manual/missing"
    if detected is not None:
        distance = np.linalg.norm(detected - scene.corners, axis=1).max()
        tolerance = 0.01 * np.hypot(*scene.photo.shape[:2])
        if distance <= tolerance:
            result, corners = "auto", detected
        else:
            result = "manual/mismatch"
    enhanced = enhancePage(correctPerspective(scene.photo, corners))
    return result, distance, render_pdf(exportPdf([enhanced], mode=mode))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("color", "grayscale", "black-and-white"), default="color")
    mode = parser.parse_args().mode
    before_scores, after_scores, times = [], [], []
    automatic = 0
    print(f"PDF mode: {mode}\n")
    print("| Scene | Corners | Max error (px) | PSNR before / after (dB) | "
          "SSIM before / after | OCR edits before / after / characters | Median ms |")
    print("| --- | --- | ---: | ---: | ---: | ---: | ---: |")
    for scene in make_scenes():
        # Use only the axis-aligned box around the four labeled corner points.
        x, y, w, h = cv2.boundingRect(scene.corners)
        before = measure(scene.photo[y:y + h, x:x + w], scene, mode)
        scan(scene, mode)  # Warm-up excludes dataset creation, scoring and OCR.
        durations = []
        for _ in range(3):
            start = perf_counter()
            result, distance, output = scan(scene, mode)
            durations.append(1000 * (perf_counter() - start))
        after = measure(output, scene, mode)
        before_scores.append(before)
        after_scores.append(after)
        automatic += result == "auto"
        times.append(median(durations))
        error = "—" if distance is None else f"{distance:.2f}"
        print(f"| {scene.name} | {result} | {error} | {before.psnr:.2f} / {after.psnr:.2f} | "
              f"{before.ssim:.4f} / {after.ssim:.4f} | "
              f"{before.errors} / {after.errors} / {after.characters} | {times[-1]:.1f} |",
              flush=True)
    print(f"\nAutomatic corners: {automatic}/{len(times)}. Median of scene medians: {median(times):.1f} ms.")
    for label, scores in (("Baseline", before_scores), ("PDF", after_scores)):
        edits = sum(score.errors for score in scores)
        characters = sum(score.characters for score in scores)
        cer = edits / characters
        print(f"{label}: character errors {edits}/{characters}, CER {cer:.2%}, "
              f"accuracy {max(0, 1 - cer):.2%}.")


if __name__ == "__main__":
    main()
