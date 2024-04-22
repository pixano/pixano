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

from .base_schema import BaseSchema


@_register_schema_internal
class Tracklet(BaseSchema):
    """Tracklet Lance Model."""

    track_id: str


class TrackletWithTimestep(Tracklet):
    """Tracklet with Timestep Lance Model."""

    start_timestep: int
    end_timestep: int


class TrackletWithTimestamp(Tracklet):
    """Tracklet with Timestamp Lance Model."""

    start_timestamp: int
    end_timestamp: int


class TrackletWithTimestepAndTimestamp(Tracklet):
    """Tracklet with Timestep and Timestamp Lance Model."""

    start_timestep: int
    end_timestep: int
    start_timestamp: int
    end_timestamp: int
