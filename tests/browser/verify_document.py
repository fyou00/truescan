"""Compare downloaded PDF pages against the ordered PNGs actually shown by the browser."""

import sys

import cv2
import numpy as np
import pypdfium2 as pdfium


def compare_previews(filename, preview_paths):
    with pdfium.PdfDocument(filename) as document:
        assert len(document) == len(preview_paths), "Page count differs from the preview"
        for index, preview_path in enumerate(preview_paths):
            preview = cv2.imread(preview_path, cv2.IMREAD_COLOR)
            page = document[index]
            bitmap = page.render(scale=300 / 72)
            rendered = bitmap.to_numpy()[:, :, :3]
            ph, pw = preview.shape[:2]
            rh, rw = rendered.shape[:2]
            assert abs(rw / rh - pw / ph) < 0.02, f"Page {index + 1} has the wrong dimensions"
            assert np.all(rendered == rendered[:, :, :1]), "Expected grayscale output"
            compared = cv2.resize(rendered, (pw, ph), interpolation=cv2.INTER_AREA)
            mean_difference = cv2.absdiff(compared, preview).mean()
            assert mean_difference < 4, f"Page {index + 1} differs from preview by {mean_difference:.2f}/255"
            bitmap.close()
            page.close()


if __name__ == "__main__":
    compare_previews(sys.argv[1], sys.argv[2:])
