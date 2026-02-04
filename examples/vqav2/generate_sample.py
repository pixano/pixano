# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Generate a sample folder from VQAv2.

Produces a Pixano-compatible folder structure with metadata.jsonl files
ready to import with `pixano data import`.

Uses the small VQAv2 subset from HuggingFace (merve/vqav2-small).

Requirements:
    pip install datasets pillow

Usage:
    python generate_sample.py ./vqav2_sample --num-samples 50
    python generate_sample.py ./vqav2_sample --num-samples 100

Then import into Pixano:
    pixano data import ./my_data ./vqav2_sample --name "VQAv2 Sample" --type vqa
"""

import argparse
import json
import random
from pathlib import Path

from datasets import load_dataset
from PIL import Image


def export_split(output_dir: Path, num_samples: int, seed: int) -> int:
    """Export a sample of VQAv2 to a Pixano-compatible folder.

    Args:
        output_dir: Root output directory (e.g. ./vqav2_sample).
        num_samples: Number of Q&A pairs to sample.
        seed: Random seed for reproducible sampling.

    Returns:
        Number of images actually exported.
    """
    split = "validation"
    split_dir = output_dir / split
    split_dir.mkdir(parents=True, exist_ok=True)

    print(f"  Loading VQAv2 (merve/vqav2-small) from HuggingFace...")
    ds = load_dataset("merve/vqav2-small", split="validation")

    rng = random.Random(seed)
    num_samples = min(num_samples, len(ds))
    sampled_indices = sorted(rng.sample(range(len(ds)), num_samples))

    metadata_lines: list[str] = []

    for i, idx in enumerate(sampled_indices):
        entry = ds[idx]

        filename = f"{i:06d}.jpg"
        dst_image = split_dir / filename

        # Save image as JPEG (convert to RGB if needed)
        pil_image: Image.Image = entry["image"]
        if pil_image.mode != "RGB":
            pil_image = pil_image.convert("RGB")
        pil_image.save(dst_image, "JPEG")

        # Build conversation entry
        conversation: dict = {
            "question": {
                "content": entry["question"],
                "question_type": "OPEN",
            },
            "responses": [{"content": entry["multiple_choice_answer"]}],
        }

        metadata_entry = {
            "image": filename,
            "conversations": [conversation],
        }
        metadata_lines.append(json.dumps(metadata_entry, ensure_ascii=False))

    # Write metadata.jsonl
    metadata_path = split_dir / "metadata.jsonl"
    metadata_path.write_text("\n".join(metadata_lines) + "\n", encoding="utf-8")

    print(f"  {split}: exported {num_samples} images to {split_dir}")
    return num_samples


def main():
    """Generate a Pixano-compatible sample folder from VQAv2."""
    parser = argparse.ArgumentParser(
        description="Generate a Pixano-compatible sample folder from VQAv2.",
    )
    parser.add_argument(
        "output_dir",
        type=Path,
        help="Output directory for the sample dataset (e.g. ./vqav2_sample).",
    )
    parser.add_argument(
        "--num-samples",
        type=int,
        default=50,
        help="Number of images to sample (default: 50).",
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

    output_dir.mkdir(parents=True)
    print(f"Generating VQAv2 sample in {output_dir}")

    total = export_split(output_dir, args.num_samples, args.seed)

    print(f"\nDone. {total} images exported.")
    print("\nTo import into Pixano:")
    print(f'  pixano data import ./my_data {output_dir} --name "VQAv2 Sample" --type vqa')


if __name__ == "__main__":
    main()
