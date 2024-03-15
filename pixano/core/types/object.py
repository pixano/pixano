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


from lancedb.pydantic import LanceModel

from . import bbox, compressed_rle
from .registry import _register_table_type_internal


@_register_table_type_internal()
class Object(LanceModel):
    """Object Lance Model."""

    id: str
    item_id: str
    view_id: str

    class Config:  # noqa: D106
        extra = "ignore"


class ObjectWithBBox(Object):
    """Object with Bounding Box Lance Model."""

    bbox: bbox.BBox


class ObjectWithMask(Object):
    """Object with Mask Lance Model."""

    mask: compressed_rle.CompressedRLE


class ObjectWithBBoxAndMask(Object):
    """Object with Bounding Box and Mask Lance Model."""

    bbox: bbox.BBox
    mask: compressed_rle.CompressedRLE
