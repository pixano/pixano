# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import SequenceFrame, create_sequence_frame, is_sequence_frame
from pixano.features.types.schema_reference import ItemRef, ViewRef
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY, IMAGE_JPG_ASSET_URL, IMAGE_JPG_METADATA
from tests.features.utils import make_tests_is_sublass_strict


class TestSequenceFrame:
    def test_open(self):
        sequence_frame = create_sequence_frame(
            timestamp=1.0,
            frame_index=1,
            url=IMAGE_JPG_ASSET_URL,
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
    # Test 1: read url and default referneces
    sequence_frame = create_sequence_frame(url=IMAGE_JPG_ASSET_URL, timestamp=1.0, frame_index=1)
    assert sequence_frame.model_dump(exclude_timestamps=True) == SequenceFrame(
        url=str(IMAGE_JPG_ASSET_URL.as_posix()),
        timestamp=1.0,
        frame_index=1,
        width=IMAGE_JPG_METADATA["width"],
        height=IMAGE_JPG_METADATA["height"],
        format=IMAGE_JPG_METADATA["format"],
        id="",
        item=ItemRef.none(),
        parent_ref=ViewRef.none(),
    ).model_dump(exclude_timestamps=True)

    # Test 2: read url with custom id and other path and custom references
    sequence_frame = create_sequence_frame(
        timestamp=1.0,
        frame_index=1,
        url=IMAGE_JPG_ASSET_URL,
        other_path=ASSETS_DIRECTORY,
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    )
    assert sequence_frame.model_dump(exclude_timestamps=True) == SequenceFrame(
        url="sample_data/image_jpg.jpg",
        timestamp=1.0,
        frame_index=1,
        width=IMAGE_JPG_METADATA["width"],
        height=IMAGE_JPG_METADATA["height"],
        format=IMAGE_JPG_METADATA["format"],
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    ).model_dump(exclude_timestamps=True)

    # Test 3: no read
    sequence_frame = create_sequence_frame(
        url=IMAGE_JPG_ASSET_URL,
        timestamp=1.0,
        frame_index=1,
        width=100,
        height=100,
        format="PNG",
    )
    assert sequence_frame.model_dump(exclude_timestamps=True) == SequenceFrame(
        url=str(IMAGE_JPG_ASSET_URL.as_posix()),
        timestamp=1.0,
        frame_index=1,
        width=100,
        height=100,
        format="PNG",
        id="",
        item=ItemRef.none(),
        parent_ref=ViewRef.none(),
    ).model_dump(exclude_timestamps=True)
