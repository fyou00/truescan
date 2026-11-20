"""Generate reproducible document photographs and their rectified references in memory."""

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np


@dataclass
class Scene:
    name: str
    reference: np.ndarray
    photo: np.ndarray
    corners: np.ndarray
    transcript: str
    limitation: str | None


def make_scenes():
    """Yield four baseline photographs followed by four known-limitation cases."""
    front = [(180, 65), (779, 65), (779, 784), (180, 784)]
    left = [(148, 142), (697, 48), (825, 696), (253, 807)]
    right = [(223, 53), (816, 161), (704, 797), (127, 698)]
    skew = [(243, 120), (732, 76), (815, 792), (132, 723)]
    # name, projected corners, desk texture, illumination, known limitation
    cases = [
        ("flat-dark", front, "charcoal", "uniform", None),
        ("angled-side", left, "wood", "side", None),
        ("angled-shadow", right, "blue", "patch", None),
        ("keystone-grain", skew, "wood", "patch", None),
        ("curved-sheet", front, "charcoal", "uniform", "Curved paper"),
        ("matching-paper", left, "paper", "uniform", "Background matches paper"),
        ("underexposure", skew, "charcoal", "dark", "Extreme underexposure"),
        ("glare", right, "blue", "glare", "Clipped specular glare"),
    ]
    yy, xx = np.indices((850, 960), dtype=np.float32)
    for index, (name, outline, desk, light, limitation) in enumerate(cases):
        rng = np.random.default_rng(1701 + index)
        page = np.full((720, 600, 3), 243, np.uint8)
        lines = (
            "DOCUMENT CHECK", f"PAGE {index + 1:02d}",
            "PAPER AND INK", "SCAN SAMPLE", "READ EACH LINE", "END OF PAGE",
        )
        for row, line in enumerate(lines):
            ink = (104, 66, 29) if row == 0 else (38, 38, 38)
            cv2.putText(page, line, (45, 105 + 94 * row), cv2.FONT_HERSHEY_SIMPLEX,
                        1.45, ink, 2, cv2.LINE_AA)

        if desk == "wood":
            grain = 8 * np.sin(yy / 9 + 0.5 * np.sin(xx / 50))
            background = np.array([65, 95, 132]) + grain[..., None]
        else:
            colors = {"charcoal": (55, 56, 60), "blue": (135, 99, 68), "paper": (243,) * 3}
            background = np.broadcast_to(colors[desk], (850, 960, 3))
        photo = np.ascontiguousarray(background, dtype=np.uint8)
        corners = np.float32(outline)
        plane = np.float32([[0, 0], [599, 0], [599, 719], [0, 719]])
        cv2.warpPerspective(page, cv2.getPerspectiveTransform(plane, corners), (960, 850),
                            dst=photo, borderMode=cv2.BORDER_TRANSPARENT)
        if name == "curved-sheet":
            # Bow the text and the top/bottom edges while leaving all four vertices fixed.
            displacement = 46 * np.sin(np.pi * np.clip((xx - 180) / 599, 0, 1))
            photo = cv2.remap(photo, xx, yy - displacement, cv2.INTER_LINEAR,
                              borderMode=cv2.BORDER_REPLICATE)
        illumination = 1.0
        if light == "side":
            illumination = 0.55 + 0.45 * xx / 959
        elif light == "patch":
            illumination = 1 - 0.48 * np.exp(-((xx - 460) / 210)**2 - ((yy - 340) / 250)**2)
        elif light == "dark":
            illumination = 0.035 + 0.09 * xx / 959
        elif light == "glare":
            illumination = 0.9
        exposed = photo * np.asarray(illumination)[..., None]
        if light == "glare":
            flare = 350 * np.exp(-((xx - 455) / 185)**2 - ((yy - 360) / 225)**2)
            exposed += flare[..., None]
        noise = rng.normal(0, 2 if light == "dark" else 0.9, size=xx.shape)
        photo = np.rint(exposed + noise[..., None]).clip(0, 255).astype(np.uint8)
        yield Scene(name, page, photo, corners, "\n".join(lines), limitation)


def export_dataset(output):
    """Write the lossless photos, references and a manifest with relative paths."""
    output.mkdir(parents=True, exist_ok=True)
    entries = []
    for scene in make_scenes():
        directory = output / scene.name
        directory.mkdir(exist_ok=True)
        for filename, image in (("photo.png", scene.photo), ("reference.png", scene.reference)):
            if not cv2.imwrite(str(directory / filename), image):
                raise OSError(f"Could not write {directory / filename}")
        entries.append({
            "name": scene.name,
            "photo": f"{scene.name}/photo.png",
            "reference": f"{scene.name}/reference.png",
            "corners": scene.corners.tolist(),
            "transcript": scene.transcript,
            "limitation": scene.limitation,
        })
    manifest = output / "manifest.json"
    manifest.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="Destination directory")
    print(export_dataset(parser.parse_args().output))
