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


from .base_schema import BaseSchema
from .image import Image
from .registry import register_schema
from .sequence_frame import SequenceFrame
from .video import Video
from .view import View
from .embedding import Embedding
from .item import Item
from .point_cloud import PointCloud
from .object import Object, ObjectWithBBox, ObjectWithBBoxAndMask, ObjectWithMask

__all__ = [
    'BaseSchema',
    'Image',
    'Embedding',
    'Item',
    'PointCloud',
    'register_schema',
    'SequenceFrame',
    'Video',
    'View',
    'Object',
    'ObjectWithBBox',
    'ObjectWithBBoxAndMask',
    'ObjectWithMask',
]