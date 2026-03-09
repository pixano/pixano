# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
from pathlib import Path
import shortuuid
from pixano.utils import issubclass_strict
from .view import View


class Video(View):
    """Video view.

    Attributes:
        num_frames: The number of frames in the video.
        fps: The frames per second of the video.
        width: The video width.
        height: The video height.
        format: The video format.
        duration: The video duration.
    """

    num_frames: int
    fps: float
    width: int
    height: int
    format: str
    duration: float


def is_video(cls: type, strict: bool = False) -> bool:
    """Check if the given class is a `Video` or a subclass of `Video`."""
    return issubclass_strict(cls, Video, strict)


def create_video(
    uri: Path,
    id: str = "",
    record_id: str = "",
    logical_name: str = "",
    num_frames: int | None = None,
    fps: float | None = None,
    width: int | None = None,
    height: int | None = None,
    format: str | None = None,
    duration: float | None = None,
    preview: bytes = b"",
    preview_format: str = "",
) -> Video:
    """Create a `Video` instance.

    Args:
        uri: The video URI (absolute path or remote URI).
        id: Video ID.
        record_id: Record ID.
        logical_name: Logical view name (e.g. "front_camera").
        num_frames: The number of frames in the video. If None, the number of frames is
            extracted from the video file.
        fps: The frames per second of the video. If None, the fps is extracted from the video
            file.
        width: The video width. If None, the width is extracted from the video file.
        height: The video height. If None, the height is extracted from the video file.
        format: The video format. If None, the format is extracted from the video file.
        duration: The video duration. If None, the duration is extracted from the video file.
        preview: Thumbnail/preview bytes.
        preview_format: Preview format (e.g. "jpeg", "png").

    Returns:
        The created `Video` instance.
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
    uri = Path(uri)
    if id is None:
        id = shortuuid.uuid()
    if width is None:
        try:
            import ffmpeg
        except ImportError:
            raise ImportError("To load video files metadata, install ffmpeg")
        try:
            metadata = ffmpeg.probe(str(uri.resolve()), cmd="ffprobe")["streams"][0]
        except FileNotFoundError:
            raise FileNotFoundError("File not found or ffprobe is not installed.")
        r_frame_rate = metadata["r_frame_rate"].split("/")
        fps = float(r_frame_rate[0]) / float(r_frame_rate[1])
        num_frames = int(metadata["nb_frames"])
        width = int(metadata["width"])
        height = int(metadata["height"])
        format = uri.suffix[1:]
        duration = float(metadata["duration"])
    return Video(
        id=id,
        record_id=record_id,
        logical_name=logical_name,
        uri=uri.as_posix(),
        num_frames=num_frames,
        fps=fps,
        width=width,
        height=height,
        format=format,
        duration=duration,
        preview=preview,
        preview_format=preview_format,
    )
