# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Unit tests for pure helper functions in the views router."""

from collections.abc import Sequence
from unittest.mock import MagicMock

import pytest

from pixano.api.routers.views import (
    CALIBRATED_IMAGE_TABLE,
    IMAGE_TABLE,
    _combine_where,
    _resolve_image_table,
    _to_point_cloud_response,
)
from pixano.schemas.schema_group import SchemaGroup


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _make_dataset(view_tables: set[str]) -> MagicMock:
    """Return a minimal mock Dataset whose info.groups contains the given VIEW tables."""
    dataset = MagicMock()
    dataset.info.groups = {SchemaGroup.VIEW: view_tables}
    return dataset


# ─── _resolve_image_table ─────────────────────────────────────────────────────


class TestResolveImageTable:
    def test_returns_images_when_no_calibrated_images(self):
        dataset = _make_dataset({"images"})
        assert _resolve_image_table(dataset) == IMAGE_TABLE

    def test_returns_calibrated_images_when_present(self):
        dataset = _make_dataset({"calibrated_images"})
        assert _resolve_image_table(dataset) == CALIBRATED_IMAGE_TABLE

    def test_calibrated_images_takes_precedence_when_both_present(self):
        dataset = _make_dataset({"images", "calibrated_images"})
        assert _resolve_image_table(dataset) == CALIBRATED_IMAGE_TABLE

    def test_returns_images_when_view_tables_is_empty(self):
        dataset = _make_dataset(set())
        assert _resolve_image_table(dataset) == IMAGE_TABLE

    def test_returns_images_when_view_group_absent(self):
        dataset = MagicMock()
        dataset.info.groups = {}
        assert _resolve_image_table(dataset) == IMAGE_TABLE

    def test_table_constants_have_expected_values(self):
        assert IMAGE_TABLE == "images"
        assert CALIBRATED_IMAGE_TABLE == "calibrated_images"


# ─── _combine_where ───────────────────────────────────────────────────────────


class TestCombineWhere:
    def test_returns_none_when_all_clauses_are_none(self):
        assert _combine_where(None, None) is None

    def test_returns_none_with_no_arguments(self):
        assert _combine_where() is None

    def test_returns_single_clause_unchanged(self):
        assert _combine_where("a = 1") == "a = 1"

    def test_joins_two_clauses_with_and(self):
        assert _combine_where("a = 1", "b = 2") == "a = 1 AND b = 2"

    def test_joins_three_clauses(self):
        assert _combine_where("a = 1", "b = 2", "c = 3") == "a = 1 AND b = 2 AND c = 3"

    def test_skips_none_clauses_in_mixed_list(self):
        assert _combine_where(None, "b = 2", None) == "b = 2"

    def test_skips_none_among_multiple_valid_clauses(self):
        assert _combine_where("a = 1", None, "c = 3") == "a = 1 AND c = 3"

    def test_returns_none_for_empty_strings(self):
        # Empty string is falsy — treated the same as None
        assert _combine_where("", None) is None

    def test_returns_none_when_all_are_empty_strings(self):
        assert _combine_where("", "") is None


# ─── _to_point_cloud_response ─────────────────────────────────────────────────


def _make_point_cloud_row(**extra) -> MagicMock:
    """A point-cloud row carrying only the base View columns, plus any extras."""
    # `spec` matters: a bare MagicMock answers every getattr with a new mock, so
    # the "plain PointCloud row" cases below would silently pass on a truthy
    # stub instead of on a genuinely absent column.
    row = MagicMock(spec=["id", "record_id", "logical_name", "uri", *extra])
    row.id = "pcd-1"
    row.record_id = "rec-1"
    row.logical_name = "LIDAR_TOP"
    row.uri = ""
    for name, value in extra.items():
        setattr(row, name, value)
    return row


class TestToPointCloudResponse:
    def test_serves_a_blob_url_when_the_row_has_no_uri(self):
        response = _to_point_cloud_response("ds-1", _make_point_cloud_row())
        assert response.src == "/datasets/ds-1/point-clouds/pcd-1/blob"

    def test_leaves_the_pose_unset_for_a_plain_point_cloud(self):
        # A `PointCloud` table has no extrinsics; the field must read as absent
        # rather than as an empty matrix a caller might try to apply.
        response = _to_point_cloud_response("ds-1", _make_point_cloud_row())
        assert response.extrinsic_matrix is None
        assert response.ego_to_world is None

    def test_exposes_the_sensor_pose_of_a_calibrated_point_cloud(self):
        world_to_sensor = [float(i) for i in range(16)]
        ego_to_world = [float(i) for i in range(16, 32)]
        response = _to_point_cloud_response(
            "ds-1",
            _make_point_cloud_row(extrinsic_matrix=world_to_sensor, ego_to_world=ego_to_world),
        )
        assert response.extrinsic_matrix == world_to_sensor
        assert response.ego_to_world == ego_to_world

    def test_converts_the_stored_vector_to_a_plain_list(self):
        # Lance hands back its own `Vector(16)` sequence; the response model has
        # to be JSON-serialisable, so it must not keep the storage type.
        class _Vector(Sequence):
            def __init__(self, values):
                self._values = values

            def __getitem__(self, index):
                return self._values[index]

            def __len__(self):
                return len(self._values)

        values = [float(i) for i in range(16)]
        response = _to_point_cloud_response("ds-1", _make_point_cloud_row(extrinsic_matrix=_Vector(values)))
        assert isinstance(response.extrinsic_matrix, list)
        assert response.extrinsic_matrix == values
