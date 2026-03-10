# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Dataset info for VQAv2 samples.

Usage:
    pixano data import ./my_data ./vqav2_sample \
        --info ./examples/vqav2/info.py:dataset_info
"""

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, CompressedRLE, Entity, Image, Message, Record


class VQAv2Entity(Entity):
    """Custom entity for VQAv2 annotation with category and subcategory."""

    category: str = ""
    subcategory: str = ""


dataset_info = DatasetInfo(
    name="VQAv2 Sample",
    description="Sample import for VQAv2 visual question answering data.",
    workspace=WorkspaceType.IMAGE_VQA,
    record=Record,
    entity=VQAv2Entity,
    message=Message,
    bbox=BBox,
    mask=CompressedRLE,
    views={"image": Image},
)
