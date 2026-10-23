# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Prepare the two datasets of the step 1 demo, on any machine.

The demo depends on no sample library: the images are generated here, deterministically, then
imported through the Pixano CLI — the path a user would take. Two datasets, one for each part of
the demo:

- **Demo shapes**: 400 images embedded in LanceDB (`embed` mode, the one of a default import).
  On a CPU inference, computing their embeddings takes two to three minutes: enough to watch the
  progress, cancel, and kill the worker mid-work.
- **Demo damaged images**: 60 images referenced by path (`uri` mode), two of them corrupted and
  one deleted after the import. This is where the quarantine shows.

Replayable: each run overwrites both datasets and regenerates the same images.

Usage:
    uv run --directory packages/pixano-worker python scripts/prepare_demo.py

By default, the datasets go to `data/` at the repository root — the values of `.env.example`.
The default paths are computed from the location of this script and not from the current
directory, which `uv run --directory` moves.
"""

import argparse
import json
import random
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image, ImageDraw


SHAPES_NAME = "Demo shapes"
SHAPES_COUNT = 400

DEFECTS_NAME = "Demo damaged images"
DEFECTS_COUNT = 60
DEFECTS_FOLDER = "demo_defects"
# What the demo announces: two unreadable images and one missing, hence 57 vectors out of 60.
CORRUPTED = (10, 11)
DELETED = 40

IMAGE_SIZE = 224
# The seeds pin the images: two preparations give the same dataset, and the demo announces the
# same numbers for everyone.
SHAPES_SEED = 2026
DEFECTS_SEED = 1789

REPO_ROOT = Path(__file__).resolve().parents[3]

# The path under which the worker sees the media folder — in the compose, the volume mounted
# at /medias. The images of the by-path dataset are referenced under this root: it is the
# worker's PIXANO_MEDIA_ROOT, wherever it is launched from.
COMPOSE_MEDIA_ROOT = "/medias"


def draw_images(target: Path, count: int, seed: int) -> list[Path]:
    """Draw coloured shapes, different from one image to the next.

    Shapes rather than noise: a model like CLIP derives distinct vectors from them, which makes
    the result verifiable, and they weigh a few kilobytes.
    """
    rng = random.Random(seed)
    target.mkdir(parents=True, exist_ok=True)
    paths = []
    for index in range(count):
        background = tuple(rng.randint(180, 255) for _ in range(3))
        image = Image.new("RGB", (IMAGE_SIZE, IMAGE_SIZE), background)
        pen = ImageDraw.Draw(image)
        for _ in range(rng.randint(1, 4)):
            colour = tuple(rng.randint(0, 200) for _ in range(3))
            x0, y0 = rng.randint(0, IMAGE_SIZE - 60), rng.randint(0, IMAGE_SIZE - 60)
            x1, y1 = x0 + rng.randint(30, 150), y0 + rng.randint(30, 150)
            shape = rng.choice(("ellipse", "rectangle", "triangle"))
            if shape == "ellipse":
                pen.ellipse((x0, y0, x1, y1), fill=colour)
            elif shape == "rectangle":
                pen.rectangle((x0, y0, x1, y1), fill=colour)
            else:
                pen.polygon([(x0, y1), ((x0 + x1) // 2, y0), (x1, y1)], fill=colour)
        path = target / f"forme-{index:04d}.jpg"
        image.save(path, quality=90)
        paths.append(path)
    return paths


def pixano_import(data_dir: Path, source: Path, extra: list[str]) -> str:
    """Import through the Pixano CLI, as a user would.

    Returns:
        The last line of the CLI, which names the created dataset.
    """
    cli = Path(sys.executable).parent / "pixano"
    command = [str(cli), "data", "import", str(data_dir), str(source), "--workspace", "image", "--yes", *extra]
    completed = subprocess.run(command, capture_output=True, text=True)
    if completed.returncode != 0:
        raise SystemExit(f"the import failed:\n{completed.stdout}\n{completed.stderr}")
    lines = [line for line in completed.stdout.splitlines() if "imported successfully" in line]
    return lines[-1] if lines else completed.stdout.strip().splitlines()[-1]


def remove_previous(data_dir: Path, name: str) -> None:
    """Remove a demo dataset that is already present.

    Rather than the import's `overwrite` mode: starting again from an empty folder guarantees
    that no table left by a previous demo — the embeddings, above all — survives the preparation.
    Only the datasets that bear exactly the demo's name are touched.
    """
    library = data_dir / "library"
    if not library.is_dir():
        return
    for info_path in library.glob("*/info.json"):
        if json.loads(info_path.read_text()).get("name") == name:
            shutil.rmtree(info_path.parent)


def dataset_id(data_dir: Path, name: str) -> str:
    """The identifier of the dataset bearing this name, to find it again in the API and the logs."""
    for info_path in (data_dir / "library").glob("*/info.json"):
        info = json.loads(info_path.read_text())
        if info.get("name") == name:
            return info["id"]
    raise SystemExit(f"dataset not found after import: {name}")


def prepare_shapes(data_dir: Path) -> str:
    """Generate and import the embedded dataset; return its identifier."""
    remove_previous(data_dir, SHAPES_NAME)
    with tempfile.TemporaryDirectory() as scratch:
        source = Path(scratch)
        draw_images(source, SHAPES_COUNT, SHAPES_SEED)
        pixano_import(data_dir, source, ["--name", SHAPES_NAME, "--media", "embed"])
    return dataset_id(data_dir, SHAPES_NAME)


def prepare_defects(data_dir: Path, media_dir: Path, media_root: str) -> str:
    """Generate, import by path, then damage the quarantine dataset; return its identifier.

    Args:
        data_dir: The dataset library.
        media_dir: Where to write the images, as this machine sees it.
        media_root: The same folder, as the worker will see it: the prefix of the imported paths.
    """
    remove_previous(data_dir, DEFECTS_NAME)
    folder = media_dir / DEFECTS_FOLDER
    shutil.rmtree(folder, ignore_errors=True)
    paths = draw_images(folder, DEFECTS_COUNT, DEFECTS_SEED)

    with tempfile.TemporaryDirectory() as scratch:
        spec = Path(scratch) / "dataset.yaml"
        spec.write_text(
            "pixano: 2\n"
            "dataset:\n"
            f'  name: "{DEFECTS_NAME}"\n'
            "  workspace: image\n"
            "format: pixano_jsonl\n"
            "media:\n"
            "  mode: uri\n"
            f"  uri_prefix: {media_root}/{DEFECTS_FOLDER}\n"
        )
        pixano_import(data_dir, folder, ["--spec", str(spec), "--media", "uri"])

    # Damaged after the import. In `uri` mode, the import does not read the images today — it
    # references them without knowing their size — but the demo wants the defect to be met by
    # the embeddings computation, not by an import that would one day start validating them.
    for index in CORRUPTED:
        paths[index].write_bytes(b"this is not an image " * 100)
    paths[DELETED].unlink()
    return dataset_id(data_dir, DEFECTS_NAME)


def main() -> None:
    """Prepare the two datasets and say what to do next."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--data-dir", type=Path, default=REPO_ROOT / "data", help="The compose's PIXANO_DATA_DIR.")
    parser.add_argument(
        "--media-dir", type=Path, default=REPO_ROOT / "data" / "media", help="The compose's PIXANO_MEDIA_DIR."
    )
    parser.add_argument(
        "--media-root",
        default=COMPOSE_MEDIA_ROOT,
        help="The media folder as the worker sees it, that is, its PIXANO_MEDIA_ROOT. "
        "By default the compose's mount; for a worker launched by hand, give --media-dir itself.",
    )
    args = parser.parse_args()

    data_dir, media_dir = args.data_dir.resolve(), args.media_dir.resolve()
    (data_dir / "library").mkdir(parents=True, exist_ok=True)

    print(f"library: {data_dir / 'library'}", flush=True)
    print(f"'{SHAPES_NAME}': {SHAPES_COUNT} embedded images...", flush=True)
    shapes = prepare_shapes(data_dir)
    print(f"'{DEFECTS_NAME}': {DEFECTS_COUNT} images by path, 3 of them damaged...", flush=True)
    defects = prepare_defects(data_dir, media_dir, args.media_root)

    print(f"ready — '{SHAPES_NAME}' ({shapes}) and '{DEFECTS_NAME}' ({defects}).")


if __name__ == "__main__":
    main()
