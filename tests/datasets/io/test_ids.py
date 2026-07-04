# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import subprocess
import sys
from pathlib import Path

import pytest

from pixano.datasets.io import IdLedger, namespace_prefix, stable_id


class TestStableId:
    def test_deterministic_across_processes(self):
        expected = stable_id("voc2007", "train", "000042", 3)
        code = "from pixano.datasets.io import stable_id;" "print(stable_id('voc2007', 'train', '000042', 3), end='')"
        result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
        assert result.stdout == expected

    def test_namespace_prefix_shape(self):
        prefix = namespace_prefix("voc2007")
        assert len(prefix) == 8
        assert stable_id("voc2007", "x").startswith(f"{prefix}-")
        assert namespace_prefix("other_ds") != prefix

    def test_distinct_part_tuples_are_distinct(self):
        # Length-prefixed hashing: concatenation ambiguity must not collide.
        assert stable_id("ns", "ab", "c") != stable_id("ns", "a", "bc")
        assert stable_id("ns", "a", "") != stable_id("ns", "a")
        assert stable_id("ns", 12, 3) != stable_id("ns", 1, 23)

    def test_same_parts_different_namespace_differ(self):
        assert stable_id("ns1", "train", 0) != stable_id("ns2", "train", 0)


class TestIdLedger:
    def test_memory_path(self):
        ledger = IdLedger()
        ledger.add("records", {"a", "b"})
        assert ledger.contains("records", "a")
        assert not ledger.contains("records", "c")
        assert ledger.fk_lookup("records", {"a", "c"}) == {"a": True, "c": False}
        assert ledger.missing("records", {"a", "c"}) == {"c"}
        assert ledger.known_ids() == {"records": {"a", "b"}}

    def test_spill_boundary_is_exact(self, tmp_path: Path):
        ledger = IdLedger(spill_dir=tmp_path, spill_threshold=1_000)
        first_half = {f"id_{n}" for n in range(800)}
        second_half = {f"id_{n}" for n in range(800, 5_000)}
        ledger.add("records", first_half)
        ledger.add("entities", second_half)  # crosses the threshold -> spills

        assert (tmp_path / "id_ledger.sqlite").exists()
        assert ledger.contains("records", "id_0")
        assert ledger.contains("entities", "id_4999")
        assert not ledger.contains("records", "id_4999")  # table separation survives the spill

        lookup = ledger.fk_lookup("entities", {"id_800", "id_4999", "ghost"})
        assert lookup == {"id_800": True, "id_4999": True, "ghost": False}

        # Post-spill adds land in SQLite too.
        ledger.add("records", {"late"})
        assert ledger.contains("records", "late")
        with pytest.raises(RuntimeError, match="spilled"):
            ledger.known_ids()
        ledger.close()

    @pytest.mark.slow
    def test_soak_many_ids(self, tmp_path: Path):
        ledger = IdLedger(spill_dir=tmp_path, spill_threshold=1_000_000)
        for chunk_start in range(0, 6_000_000, 500_000):
            ledger.add("records", [f"id_{n}" for n in range(chunk_start, chunk_start + 500_000)])
        assert ledger.contains("records", "id_5999999")
        assert not ledger.contains("records", "id_6000000")
        ledger.close()
