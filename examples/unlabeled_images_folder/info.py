# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Dataset info for unlabeled images samples.

Usage:
    pixano data import ./my_data ./voc_sample \
        --info examples/unlabeled_images_folder/info.py:dataset_info
"""

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import Entity, Image, Record


class IMAGEEntity(Entity):
    """An object in an unlabeled image."""

    category: str = ""
    sub_category: str = ""
    is_occluded: bool = False
    custom_value: float = 0.0


dataset_info = DatasetInfo(
    name="IMAGE Sample",
    description="Sample import for unlabeled images.",
    workspace=WorkspaceType.IMAGE,
    record=Record,
    entity=IMAGEEntity,
    views={"image": Image},
)
