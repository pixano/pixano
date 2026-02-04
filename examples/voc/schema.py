# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Dataset schema for Pascal VOC 2007 samples.

Usage:
    pixano data import ./my_data ./voc_sample \
        --name "VOC 2007 Sample" --schema ./notebooks/voc_schema.py:VOCDatasetItem
"""

from pixano.datasets.workspaces import DefaultImageDatasetItem
from pixano.features import Entity


class VOCObject(Entity):
    """An object detected in a VOC image."""

    category: str = ""
    is_difficult: bool = False


class VOCDatasetItem(DefaultImageDatasetItem):
    """Dataset item for Pascal VOC with category and difficulty flag."""

    objects: list[VOCObject]
