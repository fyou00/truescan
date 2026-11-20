"""Run from the project root with python -m evaluation.enhancement."""

from statistics import median
from time import perf_counter

import cv2
import numpy as np

from truescan.enhance import enhancePage


def make_pages():
    height, width = 480, 640
    reference = np.full((height, width, 3), 245, np.uint8)
    for row, label in enumerate(("PAGE FOUR", "Thin ink 0123", "Notes 4567", "Scan 89")):
        cv2.putText(reference, label, (54, 100 + row * 85), cv2.FONT_HERSHEY_SIMPLEX,
                    1.1, (35, 35, 35), 1, cv2.LINE_AA)
    cv2.rectangle(reference, (380, 80), (405, 190), (70, 90, 180), -1)
    cv2.line(reference, (44, 410), (595, 410), (175, 95, 40), 2)
    y, x = np.mgrid[0:height, 0:width]
    side = 0.55 + 0.45 * x / (width - 1)
    patch = np.exp(-0.5 * (((x - 220) / 125) ** 2 + ((y - 275) / 100) ** 2))
    for name, field in (("Uniform", np.ones_like(side)), ("Side", side),
                        ("Soft patch", 1 - 0.45 * patch)):
        yield name, reference, np.rint(reference * field[..., None]).astype(np.uint8)


def luminance_ssim(reference, sample):
    def blur(image):
        return cv2.GaussianBlur(image, (11, 11), 1.5)

    clean, actual = (cv2.cvtColor(image, cv2.COLOR_BGR2GRAY).astype(np.float64)
                     for image in (reference, sample))
    mean_clean, mean_actual = blur(clean), blur(actual)
    var_clean = blur(clean * clean) - mean_clean ** 2
    var_actual = blur(actual * actual) - mean_actual ** 2
    covariance = blur(clean * actual) - mean_clean * mean_actual
    c1, c2 = (0.01 * 255) ** 2, (0.03 * 255) ** 2
    score = ((2 * mean_clean * mean_actual + c1) * (2 * covariance + c2)
             / ((mean_clean ** 2 + mean_actual ** 2 + c1) * (var_clean + var_actual + c2)))
    return score[5:-5, 5:-5].mean()


def metrics(reference, sample):
    background = np.all(reference == 245, axis=2)
    gray = cv2.cvtColor(sample, cv2.COLOR_BGR2GRAY)
    dark, light = np.percentile(gray[background], [5, 95])
    psnr = np.inf if np.array_equal(reference, sample) else cv2.PSNR(reference, sample)
    return f"{psnr:.2f} dB / {luminance_ssim(reference, sample):.4f} / {light-dark:.0f}"


def main():
    for name, reference, sample in make_pages():
        enhanced = enhancePage(sample)
        times = []
        for _ in range(10):
            start = perf_counter()
            enhancePage(sample)
            times.append((perf_counter() - start) * 1000)
        print(f"{name}: {metrics(reference, sample)} -> {metrics(reference, enhanced)}"
              f" | {median(times):.2f} ms")


if __name__ == "__main__":
    main()
