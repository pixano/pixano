# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Default table configurations for common dataset workspaces.

These functions return pre-configured ``tables`` dicts suitable for passing
to :class:`DatasetInfo`.
"""

from lancedb.pydantic import LanceModel

from pixano.schemas import (
    BBox,
    CompressedRLE,
    Entity,
    EntityDynamicState,
    Image,
    KeyPoints,
    Message,
    Record,
    SequenceFrame,
    Tracklet,
)


def default_vqa_tables() -> dict[str, type[LanceModel]]:
    """Return default tables for a VQA dataset."""
    return {
        "records": Record,
        "images": Image,
        "messages": Message,
        "entities": Entity,
        "bboxes": BBox,
        "masks": CompressedRLE,
        "keypoints": KeyPoints,
    }


def default_video_tables() -> dict[str, type[LanceModel]]:
    """Return default tables for a video dataset."""
    return {
        "records": Record,
        "sequence_frames": SequenceFrame,
        "entities": Entity,
        "entity_dynamic_states": EntityDynamicState,
        "tracklets": Tracklet,
        "bboxes": BBox,
        "masks": CompressedRLE,
        "keypoints": KeyPoints,
    }


def default_image_tables() -> dict[str, type[LanceModel]]:
    """Return default tables for an image dataset."""
    return {
        "records": Record,
        "images": Image,
        "entities": Entity,
        "bboxes": BBox,
        "masks": CompressedRLE,
        "keypoints": KeyPoints,
    }
