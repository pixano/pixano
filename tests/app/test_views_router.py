# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Unit tests for pure helper functions in the views router."""

from unittest.mock import MagicMock

import pytest

from pixano.api.routers.views import (
    CALIBRATED_IMAGE_TABLE,
    IMAGE_TABLE,
    _combine_where,
    _resolve_image_table,
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
