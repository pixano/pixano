# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from pydantic import ValidationError

from pixano.datasets.features import Tracklet, create_tracklet, is_tracklet
from pixano.datasets.features.types.schema_reference import EntityRef, ItemRef, ViewRef
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_tracklet():
    make_tests_is_sublass_strict(is_tracklet, Tracklet)


def test_create_tracklet():
    # Test 1: Default references
    tracklet = create_tracklet(
        start_timestamp=1.0,
        end_timestamp=2.0,
        start_timestep=3,
        end_timestep=4,
    )

    assert isinstance(tracklet, Tracklet)
    assert tracklet.start_timestamp == 1.0
    assert tracklet.end_timestamp == 2.0
    assert tracklet.start_timestep == 3
    assert tracklet.end_timestep == 4
    assert tracklet.id == ""
    assert tracklet.item_ref == ItemRef.none()
    assert tracklet.view_ref == ViewRef.none()
    assert tracklet.entity_ref == EntityRef.none()

    # Test 2: Custom references
    tracklet = create_tracklet(
        start_timestamp=1.0,
        end_timestamp=2.0,
        start_timestep=1,
        end_timestep=2,
        id="id",
        item_ref=ItemRef(id="item_id"),
        view_ref=ViewRef(id="view_id", name="view"),
        entity_ref=EntityRef(id="track_id", name="track"),
    )

    assert isinstance(tracklet, Tracklet)
    assert tracklet.start_timestamp == 1.0
    assert tracklet.end_timestamp == 2.0
    assert tracklet.start_timestep == 1
    assert tracklet.end_timestep == 2
    assert tracklet.id == "id"
    assert tracklet.item_ref == ItemRef(id="item_id")
    assert tracklet.view_ref == ViewRef(id="view_id", name="view")
    assert tracklet.entity_ref == EntityRef(id="track_id", name="track")


@pytest.mark.parametrize(
    "start_timestep, end_timestep, start_timestamp, end_timestamp, match",
    [
        (2, 1, -1.0, -1.0, "start_timestep must be less than or equal to end_timestep."),
        (-1, -1.0, 2.0, 1.0, "start_timestamp must be less than or equal to end_timestamp."),
        (
            -1,
            -1,
            -1.0,
            -1.0,
            "At least one of start_timestep, end_timestep, start_timestamp, or end_timestamp must be set.",
        ),
        (-1, 1, -1.0, -1.0, "start_timestep must be set if end_timestep is set."),
        (1, -1, -1.0, -1.0, "end_timestep must be set if start_timestep is set."),
        (-1, -1, -1.0, 1.0, "start_timestamp must be set if end_timestamp is set."),
        (-1, -1, 1.0, -1.0, "end_timestamp must be set if start_timestamp is set."),
        (-1, -1, -2.0, -1.0, "start_timestamp, and end_timestamp must be greater than or equal to -1."),
        (-1, -1, -1.0, -2.0, "start_timestamp, and end_timestamp must be greater than or equal to -1."),
        (-2, -1, -1.0, -1.0, "start_timestamp, and end_timestamp must be greater than or equal to -1."),
        (-1, -2, -1.0, -1.0, "start_timestamp, and end_timestamp must be greater than or equal to -1."),
        (-1, -1, -2.0, -1.0, "start_timestamp, and end_timestamp must be greater than or equal to -1."),
        (-1, -1, -1.0, -2.0, "start_timestamp, and end_timestamp must be greater than or equal to -1."),
    ],
)
def test_invalid_create_tracklet(start_timestamp, end_timestamp, start_timestep, end_timestep, match):
    with pytest.raises(ValidationError, match=match):
        create_tracklet(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            start_timestep=start_timestep,
            end_timestep=end_timestep,
        )
