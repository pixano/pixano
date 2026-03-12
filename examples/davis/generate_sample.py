# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

r"""Generate a sample folder from DAVIS 2017 video object segmentation dataset.

Produces a Pixano-compatible folder structure with metadata.jsonl files
ready to import with `pixano data import`.

Usage:
    python examples/davis/generate_sample.py ./davis_sample /path/to/DAVIS --num-samples 5
    python examples/davis/generate_sample.py ./davis_sample /path/to/DAVIS --splits train val

Then import into Pixano:
    pixano data import ./my_data ./davis_sample \
        --info examples/davis/info.py:dataset_info
"""

import argparse
import json
import random
import shutil
from pathlib import Path


def _load_split_video_names(davis_root: Path, split: str) -> list[str]:
    """Read video names for a split from ImageSets/2017/{split}.txt."""
    split_file = davis_root / "ImageSets" / "2017" / f"{split}.txt"
    if not split_file.exists():
        raise FileNotFoundError(f"Split file not found: {split_file}")
    return [line.strip() for line in split_file.read_text().splitlines() if line.strip()]


def export_split(output_dir: Path, split: str, num_samples: int, seed: int, davis_root: Path) -> int:
    """Export a sample of a DAVIS split to a Pixano-compatible folder.

    Args:
        output_dir: Root output directory (e.g. ./davis_sample).
        split: Split name ("train" or "val").
        num_samples: Maximum number of videos to export for this split.
        seed: Random seed for reproducible sampling.
        davis_root: Path to the DAVIS dataset root.

    Returns:
        Number of videos actually exported.
    """
    split_dir = output_dir / split
    split_dir.mkdir(parents=True, exist_ok=True)

    video_names = _load_split_video_names(davis_root, split)

    rng = random.Random(seed)
    num_samples = min(num_samples, len(video_names))
    sampled_videos = sorted(rng.sample(video_names, num_samples))

    jpeg_dir = davis_root / "JPEGImages" / "Full-Resolution"
    anno_dir = davis_root / "Annotations" / "Full-Resolution"

    metadata_lines: list[str] = []

    for video_name in sampled_videos:
        # Copy frame JPEGs
        src_frames = jpeg_dir / video_name
        dst_frames = split_dir / "frames" / video_name
        dst_frames.mkdir(parents=True, exist_ok=True)
        for frame_file in sorted(src_frames.glob("*.jpg")):
            shutil.copy2(frame_file, dst_frames / frame_file.name)

        # Copy mask PNGs
        src_masks = anno_dir / video_name
        dst_masks = split_dir / "masks" / video_name
        dst_masks.mkdir(parents=True, exist_ok=True)
        for mask_file in sorted(src_masks.glob("*.png")):
            shutil.copy2(mask_file, dst_masks / mask_file.name)

        # Build metadata entry with glob patterns
        entry = {
            "views": {
                "image": {"path": f"frames/{video_name}/*.jpg", "fps": 24},
            },
            "annotation_files": {
                "mask": f"masks/{video_name}/*.png",
            },
        }
        metadata_lines.append(json.dumps(entry, ensure_ascii=False))

    # Write metadata.jsonl
    metadata_path = split_dir / "metadata.jsonl"
    metadata_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")

    print(f"  {split}: exported {num_samples} videos to {split_dir}")
    return num_samples


def main():
    """Generate a Pixano-compatible sample folder from DAVIS 2017."""
    parser = argparse.ArgumentParser(
        description="Generate a Pixano-compatible sample folder from DAVIS 2017.",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory for the sample dataset (e.g. ./davis_sample).",
    )
    parser.add_argument(
        "davis_root",
        type=Path,
        help="Path to the DAVIS dataset root (containing JPEGImages/, Annotations/, ImageSets/).",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=5,
        help="Number of videos to sample per split (default: 5).",
    )
    parser.add_argument(
        "--splits",
        nargs="+",
        default=["train", "val"],
        choices=["train", "val"],
        help="Splits to export (default: train val).",
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

    davis_root: Path = args.davis_root
    if not davis_root.is_dir():
        parser.error(f"DAVIS root directory '{davis_root}' does not exist.")

    output_dir.mkdir(parents=True)
    print(f"Generating DAVIS 2017 sample in {output_dir}")

    total = 0
    for split in args.splits:
        total += export_split(output_dir, split, args.num_samples, args.seed, davis_root)

    print(f"\nDone. {total} videos exported.")
    print("\nTo import into Pixano:")
    print(f"  pixano dataset import ./my_data {output_dir} \\")
    print("      --info examples/davis/info.py:dataset_info")


if __name__ == "__main__":
    main()
