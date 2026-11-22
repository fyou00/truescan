"""Check PDF sheet size, aspect-fit image placement and colored corner registration."""

import json
import sys

import cv2
import numpy as np
import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c


def verify(original_file, a4_file, source_sizes):
    with pdfium.PdfDocument(original_file) as original, pdfium.PdfDocument(a4_file) as a4:
        assert len(a4) == len(original) == 2
        for index, (width, height) in enumerate(source_sizes):
            native, sheet = original[index], a4[index]
            np.testing.assert_allclose(np.array(native.get_size()) * 300 / 72, [width, height], atol=0.1)
            paper = np.array(sheet.get_size())
            expected_mm = [210, 297] if height > width else [297, 210]
            np.testing.assert_allclose(paper * 25.4 / 72, expected_mm, atol=0.02)

            printable = paper - 2 * (10 * 72 / 25.4)  # 10 mm on each edge.
            image_size = np.array([width, height]) * min(printable[0] / width, printable[1] / height)
            minimum = (paper - image_size) / 2
            maximum = minimum + image_size
            image, = sheet.get_objects(filter=[pdfium_c.FPDF_PAGEOBJ_IMAGE])
            np.testing.assert_allclose(image.get_bounds(), [*minimum, *maximum], atol=0.03)

            native_bitmap = native.render(scale=300 / 72)
            sheet_bitmap = sheet.render(scale=1)
            reference = native_bitmap.to_numpy()[:, :, :3]
            rendered = sheet_bitmap.to_numpy()[:, :, :3]
            x1, y1 = np.rint(minimum).astype(int)
            x2, y2 = np.rint(maximum).astype(int)
            restored = cv2.resize(rendered[y1:y2, x1:x2], (width, height), interpolation=cv2.INTER_AREA)
            reference = cv2.resize(reference, (width, height), interpolation=cv2.INTER_AREA)
            # The marks sit 11 source pixels in from each corner; rectification may shift them slightly.
            for x, y, strong_channels in (
                (11, 11, (2,)), (width - 11, 11, (1,)),
                (width - 11, height - 11, (0,)), (11, height - 11, (0, 2)),
            ):
                expected = reference[y, x].astype(int)
                background = [c for c in range(3) if c not in strong_channels]
                assert expected[list(strong_channels)].min() > expected[background].max() + 60
                np.testing.assert_allclose(restored[y, x], expected, atol=6)
            assert cv2.absdiff(restored, reference).mean() < 4, "A4 output differs from the original scan"
            native_bitmap.close()
            sheet_bitmap.close()
            native.close()
            sheet.close()


if __name__ == "__main__":
    verify(sys.argv[1], sys.argv[2], json.loads(sys.argv[3]))
