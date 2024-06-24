# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2024)
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

from pixano.datasets.features.schemas.registry import _register_schema_internal

from .object import Object


@_register_schema_internal
class TrackObject(Object):
    """Object belonging to a track.

    Attributes:
        tracklet_id (str): tracklet id
        is_key (bbol): True if object is a "key"
        frame_idx (int): frame index
    """
    tracklet_id: str
    is_key: bool
    frame_idx: int
