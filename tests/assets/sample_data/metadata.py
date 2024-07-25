# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path


ASSETS_DIRECTORY = Path(__file__).parent.parent.parent / "assets"
IMAGE_JPG_ASSET_URL = ASSETS_DIRECTORY / "sample_data/image_jpg.jpg"
IMAGE_PNG_ASSET_URL = ASSETS_DIRECTORY / "sample_data/image_png.png"
VIDEO_MP4_ASSET_URL = ASSETS_DIRECTORY / "sample_data/video_mp4.mp4"
SAMPLE_DATA_PATHS = {
    "image_jpg": IMAGE_JPG_ASSET_URL,
    "image_png": IMAGE_PNG_ASSET_URL,
    "video_mp4": VIDEO_MP4_ASSET_URL,
}

IMAGE_JPG_METADATA = dict(
    width=586,
    height=640,
    format="JPEG",
)

IMAGE_PNG_METADATA = dict(
    width=640,
    height=426,
    format="PNG",
)

VIDEO_MP4_METADATA = dict(
    width=320,
    height=240,
    format="mp4",
    num_frames=209,
    fps=29.97,  # rounded
    duration=6.97,  # rounded
)
