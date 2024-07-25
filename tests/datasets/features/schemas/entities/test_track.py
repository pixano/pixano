# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from pydantic import ValidationError

from pixano.datasets.features import Track, create_track, is_track
from pixano.datasets.features.types.schema_reference import EntityRef, ItemRef, ViewRef
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_track():
    make_tests_is_sublass_strict(is_track, Track)


def test_create_track():
    # Test 1: Default references
    track = create_track(
        name="name",
    )

    assert isinstance(track, Track)
    assert track.name == "name"
    assert track.id == ""
    assert track.item_ref == ItemRef.none()
    assert track.view_ref == ViewRef.none()
    assert track.parent_ref == EntityRef.none()

    # Test 2: Custom references
    track_object = create_track(
        name="name",
        id="id",
        item_ref=ItemRef(id="item_id"),
        view_ref=ViewRef(id="view_id", name="view"),
        parent_ref=EntityRef(id="entity_id", name="entity"),
    )

    assert isinstance(track_object, Track)
    assert track_object.name == "name"
    assert track_object.id == "id"
    assert track_object.item_ref == ItemRef(id="item_id")
    assert track_object.view_ref == ViewRef(id="view_id", name="view")
    assert track_object.parent_ref == EntityRef(id="entity_id", name="entity")
