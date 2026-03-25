# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

r"""Generate a Pixano-compatible dataset from a folder of unannotated images.

This script creates `train/` (empty) and `val/` (populated) splits and
metadata.jsonl files ready for Pixano import.

Expected folder structure::

    output_root/
    ├── train/
    │   └── metadata.jsonl # optional/empty
    └── val/
        ├── <image_name_0>.jpg
        ├── <image_name_1>.jpg
        └── metadata.jsonl

Usage:
    python generate_sample.py --input_folder ./images --output ./sample_images

Then import into Pixano:
    pixano data import ./my_data ./sample_images --info examples/unlabeled_images_folder/info.py:dataset_info
"""

import argparse
import json
import shutil
from pathlib import Path


def generate_image_dataset(input_folder: Path, output_root: Path):
    """Copy images into a Pixano-compatible folder and generate metadata."""
    # Define train/val directories
    train_images = output_root / "train"
    val_images = output_root / "val"

    for d in [train_images, val_images]:
        d.mkdir(parents=True, exist_ok=True)

    metadata_lines = []
    image_extensions = [".jpg", ".jpeg", ".png", ".bmp", ".tif"]

    for img_path in sorted(input_folder.iterdir()):
        if img_path.suffix.lower() not in image_extensions:
            continue
        dst_path = val_images / img_path.name
        shutil.copy2(img_path, dst_path)

        # Add metadata entry (no masks/entities)
        entry = {"status": "unlabeled", "views": {"image": img_path.name}}
        metadata_lines.append(json.dumps(entry, ensure_ascii=False))

    # Write metadata.jsonl
    metadata_path = output_root / "val" / "metadata.jsonl"
    metadata_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")
    print(f"Metadata saved to {metadata_path}")
    print(f"Dataset generation complete ({len(metadata_lines)} images).")


def main():
    """Generate a Pixano-compatible sample folder from a folder of images."""
    parser = argparse.ArgumentParser(
        description="Generate a Pixano-compatible dataset from a folder of unannotated images."
    )
    parser.add_argument("--input_folder", required=True, type=Path, help="Folder containing image files to process.")
    parser.add_argument("--output", required=True, type=Path, help="Root output directory for the dataset.")
    args = parser.parse_args()

    if not args.input_folder.is_dir():
        parser.error(f"Input folder '{args.input_folder}' does not exist.")
    if args.output.exists():
        parser.error(f"Output directory '{args.output}' already exists. Remove it or choose another path.")

    args.output.mkdir(parents=True, exist_ok=True)
    generate_image_dataset(args.input_folder, args.output)


if __name__ == "__main__":
    main()
