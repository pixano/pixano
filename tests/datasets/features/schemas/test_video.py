# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.datasets.features.schemas.video import Video, create_video, is_video
from tests.datasets.features.utils import make_tests_is_sublass_strict


ASSETS_DIRECTORY = Path(__file__).parent.parent.parent.parent / "assets"
VIDEO_ASSET_URL = ASSETS_DIRECTORY / "sample_data/video_mp4.mp4"


def test_is_video():
    make_tests_is_sublass_strict(is_video, Video)


def test_create_video():
    # Test 1: read url
    video: Video = create_video(
        item_id="item_id",
        url=VIDEO_ASSET_URL,
    )

    assert isinstance(video, Video)
    assert isinstance(video.id, str)
    assert video.item_id == "item_id"
    assert video.url == str(VIDEO_ASSET_URL.as_posix())
    assert video.width == 320
    assert video.height == 240
    assert video.format == "mp4"
    assert video.num_frames == 209
    assert round(video.fps, 2) == 29.97

    # Test 2: read url with custom id and other path
    video = create_video(item_id="item_id", id="id", url=VIDEO_ASSET_URL, other_path=ASSETS_DIRECTORY)

    assert isinstance(video, Video)
    assert video.id == "id"
    assert video.item_id == "item_id"
    assert video.url == "sample_data/video_mp4.mp4"
    assert video.width == 320
    assert video.height == 240
    assert video.format == "mp4"
    assert video.num_frames == 209
    assert round(video.fps, 2) == 29.97

    # Test 3: no read
    video = create_video(
        item_id="item_id",
        url=VIDEO_ASSET_URL,
        id="id",
        width=100,
        height=100,
        format="avi",
        num_frames=100,
        fps=30,
        duration=3.33,
    )

    assert isinstance(video, Video)
    assert video.id == "id"
    assert video.item_id == "item_id"
    assert video.url == str(VIDEO_ASSET_URL.as_posix())
    assert video.width == 100
    assert video.height == 100
    assert video.format == "avi"
    assert video.num_frames == 100
    assert video.fps == 30
    assert video.duration == 3.33
