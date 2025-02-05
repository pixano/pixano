# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import math
import os
import os.path
from pathlib import Path

from PIL import Image


def generate_mosaic_name(image_files, extension=".jpg"):
    """Generate a name for mosaic file whime keeping most common path / filename as possible."""
    if not image_files:
        return "mosaic" + extension

    # Extract common path
    common_path = os.path.commonpath(image_files)

    # Extract file name only
    filenames = [os.path.basename(f) for f in image_files]

    # Get common filename
    common_prefix = os.path.commonprefix(filenames).rstrip("_- ")

    # Generate final name
    mosaic_name = f"{common_prefix}_mosaic{extension}" if common_prefix else f"mosaic{extension}"

    return os.path.join(common_path, mosaic_name)


def arrange_grid(num_images):
    """Get optimal grid distribution (rows, cols) for num_images."""
    cols = math.ceil(math.sqrt(num_images))
    rows = math.ceil(num_images / cols)
    return rows, cols


def compute_average_size(images):
    """Compute images average size."""
    widths, heights = zip(*(img.size for img in images))
    avg_width = sum(widths) // len(images)
    avg_height = sum(heights) // len(images)
    return avg_width, avg_height


def create_mosaic(source_dir: Path, image_files, output_path, padding=10):
    """Create a mosaic from image_files with black background."""
    if not image_files:
        print("No input images.")
        return

    images = [Image.open(source_dir / f).convert("RGBA") for f in image_files]
    rows, cols = arrange_grid(len(images))
    avg_width, avg_height = compute_average_size(images)
    target_size = (avg_width, avg_height)
    images_resized = [img.resize(target_size, Image.LANCZOS) for img in images]
    mosaic_width = cols * (avg_width + padding) - padding
    mosaic_height = rows * (avg_height + padding) - padding
    mosaic = Image.new("RGB", (mosaic_width, mosaic_height), (0, 0, 0))

    for idx, img in enumerate(images_resized):
        x_offset = (idx % cols) * (avg_width + padding)
        y_offset = (idx // cols) * (avg_height + padding)
        # Create RGB version with black background if image has transparency
        img_rgb = Image.new("RGB", img.size, (0, 0, 0))
        img_rgb.paste(img, mask=img.split()[3])  # Apply alpha channel
        mosaic.paste(img_rgb, (x_offset, y_offset))

    mosaic.save(source_dir / output_path, format="JPEG", quality=85, optimize=True)


def mosaic(source_dir: Path, image_files: list[str]) -> str:
    """Create a mosaic from input images."""
    mosaic_filename = generate_mosaic_name(image_files)
    create_mosaic(source_dir, image_files, mosaic_filename, padding=5)
    return mosaic_filename
