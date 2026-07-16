# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Unit tests for pure helper functions in the records router."""

from typing import Any
from unittest.mock import patch

from pixano.api.models import PreviewDescriptor
from pixano.api.routers.records import _resolve_view_previews


# ─── Helpers ──────────────────────────────────────────────────────────────────


def _rows_for(table_rows: dict[str, list[dict[str, Any]]]):
    """Return a stand-in for `_query_preview_rows` that serves rows per table name."""

    def _fake_query(dataset, table_name, columns, record_ids, *, order_by=None):
        return table_rows.get(table_name, [])

    return _fake_query


# ─── _resolve_view_previews ───────────────────────────────────────────────────


class TestResolveViewPreviews:
    def test_plain_images_produce_previews(self):
        rows = {"images": [{"id": "image_0", "record_id": "rec_0", "logical_name": "image"}]}
        with patch("pixano.api.routers.records._query_preview_rows", side_effect=_rows_for(rows)):
            result = _resolve_view_previews("ds", object(), ["rec_0"])
        assert result["rec_0"]["image"] == PreviewDescriptor(
            resource="images",
            id="image_0",
            kind="image",
            preview_url="/datasets/ds/images/image_0/preview",
        )

    def test_calibrated_images_produce_previews_via_images_route(self):
        # nuScenes-style cameras live in the `calibrated_images` table; they must
        # still yield a preview served through the `/images/{id}/preview` route.
        rows = {
            "calibrated_images": [
                {"id": "CAM_FRONT_0", "record_id": "rec_0", "logical_name": "CAM_FRONT"},
                {"id": "CAM_BACK_0", "record_id": "rec_0", "logical_name": "CAM_BACK"},
            ]
        }
        with patch("pixano.api.routers.records._query_preview_rows", side_effect=_rows_for(rows)):
            result = _resolve_view_previews("ds", object(), ["rec_0"])
        assert result["rec_0"]["CAM_FRONT"] == PreviewDescriptor(
            resource="images",
            id="CAM_FRONT_0",
            kind="image",
            preview_url="/datasets/ds/images/CAM_FRONT_0/preview",
        )
        assert result["rec_0"]["CAM_BACK"].preview_url == "/datasets/ds/images/CAM_BACK_0/preview"

    def test_calibrated_images_win_when_both_tables_share_a_logical_name(self):
        rows = {
            "calibrated_images": [{"id": "cal_0", "record_id": "rec_0", "logical_name": "cam"}],
            "images": [{"id": "img_0", "record_id": "rec_0", "logical_name": "cam"}],
        }
        with patch("pixano.api.routers.records._query_preview_rows", side_effect=_rows_for(rows)):
            result = _resolve_view_previews("ds", object(), ["rec_0"])
        assert result["rec_0"]["cam"].id == "cal_0"

    def test_record_without_views_gets_empty_map(self):
        with patch("pixano.api.routers.records._query_preview_rows", side_effect=_rows_for({})):
            result = _resolve_view_previews("ds", object(), ["rec_0"])
        assert result["rec_0"] == {}

    def test_rows_missing_required_fields_are_skipped(self):
        rows = {"calibrated_images": [{"id": "", "record_id": "rec_0", "logical_name": "cam"}]}
        with patch("pixano.api.routers.records._query_preview_rows", side_effect=_rows_for(rows)):
            result = _resolve_view_previews("ds", object(), ["rec_0"])
        assert result["rec_0"] == {}
