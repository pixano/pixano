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
from pixano.features import Entity, Image
from pixano.features.schemas.annotations.bbox import BBox


class FLIRObject(Entity):
    """An object detected in a FLIR thermal image."""

    category: str = ""


class FLIRDatasetItem(DatasetItem):
    """Dataset item for FLIR ADAS v2 with RGB and thermal views."""

    rgb_image: Image
    thermal_image: Image
    objects: list[FLIRObject]
    bboxes: list[BBox]
