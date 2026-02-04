# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Dataset schema for VQAv2 samples.

Usage:
    pixano data import ./my_data ./vqav2_sample \
        --name "VQAv2 Sample" --type vqa --schema ./examples/vqav2/schema.py:VQAv2DatasetItem
"""

from pixano.datasets.workspaces import DefaultVQADatasetItem
from pixano.features import Entity


class ObjectEntity(Entity):
    """Custom entity for object annotation with category and occlusion info."""

    category: str = ""
    subcategory: str = ""
    is_occluded: bool = False


class VQAv2DatasetItem(DefaultVQADatasetItem):
    """Dataset item for VQAv2 with object annotation support."""

    objects: list[ObjectEntity]
