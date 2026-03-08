# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
from pixano.utils import issubclass_strict

from .entity_annotation import EntityAnnotation


class PerFrameAnnotation(EntityAnnotation):
    """Per-frame annotations carry temporal linkage fields.
    Used by BBox, CompressedRLE, KeyPoints, etc. — annotations that
    reference a specific frame within a video sequence.
    Attributes:
        tracklet_id: ID of the tracklet for temporal linkage.
        entity_dynamic_state_id: ID of the entity dynamic state row.
        frame_id: ID of the referenced media row when annotation is frame-level.
        frame_index: Frame index (denormalized for temporal queries).
    """
    tracklet_id: str = ""
    entity_dynamic_state_id: str = ""
    frame_id: str = ""
    frame_index: int = -1

def is_per_frame_annotation(cls: type, strict: bool = False) -> bool:
    """Check if a class is a PerFrameAnnotation or subclass of PerFrameAnnotation."""
    return issubclass_strict(cls, PerFrameAnnotation, strict)
