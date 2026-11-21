"""Compare downloaded PDF pages against the ordered PNGs actually shown by the browser."""

import json
import sys

import cv2
import numpy as np
import pypdfium2 as pdfium


def compare_previews(filename, mode, dimensions, preview_paths):
    with pdfium.PdfDocument(filename) as document:
        assert len(document) == len(preview_paths), "Page count differs from the preview"
        for index, preview_path in enumerate(preview_paths):
            preview = cv2.imread(preview_path, cv2.IMREAD_COLOR)
            page = document[index]
            if dimensions:
                size_at_300_dpi = np.array(page.get_size()) * (300 / 72)
                np.testing.assert_allclose(size_at_300_dpi, dimensions[index], atol=0.1)
            bitmap = page.render(scale=300 / 72)
            rendered = bitmap.to_numpy()[:, :, :3]
            ph, pw = preview.shape[:2]
            rh, rw = rendered.shape[:2]
            assert abs(rw / rh - pw / ph) < 0.02, f"Page {index + 1} has the wrong dimensions"
            if mode == "grayscale":
                assert np.all(rendered == rendered[:, :, :1]), "Expected grayscale output"
            compared = cv2.resize(rendered, (pw, ph), interpolation=cv2.INTER_AREA)
            if mode == "color":
                # Use the centroid of the saturated marker to avoid interpolation at its edges.
                yy, xx = np.where(np.ptp(preview, axis=2) > 80)
                assert len(yy), "Missing colored registration mark"
                x, y = round(xx.mean()), round(yy.mean())
                np.testing.assert_allclose(compared[y, x], preview[y, x], atol=3)
            mean_difference = cv2.absdiff(compared, preview).mean()
            assert mean_difference < 4, f"Page {index + 1} differs from preview by {mean_difference:.2f}/255"
            bitmap.close()
            page.close()


if __name__ == "__main__":
    compare_previews(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]), sys.argv[4:])
