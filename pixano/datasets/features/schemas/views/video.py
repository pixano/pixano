# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import shortuuid

from pixano.datasets.utils import issubclass_strict

from ...types.schema_reference import ItemRef, ViewRef
from ..registry import _register_schema_internal
from .view import View


@_register_schema_internal
class Video(View):
    """Video Lance Model."""

    url: str
    num_frames: int
    fps: float
    width: int
    height: int
    format: str
    duration: float


def is_video(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a Video or a subclass of Video."""
    return issubclass_strict(cls, Video, strict)


def create_video(
    url: Path,
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    parent_ref: ViewRef = ViewRef.none(),
    num_frames: int | None = None,
    fps: float | None = None,
    width: int | None = None,
    height: int | None = None,
    format: str | None = None,
    duration: float | None = None,
    other_path: Path | None = None,
) -> Video:
    """Create a Video instance.

    Args:
        url (Path): The image URL. If not relative, the URL is converted to a relative path using `other_path`.
        id (str, optional): Point cloud ID.
        item_ref (ItemRef, optional): Item reference.
        parent_ref (ViewRef, optional): Parent view reference.
        num_frames (int | None, optional): The number of frames in the video. If None, the number of frames is
            extracted from the video file.
        fps (float | None, optional): The frames per second of the video. If None, the fps is extracted from the video
            file.
        width (int | None, optional): The video width. If None, the width is extracted from the video file.
        height (int | None, optional): The video height. If None, the height is extracted from the video file.
        format (str | None, optional): The video format. If None, the format is extracted from the video file.
        duration (float | None, optional): The video duration. If None, the duration is extracted from the video file.
        other_path (Path | None, optional): The path to convert the URL to a relative path.

    Returns:
        Video: The created Video instance.
    """
    none_conditions = [
        num_frames is None,
        fps is None,
        width is None,
        height is None,
        format is None,
        duration is None,
    ]
    not_none_conditions = [
        num_frames is not None,
        fps is not None,
        width is not None,
        height is not None,
        format is not None,
        duration is not None,
    ]
    if not all(none_conditions) and not all(not_none_conditions):
        raise ValueError(
            "All or none of the following arguments must be provided: width, height, format, num_frames, fps, duration"
        )

    url = Path(url)
    if id is None:
        id = shortuuid.uuid()

    if width is None:
        try:
            import ffmpeg
        except ImportError:
            raise ImportError("To load video files metadata, install ffmpeg")
        try:
            metadata = ffmpeg.probe(str(url.resolve()), cmd="ffprobe")["streams"][0]
        except FileNotFoundError:
            raise FileNotFoundError("File not found or ffprobe is not installed.")
        r_frame_rate = metadata["r_frame_rate"].split("/")
        fps = float(r_frame_rate[0]) / float(r_frame_rate[1])
        num_frames = int(metadata["nb_frames"])
        width = int(metadata["width"])
        height = int(metadata["height"])
        format = url.suffix[1:]
        duration = float(metadata["duration"])

    if other_path is not None:
        other_path = Path(other_path)
        url = url.relative_to(other_path)

    return Video(
        id=id,
        item_ref=item_ref,
        parent_ref=parent_ref,
        url=url.as_posix(),
        num_frames=num_frames,
        fps=fps,
        width=width,
        height=height,
        format=format,
        duration=duration,
    )
