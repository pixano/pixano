# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import Video, create_video, is_video
from tests.assets.sample_data.metadata import VIDEO_MP4_ASSET_URL, VIDEO_MP4_METADATA
from tests.features.utils import make_tests_is_sublass_strict


def test_is_video():
    make_tests_is_sublass_strict(is_video, Video)


def test_create_video():
    # Test 1: read url and default references
    video: Video = create_video(
        uri=VIDEO_MP4_ASSET_URL,
        width=VIDEO_MP4_METADATA["width"],
        height=VIDEO_MP4_METADATA["height"],
        format=VIDEO_MP4_METADATA["format"],
        num_frames=VIDEO_MP4_METADATA["num_frames"],
        fps=VIDEO_MP4_METADATA["fps"],
        duration=VIDEO_MP4_METADATA["duration"],
    )
    assert video.model_dump(exclude={"created_at", "updated_at"}) == Video(
        uri=str(VIDEO_MP4_ASSET_URL.as_posix()),
        width=320,
        height=240,
        format="mp4",
        num_frames=VIDEO_MP4_METADATA["num_frames"],
        fps=VIDEO_MP4_METADATA["fps"],
        duration=VIDEO_MP4_METADATA["duration"],
        id="",
        record_id="",
    ).model_dump(exclude={"created_at", "updated_at"})

    # Test 2: read url with custom id and custom references
    video = create_video(
        uri=VIDEO_MP4_ASSET_URL,
        id="id",
        record_id="record_id",
        logical_name="video",
        width=VIDEO_MP4_METADATA["width"],
        height=VIDEO_MP4_METADATA["height"],
        format=VIDEO_MP4_METADATA["format"],
        num_frames=VIDEO_MP4_METADATA["num_frames"],
        fps=VIDEO_MP4_METADATA["fps"],
        duration=VIDEO_MP4_METADATA["duration"],
    )
    assert video.model_dump(exclude={"created_at", "updated_at"}) == Video(
        uri=str(VIDEO_MP4_ASSET_URL.as_posix()),
        width=VIDEO_MP4_METADATA["width"],
        height=VIDEO_MP4_METADATA["height"],
        format=VIDEO_MP4_METADATA["format"],
        num_frames=VIDEO_MP4_METADATA["num_frames"],
        fps=VIDEO_MP4_METADATA["fps"],
        duration=VIDEO_MP4_METADATA["duration"],
        id="id",
        record_id="record_id",
        logical_name="video",
    ).model_dump(exclude={"created_at", "updated_at"})

    # Test 3: no read
    video = create_video(
        uri=VIDEO_MP4_ASSET_URL,
        width=100,
        height=100,
        format="avi",
        num_frames=100,
        fps=30,
        duration=3.33,
    )
    assert video.model_dump(exclude={"created_at", "updated_at"}) == Video(
        uri=str(VIDEO_MP4_ASSET_URL.as_posix()),
        width=100,
        height=100,
        format="avi",
        num_frames=100,
        fps=30,
        duration=3.33,
        id="",
        record_id="",
    ).model_dump(exclude={"created_at", "updated_at"})
