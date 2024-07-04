# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.features.schemas.tracklet import Tracklet, create_tracklet, is_tracklet
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_image():
    make_tests_is_sublass_strict(is_tracklet, Tracklet)


def test_create_tracklet():
    # Test 1: Default values
    tracklet = create_tracklet(
        item_id="item_id",
        track_id="track_id",
        start_timestamp=1.,
        end_timestamp=2.,
    )

    assert isinstance(tracklet, Tracklet)
    assert tracklet.item_id == "item_id"
    assert isinstance(tracklet.id, str)
    assert tracklet.start_timestamp == 1.0
    assert tracklet.end_timestamp == 2.0
    assert tracklet.start_timestep == -1
    assert tracklet.end_timestep == -1

    # Test 2: Custom values
    tracklet = create_tracklet(
        item_id="item_id",
        track_id="track_id",
        id="id",
        start_timestamp=1.0,
        end_timestamp=2.0,
        start_timestep=1,
        end_timestep=2,
    )

    assert isinstance(tracklet, Tracklet)
    assert tracklet.item_id == "item_id"
    assert tracklet.track_id == "track_id"
    assert tracklet.id == "id"
    assert tracklet.start_timestamp == 1.0
    assert tracklet.end_timestamp == 2.0
    assert tracklet.start_timestep == 1
    assert tracklet.end_timestep == 2


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
    with pytest.raises(ValueError, match=match):
        create_tracklet(
            item_id="item_id",
            track_id="track_id",
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            start_timestep=start_timestep,
            end_timestep=end_timestep,
        )
