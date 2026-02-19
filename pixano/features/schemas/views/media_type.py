# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Media-type table routing utility.

Maps View subclasses to their fixed media-type table names.
Each media type has a single table with column-per-view layout.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .image import Image, is_image
from .pdf import PDF, is_pdf
from .point_cloud import PointCloud, is_point_cloud
from .sequence_frame import SequenceFrame, is_sequence_frame
from .text import Text, is_text
from .video import Video, is_video


if TYPE_CHECKING:
    from .view import View

# Fixed media-type table names and associated view types
MEDIA_TYPE_TABLES: dict[str, tuple[type, ...]] = {
    "images": (Image,),
    "frames": (SequenceFrame,),
    "point_clouds": (PointCloud,),
    "texts": (Text,),
    "pdfs": (PDF,),
    "videos": (Video,),
}


def get_media_type_table(view_type: type["View"]) -> str:
    """Map a View subclass to its media-type table name.

    Note: SequenceFrame is checked before Image since SequenceFrame inherits from Image.
    Video is checked before Image since Video may store metadata only.

    Args:
        view_type: The View subclass to map.

    Returns:
        The media-type table name.

    Raises:
        ValueError: If the view type is not recognized.
    """
    # Order matters: SequenceFrame before Image (since SequenceFrame is a subclass of Image)
    if is_video(view_type):
        return "videos"
    elif is_sequence_frame(view_type):
        return "frames"
    elif is_image(view_type):
        return "images"
    elif is_point_cloud(view_type):
        return "point_clouds"
    elif is_text(view_type):
        return "texts"
    elif is_pdf(view_type):
        return "pdfs"
    raise ValueError(f"Unknown view type: {view_type}")
