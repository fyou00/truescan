"""Compare the two threshold methods after enhancement on synthetic text."""

from statistics import median
from time import perf_counter

import cv2
import numpy as np

from evaluation.enhancement import luminance_ssim
from truescan.binarize import binarizePage
from truescan.enhance import enhancePage


def make_pages():
    height, width = 480, 640
    reference = np.full((height, width), 255, np.uint8)
    for row, text in enumerate(("PAGE FIVE", "Thin ink 0123", "Notes 4567", "Scan 89")):
        cv2.putText(reference, text, (60, 85 + row * 90), cv2.FONT_HERSHEY_SIMPLEX,
                    1.3, 0, 2, cv2.LINE_8)
    reference = np.where(reference < 128, 0, 255).astype(np.uint8)
    y, x = np.mgrid[:height, :width]
    ink = np.where(y < height / 2, 40, 150)
    material = cv2.GaussianBlur(np.where(reference == 0, ink, 240).astype(np.float32),
                                (3, 3), 0.6)
    noise = np.random.default_rng(5).normal(0, 1.2, reference.shape)
    patch = np.exp(-0.5 * (((x - 270) / 160) ** 2 + ((y - 280) / 110) ** 2))
    for name, light in (("Side", 0.50 + 0.50 * x / (width - 1)), ("Patch", 1 - 0.50 * patch)):
        yield name, reference, np.rint(material * light + noise).clip(0, 255).astype(np.uint8)


def report(label, reference, candidate):
    true_ink, found_ink = reference == 0, candidate < 128
    f1 = 2 * np.count_nonzero(true_ink & found_ink) / (true_ink.sum() + found_ink.sum())
    clean, result = (cv2.cvtColor(image, cv2.COLOR_GRAY2BGR) for image in (reference, candidate))
    psnr = np.inf if np.array_equal(reference, candidate) else cv2.PSNR(reference, candidate)
    print(f"{label:10} {psnr:.2f} dB  {luminance_ssim(clean, result):.4f} SSIM  {f1:.4f} ink F1")


def main():
    for name, reference, sample in make_pages():
        print(name)
        enhanced = enhancePage(sample)
        report("Enhanced", reference, enhanced)
        initial = cv2.adaptiveThreshold(
            enhanced, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 7
        )
        report("Initial C7", reference, initial)
        for method in ("adaptive", "otsu"):
            binary = binarizePage(enhanced, method=method)
            times = []
            for _ in range(10):
                start = perf_counter()
                binarizePage(enhanced, method=method)
                times.append((perf_counter() - start) * 1000)
            report(method, reference, binary)
            print(f"Median {median(times):.2f} ms")


if __name__ == "__main__":
    main()
