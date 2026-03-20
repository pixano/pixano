# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from pydantic import ValidationError

from pixano.features import Tracklet, is_tracklet
from tests.features.utils import make_tests_is_sublass_strict


def test_is_tracklet():
    make_tests_is_sublass_strict(is_tracklet, Tracklet)


def test_tracklet_init():
    # Test 1: Default references
    tracklet = Tracklet(
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
    assert tracklet.record_id == ""
    assert tracklet.entity_id == ""

    # Test 2: Custom references
    tracklet = Tracklet(
        start_timestamp=1.0,
        end_timestamp=2.0,
        start_timestep=1,
        end_timestep=2,
        id="id",
        record_id="record_id",
        entity_id="track_id",
    )

    assert isinstance(tracklet, Tracklet)
    assert tracklet.start_timestamp == 1.0
    assert tracklet.end_timestamp == 2.0
    assert tracklet.start_timestep == 1
    assert tracklet.end_timestep == 2
    assert tracklet.id == "id"
    assert tracklet.record_id == "record_id"
    assert tracklet.entity_id == "track_id"


@pytest.mark.parametrize(
    "start_timestep, end_timestep, start_timestamp, end_timestamp, match",
    [
        (2, 1, -1.0, -1.0, "start_frame must be less than or equal to end_frame."),
        (-1, -1, 2.0, 1.0, "start_timestamp must be less than or equal to end_timestamp."),
        (-1, 1, -1.0, -1.0, "start_frame must be set if end_frame is set."),
        (1, -1, -1.0, -1.0, "end_frame must be set if start_frame is set."),
        (-1, -1, -1.0, 1.0, "start_timestamp must be set if end_timestamp is set."),
        (-1, -1, 1.0, -1.0, "end_timestamp must be set if start_timestamp is set."),
        (
            -1,
            -1,
            -2.0,
            -1.0,
            "start_frame, end_frame, start_timestamp, and end_timestamp must be greater than or equal to -1.",
        ),
        (
            -1,
            -1,
            -1.0,
            -2.0,
            "start_frame, end_frame, start_timestamp, and end_timestamp must be greater than or equal to -1.",
        ),
        (
            -2,
            -1,
            -1.0,
            -1.0,
            "start_frame, end_frame, start_timestamp, and end_timestamp must be greater than or equal to -1.",
        ),
        (
            -1,
            -2,
            -1.0,
            -1.0,
            "start_frame, end_frame, start_timestamp, and end_timestamp must be greater than or equal to -1.",
        ),
    ],
)
def test_invalid_tracklet(start_timestep, end_timestep, start_timestamp, end_timestamp, match):
    with pytest.raises(ValidationError, match=match):
        Tracklet(
            start_timestamp=start_timestamp,
            end_timestamp=end_timestamp,
            start_timestep=start_timestep,
            end_timestep=end_timestep,
        )
