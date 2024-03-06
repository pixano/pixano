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


class SequenceFrame(LanceModel):
    """Sequence Frame Lance Model"""

    id: str
    item_id: str
    sequence_id: str
    timestamp: float
    frame_index: int
    width: int
    height: int
    url: str
    format: str
