# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.track_object import TrackObject, create_track_object, is_track_object
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_image():
    make_tests_is_sublass_strict(is_track_object, TrackObject)


def test_create_track_object():
    # Test 1: Default values
    track_object = create_track_object(
        item_id="item_id",
        view_id="view_id",
        tracklet_id="tracklet_id",
        is_key=True,
        frame_idx=1,
    )

    assert isinstance(track_object, TrackObject)
    assert track_object.item_id == "item_id"
    assert track_object.view_id == "view_id"
    assert track_object.tracklet_id == "tracklet_id"
    assert track_object.is_key
    assert track_object.frame_idx == 1
    assert isinstance(track_object.id, str)

    # Test 2: Custom values
    track_object = create_track_object(
        item_id="item_id",
        view_id="view_id",
        tracklet_id="tracklet_id",
        is_key=False,
        frame_idx=2,
        id="id",
    )

    assert isinstance(track_object, TrackObject)
    assert track_object.item_id == "item_id"
    assert track_object.view_id == "view_id"
    assert track_object.tracklet_id == "tracklet_id"
    assert not track_object.is_key
    assert track_object.frame_idx == 2
    assert track_object.id == "id"
