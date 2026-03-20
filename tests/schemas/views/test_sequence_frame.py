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

from pixano.schemas.views.sequence_frame import SequenceFrame, is_sequence_frame


# ---------------------------------------------------------------------------
# Test asset
# ---------------------------------------------------------------------------
ASSETS_DIR = Path(__file__).resolve().parent.parent.parent / "assets"
SAMPLE_JPG = ASSETS_DIR / "coco_dataset" / "image" / "val" / "000000000632.jpg"
SAMPLE_JPG_WIDTH = 640
SAMPLE_JPG_HEIGHT = 483
SAMPLE_JPG_FORMAT = "JPEG"


def _make_dummy_png_bytes(width: int = 200, height: int = 100) -> bytes:
    """Create a minimal in-memory PNG image and return its raw bytes."""
    img = PIL.Image.new("RGB", (width, height), color=(0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _assert_valid_preview(preview: bytes, max_size: int = 64) -> None:
    """Assert that *preview* is a valid PNG whose dimensions do not exceed *max_size*."""
    assert isinstance(preview, bytes)
    assert len(preview) > 0
    thumb = PIL.Image.open(io.BytesIO(preview))
    assert thumb.format == "PNG"
    assert thumb.width <= max_size
    assert thumb.height <= max_size


# ===================================================================
# SequenceFrame.from_uri
# ===================================================================
class TestFromUri:
    def test_basic(self) -> None:
        sf = SequenceFrame.from_uri(
            record_id="rec-1",
            logical_name="front_camera",
            uri=str(SAMPLE_JPG),
            timestamp=1.5,
            frame_index=3,
        )

        # Auto-generated id.
        assert isinstance(sf.id, str)
        assert len(sf.id) > 0

        # Image metadata extracted from file.
        assert sf.width == SAMPLE_JPG_WIDTH
        assert sf.height == SAMPLE_JPG_HEIGHT
        assert sf.format == SAMPLE_JPG_FORMAT

        # URI stored, raw_bytes empty.
        assert sf.uri == str(SAMPLE_JPG)
        assert sf.raw_bytes == b""

        # Record identifiers propagated.
        assert sf.record_id == "rec-1"
        assert sf.logical_name == "front_camera"

        # SequenceFrame-specific fields.
        assert sf.timestamp == 1.5
        assert sf.frame_index == 3

        # Preview thumbnail.
        _assert_valid_preview(sf.preview)
        assert sf.preview_format == "png"

    def test_custom_id(self) -> None:
        sf = SequenceFrame.from_uri(
            record_id="rec-2",
            logical_name="cam",
            uri=str(SAMPLE_JPG),
            timestamp=0.0,
            frame_index=0,
            id="custom-sf-id",
        )
        assert sf.id == "custom-sf-id"

    def test_missing_file_raises(self) -> None:
        with pytest.raises(FileNotFoundError):
            SequenceFrame.from_uri(
                record_id="rec-x",
                logical_name="missing",
                uri="/tmp/does_not_exist_sf.jpg",
                timestamp=0.0,
                frame_index=0,
            )


# ===================================================================
# SequenceFrame.from_bytes
# ===================================================================
class TestFromBytes:
    def test_basic_png(self) -> None:
        raw = _make_dummy_png_bytes(width=200, height=100)
        sf = SequenceFrame.from_bytes(
            record_id="rec-3",
            logical_name="thermal",
            raw_bytes=raw,
            timestamp=2.0,
            frame_index=5,
        )

        # Auto-generated id.
        assert isinstance(sf.id, str)
        assert len(sf.id) > 0

        # Image metadata.
        assert sf.width == 200
        assert sf.height == 100
        assert sf.format == "PNG"

        # raw_bytes stored, uri empty.
        assert sf.raw_bytes == raw
        assert sf.uri == ""

        # Record identifiers.
        assert sf.record_id == "rec-3"
        assert sf.logical_name == "thermal"

        # SequenceFrame-specific fields.
        assert sf.timestamp == 2.0
        assert sf.frame_index == 5

        # Preview.
        _assert_valid_preview(sf.preview)
        assert sf.preview_format == "png"

    def test_basic_jpeg(self) -> None:
        raw = SAMPLE_JPG.read_bytes()
        sf = SequenceFrame.from_bytes(
            record_id="rec-4",
            logical_name="rgb",
            raw_bytes=raw,
            timestamp=0.033,
            frame_index=1,
        )
        assert sf.width == SAMPLE_JPG_WIDTH
        assert sf.height == SAMPLE_JPG_HEIGHT
        assert sf.format == SAMPLE_JPG_FORMAT
        assert sf.timestamp == 0.033
        assert sf.frame_index == 1
        _assert_valid_preview(sf.preview)

    def test_custom_id(self) -> None:
        raw = _make_dummy_png_bytes()
        sf = SequenceFrame.from_bytes(
            record_id="rec-5",
            logical_name="depth",
            raw_bytes=raw,
            timestamp=0.0,
            frame_index=0,
            id="explicit-sf-id",
        )
        assert sf.id == "explicit-sf-id"

    def test_preview_dimensions(self) -> None:
        """A large image should produce a thumbnail no bigger than 64x64."""
        large = PIL.Image.new("RGB", (1024, 768), color=(0, 128, 255))
        buf = io.BytesIO()
        large.save(buf, format="PNG")
        raw = buf.getvalue()

        sf = SequenceFrame.from_bytes(
            record_id="rec-6",
            logical_name="wide",
            raw_bytes=raw,
            timestamp=10.0,
            frame_index=300,
        )
        thumb = PIL.Image.open(io.BytesIO(sf.preview))
        assert thumb.width <= 64
        assert thumb.height <= 64
        # 1024x768 -> aspect preserved: 64x48
        assert thumb.width == 64
        assert thumb.height == 48

    def test_zero_timestamp_and_index(self) -> None:
        """Edge case: timestamp=0.0 and frame_index=0 should be valid."""
        raw = _make_dummy_png_bytes(width=10, height=10)
        sf = SequenceFrame.from_bytes(
            record_id="rec-7",
            logical_name="start",
            raw_bytes=raw,
            timestamp=0.0,
            frame_index=0,
        )
        assert sf.timestamp == 0.0
        assert sf.frame_index == 0


# ===================================================================
# is_sequence_frame
# ===================================================================
class TestIsSequenceFrame:
    def test_sequence_frame_class(self) -> None:
        assert is_sequence_frame(SequenceFrame) is True

    def test_sequence_frame_strict(self) -> None:
        assert is_sequence_frame(SequenceFrame, strict=True) is True

    def test_non_sequence_frame(self) -> None:
        assert is_sequence_frame(str) is False

    def test_subclass(self) -> None:
        class CustomFrame(SequenceFrame):
            extra: str = ""

        assert is_sequence_frame(CustomFrame) is True
        assert is_sequence_frame(CustomFrame, strict=True) is False
