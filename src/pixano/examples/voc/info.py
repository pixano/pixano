# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Dataset info for Pascal VOC 2007 samples.

Usage:
    pixano data import ./my_data ./voc_sample \
        --info examples/voc/info.py:dataset_info
"""

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, Entity, Image, Record


class VOCEntity(Entity):
    """An object detected in a VOC image."""

    category: str = ""
    is_difficult: bool = False


dataset_info = DatasetInfo(
    name="VOC 2007 Sample",
    description="Sample import for Pascal VOC 2007 object detection data.",
    workspace=WorkspaceType.IMAGE,
    record=Record,
    entity=VOCEntity,
    bbox=BBox,
    views={"image": Image},
)
