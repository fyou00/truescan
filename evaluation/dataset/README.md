# Synthetic evaluation dataset

The dataset is generated in memory by `evaluation.dataset.make_scenes()`. Run this command in the project environment to list the scenes, capture sizes and labels.

```sh
python -c "from evaluation.dataset import make_scenes; print([(s.name, s.photo.shape, s.limitation) for s in make_scenes()])"
```

To inspect the images and labels directly, run this from the repository root.

```sh
python -m evaluation.dataset --output evaluation/dataset/generated
```

Each scene gets a subdirectory under `evaluation/dataset/generated/` with `photo.png` and `reference.png`. The ordered `manifest.json` lists their relative paths, pixel coordinates, transcript and limitation label. Running the command again regenerates the same files.

Each scene contains one 960 × 850 BGR photograph, a clean 600 × 720 BGR reference page, its six-line English transcript, and four ground-truth pixel coordinates in the photograph. Corners are ordered top left, top right, bottom right, bottom left. The same document layout is used throughout, with a distinct printed page number in each scene. OpenCV draws all text and projects the page. A per-scene NumPy random seed fixes the noise realization.

| Scene | Capture condition |
| --- | --- |
| `flat-dark` | Front-facing page, charcoal surface and uniform lighting. |
| `angled-side` | Oblique page, wood-grain surface and a left-to-right illumination gradient. |
| `angled-shadow` | Opposite page tilt, blue surface and a broad local shadow. |
| `keystone-grain` | Trapezoidal perspective, wood grain and a broad local shadow. |
| `curved-sheet` | A 46-pixel bow displaces both page edges and printed lines. Corner labels remain at their projected positions. This exercises the limitation of planar correction on curved or folded paper. |
| `matching-paper` | Paper and background have equal base intensity. The text remains visible while the boundary disappears. |
| `underexposure` | Spatially varying exposure of 3.5–12.5% with additive noise compromises ink and boundary contrast. |
| `glare` | A bright elliptical reflection clips the paper and some printed strokes. |

The first four scenes exercise normal planar scanning. The final four have a nonempty `limitation` label. Ground-truth corners are available for measuring geometric error and simulating a human selection. The dataset contains one typeface and a single page layout. Scores describe this controlled fixture set.
