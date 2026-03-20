# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import io
from pathlib import Path

import PIL.Image
import pytest

from pixano.schemas.views.image import Image, is_image


# ---------------------------------------------------------------------------
# Test asset: a real JPEG file shipped with the repository.
# ---------------------------------------------------------------------------
ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
SAMPLE_JPG = ASSETS_DIR / "coco_dataset" / "image" / "val" / "000000000632.jpg"
SAMPLE_JPG_WIDTH = 640
SAMPLE_JPG_HEIGHT = 483
SAMPLE_JPG_FORMAT = "JPEG"


def _make_dummy_png_bytes(width: int = 200, height: int = 100) -> bytes:
    """Create a minimal in-memory PNG image and return its raw bytes."""
    img = PIL.Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Helper to validate the preview field
# ---------------------------------------------------------------------------
def _assert_valid_preview(preview: bytes, max_size: int = 64) -> None:
    """Assert that *preview* is a valid PNG whose dimensions do not exceed *max_size*."""
    assert isinstance(preview, bytes)
    assert len(preview) > 0
    thumb = PIL.Image.open(io.BytesIO(preview))
    assert thumb.format == "PNG"
    assert thumb.width <= max_size
    assert thumb.height <= max_size


# ===================================================================
# Image.from_uri
# ===================================================================
class TestFromUri:
    def test_basic(self) -> None:
        image = Image.from_uri(
            record_id="rec-1",
            logical_name="front_camera",
            uri=str(SAMPLE_JPG),
        )

        # Auto-generated id is present and non-empty.
        assert isinstance(image.id, str)
        assert len(image.id) > 0

        # Metadata extracted from the file.
        assert image.width == SAMPLE_JPG_WIDTH
        assert image.height == SAMPLE_JPG_HEIGHT
        assert image.format == SAMPLE_JPG_FORMAT

        # URI stored, raw_bytes empty.
        assert image.uri == str(SAMPLE_JPG)
        assert image.raw_bytes == b""

        # Record identifiers propagated.
        assert image.record_id == "rec-1"
        assert image.logical_name == "front_camera"

        # Preview thumbnail.
        _assert_valid_preview(image.preview)
        assert image.preview_format == "png"

    def test_custom_id(self) -> None:
        image = Image.from_uri(
            record_id="rec-2",
            logical_name="side_camera",
            uri=str(SAMPLE_JPG),
            id="my-custom-id",
        )
        assert image.id == "my-custom-id"

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            Image.from_uri(
                record_id="rec-x",
                logical_name="missing",
                uri="/tmp/does_not_exist_abc123.jpg",
            )


# ===================================================================
# Image.from_bytes
# ===================================================================
class TestFromBytes:
    def test_basic_png(self) -> None:
        raw = _make_dummy_png_bytes(width=200, height=100)
        image = Image.from_bytes(
            record_id="rec-3",
            logical_name="thermal",
            raw_bytes=raw,
        )

        # Auto-generated id.
        assert isinstance(image.id, str)
        assert len(image.id) > 0

        # Metadata.
        assert image.width == 200
        assert image.height == 100
        assert image.format == "PNG"

        # raw_bytes stored, uri empty.
        assert image.raw_bytes == raw
        assert image.uri == ""

        # Record identifiers.
        assert image.record_id == "rec-3"
        assert image.logical_name == "thermal"

        # Preview.
        _assert_valid_preview(image.preview)
        assert image.preview_format == "png"

    def test_basic_jpeg(self) -> None:
        """Ensure from_bytes works with a JPEG buffer as well."""
        raw = SAMPLE_JPG.read_bytes()
        image = Image.from_bytes(
            record_id="rec-4",
            logical_name="rgb",
            raw_bytes=raw,
        )
        assert image.width == SAMPLE_JPG_WIDTH
        assert image.height == SAMPLE_JPG_HEIGHT
        assert image.format == SAMPLE_JPG_FORMAT
        _assert_valid_preview(image.preview)

    def test_custom_id(self) -> None:
        raw = _make_dummy_png_bytes()
        image = Image.from_bytes(
            record_id="rec-5",
            logical_name="depth",
            raw_bytes=raw,
            id="explicit-id-42",
        )
        assert image.id == "explicit-id-42"

    def test_preview_dimensions(self) -> None:
        """A large image should produce a thumbnail no bigger than 64x64."""
        large = PIL.Image.new("RGB", (1024, 768), color=(0, 128, 255))
        buf = io.BytesIO()
        large.save(buf, format="PNG")
        raw = buf.getvalue()

        image = Image.from_bytes(
            record_id="rec-6",
            logical_name="wide",
            raw_bytes=raw,
        )
        thumb = PIL.Image.open(io.BytesIO(image.preview))
        assert thumb.width <= 64
        assert thumb.height <= 64
        # For a 1024x768 image, thumbnail preserves aspect ratio:
        # max dim = 64 => 64x48
        assert thumb.width == 64
        assert thumb.height == 48

    def test_small_image_preview_not_upscaled(self) -> None:
        """An image smaller than 64x64 should not be upscaled."""
        small = PIL.Image.new("RGB", (10, 10), color=(0, 0, 0))
        buf = io.BytesIO()
        small.save(buf, format="PNG")
        raw = buf.getvalue()

        image = Image.from_bytes(
            record_id="rec-7",
            logical_name="tiny",
            raw_bytes=raw,
        )
        thumb = PIL.Image.open(io.BytesIO(image.preview))
        assert thumb.width == 10
        assert thumb.height == 10
