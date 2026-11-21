# TrueScan

TrueScan uses Python and OpenCV to detect document corners, rectify a page from an original-resolution photo, enhance the rectified page, generate a black-and-white version, and export one or more pages as a PDF.

## Scan pages and download a PDF

Run these commands from the repository root on macOS or Linux. The local Python server serves the browser app and runs OpenCV in memory. The web assets require no build step.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-test.txt
.venv/bin/python -m truescan.server --port 8000
```

Open [the local scanner](http://127.0.0.1:8000/). Choose **Buka kamera** and **Ambil foto**, or **Impor foto** to open a JPEG, PNG, or WebP. Import also works when camera permission is denied. Camera access requires localhost or HTTPS. The browser displays the current photo in its display orientation. The scanner outlines the detected page for review. Drag a corner to adjust it. If detection finds no outline, select the top left, top right, bottom right, and bottom left in order. Confirm the outline to view the straightened page. You can return to the original to adjust it again. Choose **Tambah ke dokumen** to include the corrected page. Repeat for the remaining pages. In the document list, move pages into reading order or choose **Hapus** on a page to remove it before export. Choose **Putar 90°** on a page to turn it clockwise, then select color, grayscale, or black-and-white. The thumbnails show the selected export mode. Choose **Unduh PDF** to save the assembled document. Pages stay in memory until you reload or close the tab.

To install and run the browser tests from the repository root after installing the Python dependencies above, with Node.js 20 or newer and npm:

```sh
npm ci
npx playwright install chromium
npm test
```

Chrome 157 with a Pixel 7 emulation profile passed the permission-denial, rotated JPEG import, capture, and camera-release tests using a simulated camera. Mobile Safari 18.6 on an iPhone 16 simulator independently displayed an EXIF-rotated JPEG at the expected dimensions and orientation. Physical camera hardware remains untested. [Mobile screenshot with a synthetic page](docs/screenshots/capture-mobile.png)

The corner editor was tested with Chromium in Pixel 7 emulation for manual selection, touch dragging, and re-editing. Mobile Safari 18.6 on an iPhone 16 simulator also detected and rectified a synthetic page to 480 × 320 pixels with its orientation marker intact. [Corner editor screenshot](docs/screenshots/corners-mobile.png)

The multi-page download was tested in Chromium with Pixel 7 emulation. Two synthetic pages were reordered and exported in grayscale, then rendered with PDFium and compared to the displayed previews. A second test verifies that retrying a failed preview makes the page available for download. [Document list screenshot](docs/screenshots/document-mobile.png)

A document can contain up to 100 pages, 128 megapixels in total, and 256 MiB of input PNG data including frame headers.

## Python setup and tests

Run these commands from the repository root in PowerShell with Python 3.14 and uv installed.

```powershell
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements-test.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Start the local scanner from PowerShell with `.\.venv\Scripts\python.exe -m truescan.server --port 8000`.

The module can be imported directly. To print the corners of a local image, replace `document.jpg` with your image path.

```powershell
.\.venv\Scripts\python.exe -c "import cv2; from truescan.corners import detectCorners; print(detectCorners(cv2.imread('document.jpg')))"
```

## Detector API

`detectCorners(image)` accepts a grayscale, BGR, or BGRA NumPy array with dtype `uint8`. On success, it returns a `float32` array of shape `(4, 2)`. Each row holds an `(x, y)` coordinate in the original image, ordered clockwise from top left to top right, bottom right, and bottom left. The order follows the displayed image regardless of text orientation.

The detector limits the longest side to 800 pixels and applies Gaussian blur, Canny edge detection, and morphological closing. It selects the largest external contour that covers at least 5% of the image area and can be approximated by a convex quadrilateral. A return value of `None` signals that the caller should request manual corner selection.

## Perspective correction

Pass the original image and its four detected or manually selected corners to `correctPerspective`. Supply pixel coordinates clockwise from the top left. The function estimates output width and height from the longer edge of each opposing pair. It preserves grayscale, BGR, or BGRA channels and raises `ValueError` for invalid geometry.

```python
from truescan.corners import detectCorners
from truescan.perspective import correctPerspective

corners = detectCorners(image)
if corners is None:
    raise ValueError("Select four corners on the original image to continue")
page = correctPerspective(image, corners)
```

On the synthetic 1801 × 1133 photo in `tests/test_perspective.py`, an axis-aligned crop of the detected outline leaves the four colored marker centers displaced from their reference positions. The largest error falls from 0.1382 after cropping to 0.0028 after rectification. Error is Euclidean distance after normalizing x and y by the respective pixel spans of each output. The rectified page measures 1170 × 797 pixels in this run.

## Page enhancement

Pass the rectified page to `enhancePage` to reduce shadows and improve local contrast and sharpness. The output keeps the page dimensions and its grayscale, BGR, or BGRA format, including the original alpha channel.

```python
from truescan.enhance import enhancePage

enhanced = enhancePage(page)
```

See the [synthetic before-and-after evaluation](docs/ENHANCEMENT.md) for results and reproduction instructions.

## Black-and-white pages

Pass the enhanced page to `binarizePage` for a single-channel image at the original page dimensions. The default adaptive Gaussian threshold compares each pixel to its neighborhood. Select Otsu to use one threshold across the page. Both modes return black (0) or white (255) pixels.

```python
from truescan.binarize import binarizePage

black_and_white = binarizePage(enhanced)
otsu_comparison = binarizePage(enhanced, method="otsu")
```

See the [binarization evaluation](docs/BINARIZATION.md) for a comparison on synthetic pages.

## PDF export

Pass an ordered sequence of processed pages to `exportPdf`. Each page keeps its pixel dimensions and aspect ratio, with a physical page size calculated at 300 dpi. Select `color` (the default), `grayscale`, or `black-and-white` for the entire document. The function returns PDF bytes, ready to save locally.

```python
from pathlib import Path
from truescan.pdf import exportPdf

Path("scan.pdf").write_bytes(exportPdf([enhanced], mode="color"))
```

The order of the input pages sets the reading order. See the [PDF export verification](docs/PDF_EXPORT.md) for the multi-page checks.

## End-to-end evaluation

The [evaluation report](docs/EVALUATION.md) compares synthetic input photos with pages rendered from the exported PDF. It includes image quality, local OCR accuracy, timing, and the cases that required manual corner selection. The [dataset guide](evaluation/dataset/README.md) describes the scenes and how to regenerate them.

## Initial evaluation

The tests cover a straight document, a perspective-skewed document in an 1801 × 1133 image, and paper with no visible boundary against a matching background. On the skewed fixture, the maximum corner error was 2.65 pixels. Median local detection time was 6.7 ms over 20 runs after warm-up.

A larger four-sided object can be mistaken for the document. Curled or folded paper and glare can also distort the detected outline.
