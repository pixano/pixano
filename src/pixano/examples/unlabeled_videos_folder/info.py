# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Dataset info for unlabeled video samples.

Usage:
    pixano data import ./my_data ./unlabeled_videos_sample \
        --info examples/unlabeled_videos_folder/info.py:dataset_info
"""

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import CompressedRLE, Entity, EntityDynamicState, Record, SequenceFrame, Tracklet


class VIDEOEntity(Entity):
    """An object in an unlabeled video."""

    category: str = ""
    sub_category: str = ""
    is_occluded: bool = False
    custom_value: float = 0.0


class VIDEOEntityDynamicState(EntityDynamicState):
    """Per-frame dynamic state for a VIDEO entity."""


dataset_info = DatasetInfo(
    name="VIDEO Sample",
    description="Sample import for unlabeled videos.",
    workspace=WorkspaceType.VIDEO,
    record=Record,
    entity=VIDEOEntity,
    entity_dynamic_state=VIDEOEntityDynamicState,
    tracklet=Tracklet,
    mask=CompressedRLE,
    views={"image": SequenceFrame},
)
