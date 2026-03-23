# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

r"""Generate a Pixano-compatible sample folder from all videos in a folder.

This script extracts frames from input videos and organizes them into
a folder structure with `train/` (empty) and `val/` (populated) splits.
video is represented as a sequence of images, and metadata is stored
in `metadata.jsonl` for import into Pixano.

Expected output folder structure::

    output_root/
    ├── train/
    │   ├── frames/        # empty
    │   └── metadata.jsonl # optional/empty
    └── val/
        ├── frames/
        │   └── <video_name>/
        │       ├── 00000.jpg
        │       └── ...
        └── metadata.jsonl

Usage:
    python generate_sample.py --input_folder ./videos --output ./sample_videos

Then import into Pixano:
    pixano data import ./my_data ./sample_videos --info examples/unlabeled_videos_folder/info.py:dataset_info
"""

import argparse
import json
from pathlib import Path

import cv2


def extract_frames(video_path: Path, output_dir: Path) -> int:
    """Extract frames from a video and save them as sequential JPG images.

    Args:
        video_path: Path to the input video.
        output_dir: Directory to save extracted frames.

    Returns:
        Frames per second (FPS) of the video.
    """
    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 24  # fallback to 24 if undetected
    output_dir.mkdir(parents=True, exist_ok=True)

    frame_idx = 0
    while True:
        ret, frame = cap.read()
        if not ret:
            break
        frame_path = output_dir / f"{frame_idx:05d}.jpg"
        cv2.imwrite(str(frame_path), frame)
        frame_idx += 1

    cap.release()
    return round(fps)


def generate_dataset_from_folder(input_folder: Path, output_root: Path):
    """Generate folder structure and metadata from all videos in a folder.

    Args:
        input_folder: Folder containing video files.
        output_root: Root directory for the output dataset.
    """
    # Collect all video files (common extensions)
    video_extensions = [".mp4", ".mov", ".avi", ".mkv"]
    video_paths = [p for p in sorted(input_folder.iterdir()) if p.suffix.lower() in video_extensions]

    if not video_paths:
        print(f"No video files found in {input_folder}")
        return

    # Define train and validation directories
    train_frames = output_root / "train" / "frames"
    val_frames = output_root / "val" / "frames"

    # Create folders
    for d in [train_frames, val_frames]:
        d.mkdir(parents=True, exist_ok=True)

    metadata_path = output_root / "val" / "metadata.jsonl"
    metadata_lines = []

    for video_path in video_paths:
        video_name = video_path.stem
        print(f"Processing video: {video_name}")

        # Extract frames into val/frames/<video_name>/
        frame_dir = val_frames / video_name
        fps = extract_frames(video_path, frame_dir)

        # Build metadata entry (no masks/annotations)
        entry = {
            "status": "unlabeled",
            "views": {
                "image": {
                    "path": f"frames/{video_name}/*.jpg",
                    "fps": fps,
                }
            },
        }
        metadata_lines.append(json.dumps(entry, ensure_ascii=False))

    # Write metadata.jsonl
    metadata_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")
    print(f"\nMetadata saved to {metadata_path}")
    print("Dataset generation complete.")


def main():
    """Generate a Pixano-compatible sample folder from a folder of videos."""
    parser = argparse.ArgumentParser(
        description="Generate a Pixano-compatible sample folder from all videos in a folder."
    )
    parser.add_argument("--input_folder", required=True, type=Path, help="Folder containing video files to process.")
    parser.add_argument(
        "--output", required=True, type=Path, help="Root output directory for the dataset (e.g., ./sample_videos)."
    )
    args = parser.parse_args()

    if not args.input_folder.is_dir():
        parser.error(f"Input folder '{args.input_folder}' does not exist.")

    if args.output.exists():
        parser.error(f"Output directory '{args.output}' already exists. Remove it or choose another path.")

    args.output.mkdir(parents=True, exist_ok=True)
    generate_dataset_from_folder(args.input_folder, args.output)


if __name__ == "__main__":
    main()
