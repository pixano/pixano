# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.dataset_schema import DatasetItem
from pixano.features import CompressedRLE, Entity, EntityDynamicState, SequenceFrame, Tracklet


class DAVISEntity(Entity):
    """A segmented object in a DAVIS video."""

    category: str = "object"


class DAVISEntityDynamicState(EntityDynamicState):
    """Per-frame dynamic state for a DAVIS entity."""


class DAVISDatasetItem(DatasetItem):
    """Schema v2 DAVIS item with entities, states, tracklets and masks."""

    frames: list[SequenceFrame]
    entities: list[DAVISEntity]
    entity_dynamic_states: list[DAVISEntityDynamicState]
    tracklets: list[Tracklet]
    masks: list[CompressedRLE]
