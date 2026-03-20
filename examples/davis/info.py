# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Dataset info for DAVIS 2017 video object segmentation samples.

Usage:
    pixano data import ./my_data ./davis_sample \
        --info examples/davis/info.py:dataset_info
"""

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import CompressedRLE, Entity, EntityDynamicState, Record, SequenceFrame, Tracklet


class DAVISEntity(Entity):
    """A segmented object in a DAVIS video."""

    category: str = "object"


class DAVISEntityDynamicState(EntityDynamicState):
    """Per-frame dynamic state for a DAVIS entity."""


dataset_info = DatasetInfo(
    name="DAVIS 2017 Sample",
    description="Sample import for DAVIS 2017 video object segmentation data.",
    workspace=WorkspaceType.VIDEO,
    record=Record,
    entity=DAVISEntity,
    entity_dynamic_state=DAVISEntityDynamicState,
    tracklet=Tracklet,
    mask=CompressedRLE,
    views={"image": SequenceFrame},
)
