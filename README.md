# TrueScan

TrueScan uses Python and OpenCV to detect the four corners of a document. The detector lives in `truescan/corners.py`. Its tests generate synthetic images in `tests/test_corners.py`.

## Setup and tests

Run these commands from the repository root in PowerShell with Python 3.14 and uv installed.

```powershell
uv venv --python 3.14 .venv
uv pip install --python .venv\Scripts\python.exe -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The module can be imported directly. To print the corners of a local image, replace `document.jpg` with your image path.

```powershell
.\.venv\Scripts\python.exe -c "import cv2; from truescan.corners import detectCorners; print(detectCorners(cv2.imread('document.jpg')))"
```

## Detector API

`detectCorners(image)` accepts a grayscale, BGR, or BGRA NumPy array with dtype `uint8`. On success, it returns a `float32` array of shape `(4, 2)`. Each row holds an `(x, y)` coordinate in the original image, ordered clockwise from top left to top right, bottom right, and bottom left. The order follows the displayed image regardless of text orientation.

The detector limits the longest side to 800 pixels and applies Gaussian blur, Canny edge detection, and morphological closing. It selects the largest external contour that covers at least 5% of the image area and can be approximated by a convex quadrilateral. A return value of `None` signals that the caller should request manual corner selection.

## Initial evaluation

The tests cover a straight document, a perspective-skewed document in an 1801 × 1133 image, and paper with no visible boundary against a matching background. On the skewed fixture, the maximum corner error was 2.65 pixels. Median local detection time was 6.7 ms over 20 runs after warm-up.

A larger four-sided object can be mistaken for the document. Curled or folded paper and glare can also distort the detected outline.
