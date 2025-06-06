# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path

import pytest
from PIL import Image

from pixano.datasets.utils.mosaic import (
    add_label_above,
    arrange_grid,
    compute_average_size,
    create_mosaic,
    generate_mosaic_name,
    mosaic,
)


@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


def test_generate_mosaic_name():
    image_files = ["/path/to/image1.jpg", "/path/to/image2.jpg"]
    assert generate_mosaic_name(image_files) == "/path/to/image_mosaic.jpg"

    image_files = []
    assert generate_mosaic_name(image_files) == "mosaic.jpg"


def test_arrange_grid():
    assert arrange_grid(4) == (2, 2)
    assert arrange_grid(5) == (2, 3)
    assert arrange_grid(9) == (3, 3)


def test_compute_average_size():
    images = [Image.new("RGB", (100, 200)), Image.new("RGB", (200, 300))]
    assert compute_average_size(images) == (150, 250)


def test_add_label_above():
    image = Image.new("RGB", (100, 200), color="red")
    labeled_image = add_label_above(image, "Test Label")
    assert labeled_image.size == (100, 230)  # 200 + 30 (label_height)


def test_create_mosaic(temp_dir):
    # Create some test images
    image_files = ["image1.jpg", "image2.jpg"]
    for img_file in image_files:
        img = Image.new("RGB", (100, 100), color="red")
        img.save(temp_dir / img_file)

    output_path = "mosaic.jpg"
    create_mosaic(temp_dir, "", image_files, output_path, label_prefix="Test", padding=10, label_height=30)

    assert (temp_dir / output_path).exists()


def test_mosaic(temp_dir):
    # Create some test images
    image_files = ["image1.jpg", "image2.jpg"]
    for img_file in image_files:
        img = Image.new("RGB", (100, 100), color="red")
        img.save(temp_dir / img_file)

    mosaic_filename = mosaic(temp_dir, "", image_files, "Test View", "")
    assert (temp_dir / mosaic_filename).exists()
