# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

r"""Generate a sample folder from FLIR ADAS v2 (multi-view: RGB + thermal).

Produces a Pixano-compatible folder structure with metadata.jsonl files
ready to import with ``pixano data import``.

FLIR ADAS v2 requires manual download from
https://adas-dataset-v2.flirconservator.com/

This script uses the **video test sets** (``video_rgb_test/`` and
``video_thermal_test/``) which contain 3,749 time-synced frame pairs
documented in ``rgb_to_thermal_vid_map.json``.  The train/val splits do
NOT have reliable RGB↔thermal pairing because their images come from
independent video sequences.

Expected FLIR ADAS v2 directory layout (video test sets)::

    flir_adas_v2/
    ├── rgb_to_thermal_vid_map.json
    ├── video_rgb_test/
    │   ├── coco.json
    │   └── data/
    │       └── video-{vid}-frame-{n}-{hash}.jpg
    └── video_thermal_test/
        ├── coco.json
        └── data/
            └── video-{vid}-frame-{n}-{hash}.jpg

Usage:
    python generate_sample.py ./flir_sample /path/to/flir_adas_v2 --num-samples 50

Then import into Pixano:
    pixano data import ./my_data ./flir_sample \\
        --name "FLIR ADAS Sample" --schema examples/flir/schema.py:FLIRDatasetItem
    pixano data import ./my_data ./flir_sample \\
        --name "FLIR ADAS Sample" --schema examples/flir/schema.py:FLIRDatasetItem --embed-media
"""

import argparse
import json
import random
import re
import shutil
from pathlib import Path


def _load_json(path: Path) -> dict:
    """Load a JSON file."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _build_category_map(coco: dict) -> dict[int, str]:
    """Build a mapping from category id to category name."""
    return {cat["id"]: cat["name"] for cat in coco.get("categories", [])}


def _build_filename_to_image(coco: dict) -> dict[str, dict]:
    """Build a mapping from bare filename (no directory prefix) to image info."""
    return {Path(img["file_name"]).name: img for img in coco.get("images", [])}


def _build_annotations_by_image(coco: dict) -> dict[int, list[dict]]:
    """Group annotations by image_id."""
    annots_by_image: dict[int, list[dict]] = {}
    for ann in coco.get("annotations", []):
        annots_by_image.setdefault(ann["image_id"], []).append(ann)
    return annots_by_image


def export_video_test(
    output_dir: Path,
    flir_root: Path,
    num_samples: int,
    seed: int,
) -> int:
    """Export a sample of video test frame pairs to a Pixano-compatible folder.

    Args:
        output_dir: Root output directory (e.g. ./flir_sample).
        flir_root: Path to the FLIR ADAS v2 root directory.
        num_samples: Maximum number of frame pairs to export.
        seed: Random seed for reproducible sampling.

    Returns:
        Number of frame pairs actually exported.
    """
    # Load the pairing map
    mapping_path = flir_root / "rgb_to_thermal_vid_map.json"
    pair_map: dict[str, str] = _load_json(mapping_path)

    # Load COCO annotations for thermal modality
    thermal_coco = _load_json(flir_root / "video_thermal_test" / "coco.json")

    category_map = _build_category_map(thermal_coco)
    thermal_by_fname = _build_filename_to_image(thermal_coco)
    thermal_annots = _build_annotations_by_image(thermal_coco)

    # Sample pairs
    rgb_filenames = sorted(pair_map.keys())
    rng = random.Random(seed)
    num_samples = min(num_samples, len(rgb_filenames))
    sampled_rgb = sorted(rng.sample(rgb_filenames, num_samples))

    split_dir = output_dir / "test"
    (split_dir / "rgb").mkdir(parents=True, exist_ok=True)
    (split_dir / "thermal").mkdir(parents=True, exist_ok=True)

    metadata_lines: list[str] = []
    exported = 0

    for idx, rgb_fname in enumerate(sampled_rgb):
        thermal_fname = pair_map[rgb_fname]

        rgb_src = flir_root / "video_rgb_test" / "data" / rgb_fname
        thermal_src = flir_root / "video_thermal_test" / "data" / thermal_fname

        if not rgb_src.is_file() or not thermal_src.is_file():
            continue

        out_name = f"{idx:06d}.jpg"
        shutil.copy2(rgb_src, split_dir / "rgb" / out_name)
        shutil.copy2(thermal_src, split_dir / "thermal" / out_name)

        # Gather thermal annotations
        thermal_info = thermal_by_fname.get(thermal_fname)
        bboxes = []
        categories = []

        if thermal_info is not None:
            th_w = thermal_info.get("width", 1)
            th_h = thermal_info.get("height", 1)
            for ann in thermal_annots.get(thermal_info["id"], []):
                x, y, w, h = ann["bbox"]  # COCO: [x, y, w, h] in pixels
                bboxes.append(
                    [
                        round(x / th_w, 6),
                        round(y / th_h, 6),
                        round(w / th_w, 6),
                        round(h / th_h, 6),
                    ]
                )
                categories.append(category_map.get(ann.get("category_id", 0), "unknown"))

        entry: dict = {
            "rgb_image": f"rgb/{out_name}",
            "thermal_image": f"thermal/{out_name}",
        }
        if bboxes:
            entry["objects"] = {
                "view_name": "thermal_image",
                "bboxes": bboxes,
                "category": categories,
            }

        metadata_lines.append(json.dumps(entry, ensure_ascii=False))
        exported += 1

    metadata_path = split_dir / "metadata.jsonl"
    metadata_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")

    print(f"  Exported {exported} frame pairs to {split_dir}")
    return exported


def _parse_video_frame(filename: str) -> tuple[str, int] | None:
    """Extract (video_id, frame_number) from a FLIR thermal filename.

    Expected format: ``video-XXXXX-frame-NNNNN-HASH.jpg``
    """
    m = re.match(r"video-(\w+)-frame-(\d+)-", filename)
    if m is None:
        return None
    return m.group(1), int(m.group(2))


def export_video_test_video_mode(
    output_dir: Path,
    flir_root: Path,
    num_samples: int,
    seed: int,
) -> int:
    """Export sampled videos (as image sequences) to a Pixano-compatible folder.

    Groups frame pairs by video, copies them into per-video directories,
    and writes per-frame bbox JSON annotations with track IDs.

    Args:
        output_dir: Root output directory.
        flir_root: Path to the FLIR ADAS v2 root directory.
        num_samples: Maximum number of videos to export.
        seed: Random seed for reproducible sampling.

    Returns:
        Number of videos actually exported.
    """
    pair_map: dict[str, str] = _load_json(flir_root / "rgb_to_thermal_vid_map.json")

    thermal_coco = _load_json(flir_root / "video_thermal_test" / "coco.json")
    category_map = _build_category_map(thermal_coco)
    thermal_by_fname = _build_filename_to_image(thermal_coco)
    thermal_annots = _build_annotations_by_image(thermal_coco)

    # Group frame pairs by thermal video_id
    videos: dict[str, list[tuple[int, str, str]]] = {}
    for rgb_fname, thermal_fname in pair_map.items():
        parsed = _parse_video_frame(thermal_fname)
        if parsed is None:
            continue
        video_id, frame_num = parsed
        videos.setdefault(video_id, []).append((frame_num, rgb_fname, thermal_fname))

    # Sample videos
    rng = random.Random(seed)
    video_ids = sorted(videos.keys())
    num_samples = min(num_samples, len(video_ids))
    sampled_ids = sorted(rng.sample(video_ids, num_samples))

    split_dir = output_dir / "test"
    split_dir.mkdir(parents=True, exist_ok=True)
    metadata_lines: list[str] = []
    exported = 0

    for vid_idx, video_id in enumerate(sampled_ids):
        video_name = f"video_{vid_idx:03d}"
        frames = sorted(videos[video_id])  # sort by frame_num

        rgb_dir = split_dir / "rgb" / video_name
        thermal_dir = split_dir / "thermal" / video_name
        bbox_dir = split_dir / "bboxes" / video_name
        rgb_dir.mkdir(parents=True, exist_ok=True)
        thermal_dir.mkdir(parents=True, exist_ok=True)
        bbox_dir.mkdir(parents=True, exist_ok=True)

        for idx, (_frame_num, rgb_fname, thermal_fname) in enumerate(frames):
            rgb_src = flir_root / "video_rgb_test" / "data" / rgb_fname
            thermal_src = flir_root / "video_thermal_test" / "data" / thermal_fname

            if not rgb_src.is_file() or not thermal_src.is_file():
                continue

            out_name = f"{idx:06d}.jpg"
            shutil.copy2(rgb_src, rgb_dir / out_name)
            shutil.copy2(thermal_src, thermal_dir / out_name)

            # Build per-frame bbox annotation
            thermal_info = thermal_by_fname.get(thermal_fname)
            if thermal_info is not None:
                anns = thermal_annots.get(thermal_info["id"], [])
                if anns:
                    th_w = thermal_info.get("width", 1)
                    th_h = thermal_info.get("height", 1)
                    objects = []
                    for ann in anns:
                        x, y, w, h = ann["bbox"]
                        objects.append({
                            "track_id": ann.get("track_id", ann["id"]),
                            "bbox": [
                                round(x / th_w, 6),
                                round(y / th_h, 6),
                                round(w / th_w, 6),
                                round(h / th_h, 6),
                            ],
                            "category": category_map.get(ann.get("category_id", 0), "unknown"),
                        })
                    bbox_json = {
                        "view_name": "thermal_image",
                        "objects": objects,
                    }
                    json_name = f"{idx:06d}.json"
                    (bbox_dir / json_name).write_text(
                        json.dumps(bbox_json, ensure_ascii=False) + "\n", encoding="utf-8"
                    )

        entry = {
            "rgb_image": f"rgb/{video_name}/*.jpg",
            "thermal_image": f"thermal/{video_name}/*.jpg",
            "bboxes": f"bboxes/{video_name}/*.json",
            "fps": 30,
        }
        metadata_lines.append(json.dumps(entry, ensure_ascii=False))
        exported += 1
        print(f"  {video_name}: {len(frames)} frames (source video-{video_id})")

    metadata_path = split_dir / "metadata.jsonl"
    metadata_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")

    print(f"  Exported {exported} videos to {split_dir}")
    return exported


def main():
    """Generate a Pixano-compatible sample folder from FLIR ADAS v2."""
    parser = argparse.ArgumentParser(
        description="Generate a Pixano-compatible sample folder from FLIR ADAS v2 (multi-view).",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory for the sample dataset (e.g. ./flir_sample).",
    )
    parser.add_argument(
        "flir_root",
        type=Path,
        help="Path to the FLIR ADAS v2 root directory.",
    )
    parser.add_argument(
        "--mode",
        choices=["image", "video"],
        default="image",
        help="Export mode: 'image' (individual frame pairs) or 'video' (per-video sequences). Default: image.",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=50,
        help="Number of frame pairs (image mode) or videos (video mode) to sample (default: 50).",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for reproducible sampling (default: 42).",
    )
    args = parser.parse_args()

    output_dir: Path = args.output_dir
    flir_root: Path = args.flir_root

    if output_dir.exists():
        parser.error(f"Output directory '{output_dir}' already exists. Remove it or choose another path.")

    if not flir_root.is_dir():
        parser.error(f"FLIR root directory '{flir_root}' does not exist.")

    mapping_path = flir_root / "rgb_to_thermal_vid_map.json"
    if not mapping_path.is_file():
        parser.error(
            f"Pairing map not found: '{mapping_path}'. Ensure the FLIR root contains rgb_to_thermal_vid_map.json."
        )

    output_dir.mkdir(parents=True)
    print(f"Generating FLIR ADAS v2 sample ({args.mode} mode) in {output_dir}")

    if args.mode == "video":
        total = export_video_test_video_mode(output_dir, flir_root, args.num_samples, args.seed)
        schema_class = "FLIRVideoDatasetItem"
        unit = "videos"
    else:
        total = export_video_test(output_dir, flir_root, args.num_samples, args.seed)
        schema_class = "FLIRDatasetItem"
        unit = "frame pairs"

    print(f"\nDone. {total} {unit} exported.")
    print("\nTo import into Pixano:")
    print(
        f'  pixano data import ./my_data {output_dir} --name "FLIR ADAS Sample" '
        f"--schema examples/flir/schema.py:{schema_class}"
    )
    print(
        f'  pixano data import ./my_data {output_dir} --name "FLIR ADAS Sample" '
        f"--schema examples/flir/schema.py:{schema_class} --embed-media"
    )


if __name__ == "__main__":
    main()
