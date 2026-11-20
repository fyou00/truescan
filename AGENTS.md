# Repository Guidelines

TrueScan is a web-based document scanner. Its workflow is to capture a page with a camera or import a photo, correct it, and export the document as a PDF.

## Architecture

Image processing runs in Python with OpenCV. Keep reusable image-processing and PDF-export code separate from browser interactions such as camera permissions and file selection.

## Processing pipeline

Implement each stage as its own function so it can be tested in isolation:

1. Preprocess: resize for detection, grayscale, Gaussian blur.
2. Detect document edges: Canny, morphology, largest contour, `approxPolyDP` to four corners, ordered top-left, top-right, bottom-right, bottom-left.
3. Correct perspective: compute the homography from the downscaled image, scale the corners back, and warp the original-resolution image.
4. Enhance: background estimation to remove shadows, CLAHE, unsharp mask.
5. Binarize: adaptive threshold as default, Otsu kept as a comparison method.
6. Export: color, grayscale, and black-and-white modes; multi-page PDF.

If corner detection fails, fall back to manual corner selection. Never return a silently wrong result.

Machine learning (for example learned edge detection or OCR) is allowed where it helps, but it must be optional and the classical method must remain as the baseline.

## Development commands

Run `git status --short` to inspect changes and `git diff --cached --check` after staging. The repository has no build, development server, or test scripts yet. When introducing the toolchain, include the exact install, start, build, and test commands in the same change.

## Coding style and tests

Use names that describe scanner behavior, such as `capturePage`, `detectCorners`, or `exportPdf`. Choose formatting conventions with the first implementation and record them in the formatter configuration.

Use synthetic document images as fixtures. Cover camera permission denial, importing a rotated photo, failed corner detection with manual fallback, and exporting multiple pages in the selected order. For camera or layout changes, exercise the flow in a mobile browser and record which one you used.

## Evaluation

Keep the evaluation dataset under a documented path with varied lighting, backgrounds, and angles. Report PSNR/SSIM, OCR accuracy, and processing time. Any change to pipeline parameters or methods must include a before/after comparison.

## Known limitations

Do not work around these with ad hoc fixes: curved or folded paper, backgrounds that match the paper color, extreme lighting or glare. Document them in the report instead.

## Privacy

Never commit real user documents or send images to external services. Use synthetic or personal-data-free samples in tests and screenshots.

## Commits and pull requests

Use short imperative subjects such as `Add photo import`. In pull requests, describe the user-visible change and how you verified it. Link a related issue when available. For interface changes, include a screenshot using a sample document free of personal information.
