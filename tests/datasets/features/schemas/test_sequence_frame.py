# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.datasets.features.schemas.sequence_frame import SequenceFrame, create_sequence_frame, is_sequence_frame
from tests.datasets.features.utils import make_tests_is_sublass_strict


ASSETS_DIRECTORY = Path(__file__).parent.parent.parent.parent / "assets"
IMAGE_ASSET_URL = ASSETS_DIRECTORY / "sample_data/image_jpg.jpg"


class TestSequenceFrame:
    def test_open(self):
        sequence_frame = create_sequence_frame(
            item_id="item_id",
            sequence_id="sequence_id",
            timestamp=1.0,
            frame_index=1,
            url=IMAGE_ASSET_URL,
            other_path=ASSETS_DIRECTORY,
        )

        io = sequence_frame.open(ASSETS_DIRECTORY)
        assert isinstance(io, str)

    def test_open_url(self):
        sequence_frame = SequenceFrame.open_url("sample_data/image_jpg.jpg", ASSETS_DIRECTORY)
        assert isinstance(sequence_frame, str)


def test_is_sequence_frame():
    make_tests_is_sublass_strict(is_sequence_frame, SequenceFrame)


def test_create_sequence_frame():
    # Test 1: read url
    sequence_frame = create_sequence_frame(
        item_id="item_id", sequence_id="sequence_id", url=IMAGE_ASSET_URL, timestamp=1.0, frame_index=1
    )

    assert isinstance(sequence_frame, SequenceFrame)
    assert isinstance(sequence_frame.id, str)
    assert sequence_frame.item_id == "item_id"
    assert sequence_frame.sequence_id == "sequence_id"
    assert sequence_frame.url == str(IMAGE_ASSET_URL.as_posix())
    assert sequence_frame.timestamp == 1.0
    assert sequence_frame.frame_index == 1
    assert sequence_frame.width == 586
    assert sequence_frame.height == 640
    assert sequence_frame.format == "JPEG"

    # Test 2: read url with custom id and other path
    sequence_frame = create_sequence_frame(
        item_id="item_id",
        sequence_id="sequence_id",
        timestamp=1.0,
        frame_index=1,
        id="id",
        url=IMAGE_ASSET_URL,
        other_path=ASSETS_DIRECTORY,
    )

    assert isinstance(sequence_frame, SequenceFrame)
    assert sequence_frame.id == "id"
    assert sequence_frame.item_id == "item_id"
    assert sequence_frame.sequence_id == "sequence_id"
    assert sequence_frame.url == "sample_data/image_jpg.jpg"
    assert sequence_frame.timestamp == 1.0
    assert sequence_frame.frame_index == 1
    assert sequence_frame.width == 586
    assert sequence_frame.height == 640
    assert sequence_frame.format == "JPEG"

    # Test 3: no read
    sequence_frame = create_sequence_frame(
        item_id="item_id",
        sequence_id="sequence_id",
        url=IMAGE_ASSET_URL,
        timestamp=1.0,
        frame_index=1,
        id="id",
        width=100,
        height=100,
        format="PNG",
    )

    assert isinstance(sequence_frame, SequenceFrame)
    assert sequence_frame.id == "id"
    assert sequence_frame.item_id == "item_id"
    assert sequence_frame.sequence_id == "sequence_id"
    assert sequence_frame.url == str(IMAGE_ASSET_URL.as_posix())
    assert sequence_frame.timestamp == 1.0
    assert sequence_frame.frame_index == 1
    assert sequence_frame.width == 100
    assert sequence_frame.height == 100
    assert sequence_frame.format == "PNG"
