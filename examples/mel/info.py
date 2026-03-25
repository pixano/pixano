# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Dataset info for MEL image-text entity-linking samples.

Usage:
    pixano data import ./my_data ./mel_source \
        --info examples/mel/info.py:dataset_info
"""

from pixano.datasets import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, CompressedRLE, Entity, Image, Record, Text, TextSpan


class MELEntity(Entity):
    """Entity linked across image regions and text spans."""

    name: str = ""


dataset_info = DatasetInfo(
    name="MEL Sample",
    description="Sample import for image-text entity linking datasets.",
    workspace=WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
    record=Record,
    entity=MELEntity,
    bbox=BBox,
    mask=CompressedRLE,
    text_span=TextSpan,
    views={"image": Image, "text": Text},
)
