# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Dataset info for FLIR ADAS v2 multi-view samples (RGB + thermal).

Usage:
    pixano data import ./my_data ./flir_sample \
        --info examples/flir/schema.py:dataset_info
    pixano data import ./my_data ./flir_sample \
        --info examples/flir/schema.py:video_dataset_info
"""

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, Entity, EntityDynamicState, Image, Record, SequenceFrame, Tracklet


class FLIREntity(Entity):
    """An object detected in a FLIR thermal image."""

    category: str = ""


class FLIREntityDynamicState(EntityDynamicState):
    """Per-frame dynamic state for a FLIR entity."""


dataset_info = DatasetInfo(
    name="FLIR Static Sample",
    description="Sample import for FLIR static image pairs.",
    workspace=WorkspaceType.IMAGE,
    record=Record,
    entity=FLIREntity,
    bbox=BBox,
    views={"rgb": Image, "thermal": Image},
)

video_dataset_info = DatasetInfo(
    name="FLIR Dynamic Sample",
    description="Sample import for FLIR dynamic synchronized frame sequences.",
    workspace=WorkspaceType.VIDEO,
    record=Record,
    entity=FLIREntity,
    entity_dynamic_state=FLIREntityDynamicState,
    tracklet=Tracklet,
    bbox=BBox,
    views={"rgb": SequenceFrame, "thermal": SequenceFrame},
)
