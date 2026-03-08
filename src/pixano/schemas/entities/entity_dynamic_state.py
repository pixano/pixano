# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================
from pixano.utils import issubclass_strict
from ..records import RecordComponent


class EntityDynamicState(RecordComponent):
    """Per-frame dynamic state for an entity.
    This table stores dynamic attributes (occlusion, visibility, pose, ...)
    decoupled from geometric annotations so a single state can be shared by
    BBoxes, masks and keypoints for the same frame.

    Attributes:
        entity_id: ID of the entity.
        tracklet_id: ID of the tracklet for temporal linkage.
        source_id: ID of the annotation source.
        view_id: ID of the view from which the state is derived.
        frame_id: ID of the referenced media row.
        frame_index: Frame index (denormalized for temporal queries).
    """

    entity_id: str = ""
    tracklet_id: str = ""
    source_id: str = ""
    view_id: str = ""
    frame_id: str = ""
    frame_index: int = -1


def is_entity_dynamic_state(cls: type, strict: bool = False) -> bool:
    """Check if a class is an EntityDynamicState or subclass."""
    return issubclass_strict(cls, EntityDynamicState, strict)
