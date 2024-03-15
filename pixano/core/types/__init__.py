# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info


import pydantic

from pixano.core.types.image import Image
from pixano.core.types.item import Item, ViewRecords
from pixano.core.types.registry import register_table_type
from pixano.core.types.sequence_frame import SequenceFrame

from .bbox import BBox
from .object import Object, ObjectWithBBox, ObjectWithBBoxAndMask, ObjectWithMask

DataSchema = pydantic.BaseModel

__all__ = [
    "DataSchema",
    "BBox",
    "Item",
    "Object",
    "ObjectWithBBox",
    "ObjectWithMask",
    "ObjectWithBBoxAndMask",
    "ViewRecords",
    "Image",
    "SequenceFrame",
    "register_table_type",
]
