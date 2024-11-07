# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from typing import Iterable


def create_video_preview(path: Path, frame_urls: Iterable[str], fps: int = 25, scale: float = 0.5):
    """Create a video preview by writing a sequence of frames to a video file.

    Args:
        path: The path to the output video file.
        frame_urls: URLs pointing to the frames of the video.
        fps: The frames per second of the output video.
        scale: The scale factor to resize the frames.
    """
    # Import mediapy only when needed to avoid unnecessary dependencies.
    import mediapy

    frames = [mediapy.read_image(url) for url in frame_urls]

    if scale < 1:
        size = frames[0].shape[:2]
        target_size = (int(size[0] * scale), int(size[1] * scale))
        frames = mediapy.resize_video(frames, target_size)

    mediapy.write_video(path, frames, fps=fps)
