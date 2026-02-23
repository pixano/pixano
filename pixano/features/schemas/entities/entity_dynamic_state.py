# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.utils import issubclass_strict

from ..base_schema import BaseSchema
from ..registry import _register_schema_internal


@_register_schema_internal
class EntityDynamicState(BaseSchema):
    """Per-frame dynamic state for an entity.

    This table stores dynamic attributes (occlusion, visibility, pose, ...)
    decoupled from geometric annotations so a single state can be shared by
    BBoxes, masks and keypoints for the same frame.
    """

    item_id: str = ""
    entity_id: str = ""
    tracklet_id: str = ""
    source_id: str = ""
    view_name: str = ""
    frame_id: str = ""
    frame_index: int = -1


def is_entity_dynamic_state(cls: type, strict: bool = False) -> bool:
    """Check if a class is an EntityDynamicState or subclass."""
    return issubclass_strict(cls, EntityDynamicState, strict)
