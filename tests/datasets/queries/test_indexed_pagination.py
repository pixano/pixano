# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Filtered pagination: index-covered fast path vs full-scan fallback (P0 concurrency work)."""

from pathlib import Path

import lancedb
import pyarrow as pa
import pytest

from pixano.datasets.queries import TableQueryBuilder


@pytest.fixture()
def multi_camera_table(tmp_path: Path):
    """Interleaved 2-camera frames across 3 records — the LIBERO shape."""
    db = lancedb.connect(tmp_path / "db")
    rows = []
    for rec in ("recA", "recB", "recC"):
        for i in range(300):
            for cam in ("cam_a", "cam_b"):
                rows.append(
                    {"id": f"{rec}-{cam}-{i}", "record_id": rec, "logical_name": cam, "frame_index": i, "extra": i}
                )
    table = db.create_table("frames", pa.Table.from_pylist(rows))
    table.create_scalar_index("record_id", index_type="BTREE")
    table.create_scalar_index("frame_index", index_type="BTREE")
    table.create_scalar_index("logical_name", index_type="BITMAP")
    return table


class TestIndexCoveredFastPath:
    def test_mid_table_batch_is_exact(self, multi_camera_table):
        where = "record_id = 'recB' and logical_name = 'cam_b' and frame_index >= 128 and frame_index < 256"
        rows = TableQueryBuilder(multi_camera_table).select(["frame_index"]).where(where).limit(128).to_list()
        assert sorted(r["frame_index"] for r in rows) == list(range(128, 256))

    def test_offset_pages_are_exact_and_disjoint(self, multi_camera_table):
        where = "record_id = 'recC' and logical_name = 'cam_a'"
        page1 = (
            TableQueryBuilder(multi_camera_table).select(["frame_index"]).where(where).limit(100).offset(0).to_list()
        )
        page2 = (
            TableQueryBuilder(multi_camera_table).select(["frame_index"]).where(where).limit(100).offset(100).to_list()
        )
        got = sorted(r["frame_index"] for r in page1) + sorted(r["frame_index"] for r in page2)
        assert got == list(range(0, 200))

    def test_unindexed_predicate_falls_back_to_full_scan(self, multi_camera_table):
        # 'extra' has no scalar index -> the fast path must NOT be used, and the
        # fallback must still return exact results for mid-table matches.
        where = "record_id = 'recB' and extra >= 100 and extra < 150 and logical_name = 'cam_a'"
        builder = TableQueryBuilder(multi_camera_table).select(["frame_index"]).where(where).limit(50)
        assert not builder._filter_is_index_covered()
        rows = builder.to_list()
        assert sorted(r["frame_index"] for r in rows) == list(range(100, 150))

    def test_covered_check(self, multi_camera_table):
        covered = TableQueryBuilder(multi_camera_table).select(["id"]).where("record_id = 'recA'").limit(1)
        assert covered._filter_is_index_covered()
        # filters referencing no known schema column conservatively refuse the fast path
        odd = TableQueryBuilder(multi_camera_table).select(["id"]).where("true").limit(1)
        assert not odd._filter_is_index_covered()


class TestForceFullScan:
    """A non-servable operator on an INDEXED column must not take the fast path.

    The index-coverage check inspects columns, not operators; `!=`/`NOT IN`/`LIKE`
    on an indexed column would wrongly pass it and, under the lancedb 0.29
    limit-before-filter caveat, silently under-return. `force_full_scan` guards it.
    """

    def test_force_full_scan_flips_index_covered_to_false(self, multi_camera_table):
        builder = (
            TableQueryBuilder(multi_camera_table)
            .select(["frame_index"])
            .where("record_id = 'recB'")  # record_id IS indexed → would be covered
            .force_full_scan()
            .limit(50)
        )
        assert not builder._filter_is_index_covered()

    def test_forced_scan_with_indexed_ne_is_exact(self, multi_camera_table):
        # record_id != 'recA' on an indexed column: without force_full_scan the
        # native limit could under-return; forced, the result is exact and bounded.
        where = "record_id != 'recA' and logical_name = 'cam_a' and frame_index >= 100 and frame_index < 150"
        rows = (
            TableQueryBuilder(multi_camera_table)
            .select(["frame_index", "record_id"])
            .where(where)
            .force_full_scan()
            .limit(50)
            .to_list()
        )
        # recB and recC each contribute frames 100..149 on cam_a → 100 matches; limit 50.
        assert len(rows) == 50
        assert all(r["record_id"] != "recA" for r in rows)
        assert all(100 <= r["frame_index"] < 150 for r in rows)
