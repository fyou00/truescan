# TrueScan

TrueScan uses Python and OpenCV to detect document corners and rectify a page from an original-resolution photo.

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

## Initial evaluation

The tests cover a straight document, a perspective-skewed document in an 1801 × 1133 image, and paper with no visible boundary against a matching background. On the skewed fixture, the maximum corner error was 2.65 pixels. Median local detection time was 6.7 ms over 20 runs after warm-up.

A larger four-sided object can be mistaken for the document. Curled or folded paper and glare can also distort the detected outline.
