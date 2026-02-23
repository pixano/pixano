# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Dataset schema for FLIR ADAS v2 multi-view samples (RGB + thermal).

Usage:
    pixano data import ./my_data ./flir_sample \
        --name "FLIR ADAS Sample" --schema examples/flir/schema.py:FLIRDatasetItem
"""

from pixano.datasets.dataset_schema import DatasetItem
from pixano.features import Entity, EntityDynamicState, Image, SequenceFrame, Tracklet
from pixano.features.schemas.annotations.bbox import BBox


class FLIRObject(Entity):
    """An object detected in a FLIR thermal image."""

    category: str = ""


class FLIRDatasetItem(DatasetItem):
    """Dataset item for FLIR ADAS v2 with RGB and thermal views."""

    rgb_image: Image
    thermal_image: Image
    entities: list[FLIRObject]
    bboxes: list[BBox]


class FLIRVideoObject(Entity):
    """A tracked object across frames in FLIR video sequences."""

    category: str = ""


class FLIRVideoObjectState(EntityDynamicState):
    """Per-frame dynamic state for a FLIR object."""


class FLIRVideoDatasetItem(DatasetItem):
    """Dataset item for FLIR ADAS v2 multi-view video."""

    rgb_image: list[SequenceFrame]
    thermal_image: list[SequenceFrame]
    entities: list[FLIRVideoObject]
    entity_dynamic_states: list[FLIRVideoObjectState]
    tracklets: list[Tracklet]
    bboxes: list[BBox]
