# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Generate a sample folder from Pascal VOC 2007.

Produces a Pixano-compatible folder structure with metadata.jsonl files
ready to import with `pixano data import`.

Requirements:
    pip install pillow

Usage:
    python generate_voc_sample.py ./voc_sample --num-samples 50
    python generate_voc_sample.py ./voc_sample --num-samples 100 --splits train validation test

Then import into Pixano:
    pixano data import ./my_data ./voc_sample --name "VOC 2007 Sample"
"""

import argparse
import json
import random
import shutil
import sys
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from PIL import Image


_VOC_MIRROR = "https://github.com/ultralytics/yolov5/releases/download/v1.0/"
_ARCHIVES = {
    "trainval": "VOCtrainval_06-Nov-2007.zip",
    "test": "VOCtest_06-Nov-2007.zip",
}
_CACHE_DIR = Path.home() / ".cache" / "pixano" / "voc2007"

# Map CLI split names to VOC ImageSets filenames
_SPLIT_FILE = {
    "train": "train.txt",
    "validation": "val.txt",
    "test": "test.txt",
}

# Splits that require the trainval archive vs. the test archive
_SPLIT_ARCHIVE = {
    "train": "trainval",
    "validation": "trainval",
    "test": "test",
}


def _download_with_progress(url: str, dest: Path) -> None:
    """Download a file with a simple progress bar."""
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req) as resp:  # noqa: S310
        total = int(resp.headers.get("Content-Length", 0))
        downloaded = 0
        chunk_size = 1 << 20  # 1 MiB

        dest.parent.mkdir(parents=True, exist_ok=True)
        tmp = dest.with_suffix(".partial")
        with open(tmp, "wb") as f:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded += len(chunk)
                if total:
                    pct = downloaded * 100 // total
                    mb_done = downloaded / (1 << 20)
                    mb_total = total / (1 << 20)
                    sys.stdout.write(f"\r  {mb_done:.0f}/{mb_total:.0f} MB ({pct}%)")
                    sys.stdout.flush()
        if total:
            sys.stdout.write("\n")
        tmp.rename(dest)


def _ensure_voc_downloaded(splits: list[str]) -> Path:
    """Download and extract the needed VOC 2007 archives. Return the VOC2007 root."""
    voc_root = _CACHE_DIR / "VOCdevkit" / "VOC2007"

    needed_archives = {_SPLIT_ARCHIVE[s] for s in splits}
    for key in sorted(needed_archives):
        archive_name = _ARCHIVES[key]
        archive_path = _CACHE_DIR / archive_name

        # Skip download if already extracted
        marker = _CACHE_DIR / f".{key}_extracted"
        if marker.exists():
            continue

        # Download if not cached
        if not archive_path.exists():
            url = _VOC_MIRROR + archive_name
            print(f"Downloading {url} ...")
            _download_with_progress(url, archive_path)

        # Extract
        print(f"Extracting {archive_name} ...")
        with zipfile.ZipFile(archive_path, "r") as zf:
            zf.extractall(path=_CACHE_DIR)
        marker.touch()

    if not voc_root.is_dir():
        raise RuntimeError(f"Expected VOC directory not found at {voc_root}")

    return voc_root


def _load_split_ids(voc_root: Path, split: str) -> list[str]:
    """Read image IDs for a split from ImageSets/Main/{split}.txt."""
    split_file = voc_root / "ImageSets" / "Main" / _SPLIT_FILE[split]
    if not split_file.exists():
        raise FileNotFoundError(f"Split file not found: {split_file}")
    return [line.strip() for line in split_file.read_text().splitlines() if line.strip()]


def _parse_annotation(xml_path: Path) -> tuple[int, int, list[dict]]:
    """Parse a VOC annotation XML file.

    Returns:
        (width, height, objects) where each object is a dict with keys
        'category', 'is_difficult', 'bbox' (xmin, ymin, xmax, ymax in pixels).
    """
    tree = ET.parse(xml_path)  # noqa: S314
    root = tree.getroot()

    size = root.find("size")
    width = int(size.findtext("width"))
    height = int(size.findtext("height"))

    objects = []
    for obj in root.iter("object"):
        category = obj.findtext("name")
        is_difficult = obj.findtext("difficult") == "1"
        bndbox = obj.find("bndbox")
        bbox = (
            int(bndbox.findtext("xmin")),
            int(bndbox.findtext("ymin")),
            int(bndbox.findtext("xmax")),
            int(bndbox.findtext("ymax")),
        )
        objects.append({"category": category, "is_difficult": is_difficult, "bbox": bbox})

    return width, height, objects


def export_split(output_dir: Path, split: str, num_samples: int, seed: int, voc_root: Path) -> int:
    """Export a sample of a VOC split to a Pixano-compatible folder.

    Args:
        output_dir: Root output directory (e.g. ./voc_sample).
        split: Split name ("train", "validation", or "test").
        num_samples: Maximum number of images to export for this split.
        seed: Random seed for reproducible sampling.
        voc_root: Path to the extracted VOC2007 directory.

    Returns:
        Number of images actually exported.
    """
    split_dir = output_dir / split
    split_dir.mkdir(parents=True, exist_ok=True)

    image_ids = _load_split_ids(voc_root, split)

    rng = random.Random(seed)
    num_samples = min(num_samples, len(image_ids))
    sampled_ids = sorted(rng.sample(image_ids, num_samples))

    jpeg_dir = voc_root / "JPEGImages"
    anno_dir = voc_root / "Annotations"

    metadata_lines: list[str] = []

    for image_id in sampled_ids:
        filename = f"{image_id}.jpg"
        src_image = jpeg_dir / filename
        dst_image = split_dir / filename

        # Copy image
        shutil.copy2(src_image, dst_image)

        # Parse annotation
        xml_path = anno_dir / f"{image_id}.xml"
        width, height, objects = _parse_annotation(xml_path)

        # If size info is missing in XML, fall back to reading the image
        if width == 0 or height == 0:
            with Image.open(src_image) as img:
                width, height = img.size

        # Convert pixel bboxes to normalized (x, y, w, h)
        bboxes_xywh = []
        categories = []
        difficult_flags = []

        for obj in objects:
            xmin, ymin, xmax, ymax = obj["bbox"]
            x = xmin / width
            y = ymin / height
            w = (xmax - xmin) / width
            h = (ymax - ymin) / height
            bboxes_xywh.append([round(x, 6), round(y, 6), round(w, 6), round(h, 6)])
            categories.append(obj["category"])
            difficult_flags.append(obj["is_difficult"])

        # Build metadata line
        entry: dict = {"image": filename}
        if bboxes_xywh:
            entry["objects"] = {
                "bboxes": bboxes_xywh,
                "category": categories,
                "is_difficult": difficult_flags,
            }
        metadata_lines.append(json.dumps(entry, ensure_ascii=False))

    # Write metadata.jsonl
    metadata_path = split_dir / "metadata.jsonl"
    metadata_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")

    print(f"  {split}: exported {num_samples} images to {split_dir}")
    return num_samples


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Pixano-compatible sample folder from Pascal VOC 2007.",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory for the sample dataset (e.g. ./voc_sample).",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=50,
        help="Number of images to sample per split (default: 50).",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "validation"],
        choices=["train", "validation", "test"],
        help="Splits to export (default: train validation).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling (default: 42).",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    if output_dir.exists():
        parser.error(f"Output directory '{output_dir}' already exists. Remove it or choose another path.")

    # Download / cache VOC 2007 data
    voc_root = _ensure_voc_downloaded(args.splits)

    output_dir.mkdir(parents=True)
    print(f"Generating VOC 2007 sample in {output_dir}")

    total = 0
    for split in args.splits:
        total += export_split(output_dir, split, args.num_samples, args.seed, voc_root)

    print(f"\nDone. {total} images exported.")
    print(f"\nTo import into Pixano:")
    print(f"  pixano data import ./my_data {output_dir} --name \"VOC 2007 Sample\"")


if __name__ == "__main__":
    main()
