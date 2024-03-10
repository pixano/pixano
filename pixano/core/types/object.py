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

from pixano.core import BBox, CompressedRLE

from .registry import _register_table_type_internal

@_register_table_type_internal()
class Object(LanceModel):
    """Object Lance Model"""

    id: str
    item_id: str
    view_id: str
    track_id: str
    timestamp: float
    bbox: BBox
    mask: CompressedRLE
