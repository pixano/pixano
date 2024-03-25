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


from .image import Image
from .registry import _register_schema_internal


@_register_schema_internal
class SequenceFrame(Image):
    """Sequence Frame Lance Model."""

    sequence_id: str
    timestamp: float
    frame_index: int


def is_sequence_frame(cls: type) -> bool:
    """Check if the given class is a subclass of Sequence."""
    return cls is SequenceFrame
