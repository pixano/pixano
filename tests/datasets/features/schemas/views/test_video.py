# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.datasets.features import Video, create_video, is_video
from pixano.datasets.features.types.schema_reference import ItemRef, ViewRef
from tests.datasets.features.utils import make_tests_is_sublass_strict


ASSETS_DIRECTORY = Path(__file__).parent.parent.parent.parent.parent / "assets"
VIDEO_ASSET_URL = ASSETS_DIRECTORY / "sample_data/video_mp4.mp4"


def test_is_video():
    make_tests_is_sublass_strict(is_video, Video)


def test_create_video():
    # Test 1: read url and default references
    video: Video = create_video(
        url=VIDEO_ASSET_URL,
    )
    assert 6.97 == round(video.duration, 2)
    assert 29.97 == round(video.fps, 2)
    video.duration = 6.97
    video.fps = 29.97
    assert video == Video(
        url=str(VIDEO_ASSET_URL.as_posix()),
        width=320,
        height=240,
        format="mp4",
        num_frames=209,
        fps=29.97,
        duration=6.97,
        id="",
        item_ref=ItemRef.none(),
        parent_ref=ViewRef.none(),
    )

    # Test 2: read url with custom id and other path and custom references
    video = create_video(
        url=VIDEO_ASSET_URL,
        other_path=ASSETS_DIRECTORY,
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    )
    assert 6.97 == round(video.duration, 2)
    assert 29.97 == round(video.fps, 2)
    video.duration = 6.97
    video.fps = 29.97
    assert video == Video(
        url="sample_data/video_mp4.mp4",
        width=320,
        height=240,
        format="mp4",
        num_frames=209,
        fps=29.97,
        duration=6.97,
        id="id",
        item_ref=ItemRef(id="item_id"),
        parent_ref=ViewRef(id="view_id", name="view"),
    )

    # Test 3: no read
    video = create_video(
        url=VIDEO_ASSET_URL,
        width=100,
        height=100,
        format="avi",
        num_frames=100,
        fps=30,
        duration=3.33,
    )
    assert video == Video(
        url=str(VIDEO_ASSET_URL.as_posix()),
        width=100,
        height=100,
        format="avi",
        num_frames=100,
        fps=30,
        duration=3.33,
        id="",
        item_ref=ItemRef.none(),
        parent_ref=ViewRef.none(),
    )

