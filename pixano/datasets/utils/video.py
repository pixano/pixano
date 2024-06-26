# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from os import PathLike
from typing import Iterable

import mediapy


def create_video_preview(
    path: PathLike, frame_urls: Iterable[str], fps: int = 25, scale: float = 0.5
):
    """Create a video preview by writing a sequence of frames to a video file.

    Args:
        path (PathLike): The path to the output video file.
        frame_urls (Iterable[str]): URLs pointing to the frames of the video.
        fps (int, optional): The frames per second of the output video. Defaults to 25.
        scale (float, optional): The scale factor to resize the frames. Defaults to 0.5.
    """
    frames = [mediapy.read_image(url) for url in frame_urls]

    if scale < 1:
        size = frames[0].shape[:2]
        target_size = (int(size[0] * scale), int(size[1] * scale))
        frames = mediapy.resize_video(frames, target_size)

    mediapy.write_video(path, frames, fps=fps)
