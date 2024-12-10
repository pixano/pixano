# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features import Video, create_video, is_video
from pixano.features.types.schema_reference import ItemRef, ViewRef
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY, VIDEO_MP4_ASSET_URL, VIDEO_MP4_METADATA
from tests.features.utils import make_tests_is_sublass_strict


def test_is_video():
    make_tests_is_sublass_strict(is_video, Video)


def test_create_video():
    # Test 1: read url and default references
    video: Video = create_video(
        url=VIDEO_MP4_ASSET_URL,
    )
    assert VIDEO_MP4_METADATA["duration"] == round(video.duration, 2)
    assert VIDEO_MP4_METADATA["fps"] == round(video.fps, 2)
    video.duration = VIDEO_MP4_METADATA["duration"]
    video.fps = VIDEO_MP4_METADATA["fps"]
    assert video.model_dump(exclude_timestamps=True) == Video(
        url=str(VIDEO_MP4_ASSET_URL.as_posix()),
        width=320,
        height=240,
        format="mp4",
        num_frames=VIDEO_MP4_METADATA["num_frames"],
        fps=VIDEO_MP4_METADATA["fps"],
        duration=VIDEO_MP4_METADATA["duration"],
        id="",
        item_ref=ItemRef.none(),
        parent_ref=ViewRef.none(),
    ).model_dump(exclude_timestamps=True)

    # Test 2: read url with custom id and other path and custom references
    video = create_video(
        url=VIDEO_MP4_ASSET_URL,
        url_relative_path=ASSETS_DIRECTORY,
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    )
    assert VIDEO_MP4_METADATA["duration"] == round(video.duration, 2)
    assert VIDEO_MP4_METADATA["fps"] == round(video.fps, 2)
    video.duration = VIDEO_MP4_METADATA["duration"]
    video.fps = VIDEO_MP4_METADATA["fps"]
    assert video.model_dump(exclude_timestamps=True) == Video(
        url="sample_data/video_mp4.mp4",
        width=VIDEO_MP4_METADATA["width"],
        height=VIDEO_MP4_METADATA["height"],
        format=VIDEO_MP4_METADATA["format"],
        num_frames=VIDEO_MP4_METADATA["num_frames"],
        fps=VIDEO_MP4_METADATA["fps"],
        duration=VIDEO_MP4_METADATA["duration"],
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    ).model_dump(exclude_timestamps=True)

    # Test 3: no read
    video = create_video(
        url=VIDEO_MP4_ASSET_URL,
        width=100,
        height=100,
        format="avi",
        num_frames=100,
        fps=30,
        duration=3.33,
    )
    assert video.model_dump(exclude_timestamps=True) == Video(
        url=str(VIDEO_MP4_ASSET_URL.as_posix()),
        width=100,
        height=100,
        format="avi",
        num_frames=100,
        fps=30,
        duration=3.33,
        id="",
        item_ref=ItemRef.none(),
        parent_ref=ViewRef.none(),
    ).model_dump(exclude_timestamps=True)
