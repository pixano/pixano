# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import math
import os
import os.path
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def generate_mosaic_name(image_files, extension=".jpg"):
    """Generate a name for mosaic file whime keeping most common path / filename as possible."""
    if not image_files:
        return "mosaic" + extension
    common_path = os.path.commonpath(image_files)
    filenames = [os.path.basename(f) for f in image_files]
    common_prefix = os.path.commonprefix(filenames).rstrip("_- ")
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


def add_label_above(image, text, label_height=30):
    """Add a label at top left of image."""
    width, height = image.size

    label_img = Image.new("RGB", (width, label_height), (0, 0, 0))  # Fond noir
    draw = ImageDraw.Draw(label_img)

    # get Arial font, else system font
    try:
        font = ImageFont.truetype("arial.ttf", 20)
    except IOError:
        font = ImageFont.load_default()

    # Center text
    text_size = draw.textbbox((0, 0), text, font=font)  # Mesurer le texte
    text_width = text_size[2] - text_size[0]
    text_height = text_size[3] - text_size[1]

    text_x = (width - text_width) // 2
    text_y = (label_height - text_height) // 2

    # Draw text (white)
    draw.text((text_x, text_y), text, fill=(255, 255, 255), font=font)

    # Concat label and original image
    new_img = Image.new("RGB", (width, height + label_height))
    new_img.paste(label_img, (0, 0))  # Add label over
    new_img.paste(image, (0, label_height))  # put image under

    return new_img


def create_mosaic(
    source_dir: Path, split, image_files, output_path, label_prefix="image", padding=10, label_height=30
):
    """Create a mosaic from image_files with black background."""
    if not image_files:
        return

    need_split = False
    images = []
    for f in image_files:
        try:
            image = Image.open(source_dir / f)
        except FileNotFoundError:
            image = Image.open(source_dir / split / f)
            need_split = True
        image = image.convert("RGBA")
        images.append(image)

    rows, cols = arrange_grid(len(images))
    avg_width, avg_height = compute_average_size(images)

    images_resized = []
    for idx, img in enumerate(images):
        img_resized = img.resize((avg_width, avg_height), Image.LANCZOS)
        img_rgb = Image.new("RGB", img_resized.size, (0, 0, 0))
        img_rgb.paste(img_resized, mask=img_resized.split()[3])  # Apply alpha channel
        # Add label
        if label_prefix != "":
            label_text = f"{label_prefix} {idx + 1}"
            img_labeled = add_label_above(img_rgb, label_text, label_height)
            images_resized.append(img_labeled)
        else:
            images_resized.append(img_rgb)

    mosaic_width = cols * (avg_width + padding) - padding
    mosaic_height = rows * (avg_height + label_height + padding) - padding
    mosaic = Image.new("RGB", (mosaic_width, mosaic_height), (0, 0, 0))

    for idx, img in enumerate(images_resized):
        x_offset = (idx % cols) * (avg_width + padding)
        y_offset = (idx // cols) * (avg_height + label_height + padding)
        mosaic.paste(img, (x_offset, y_offset))

    if need_split:
        mosaic.save(source_dir / split / output_path, format="JPEG", quality=85, optimize=True)
    else:
        mosaic.save(source_dir / output_path, format="JPEG", quality=85, optimize=True)


def mosaic(source_dir: Path, split: str, image_files: list[str], view_name: str, mosaic_filename: str = "") -> str:
    """Create a mosaic from input images. Add a label if view_name is not empty string."""
    if not mosaic_filename:
        mosaic_filename = generate_mosaic_name(image_files)
    create_mosaic(source_dir, split, image_files, mosaic_filename, label_prefix=view_name, label_height=30, padding=5)
    return mosaic_filename
