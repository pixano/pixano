# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The P5.4 hardening matrix (spec §8/§14.15): crash cells, retries, GC, typed guards."""

import json
import os
from pathlib import Path

import pytest

from pixano.datasets import Dataset
from pixano.datasets.io import ImportSpec, import_dataset
from pixano.datasets.io.engine import ImportEngine, replay_journals, state_dir
from pixano.datasets.io.errors import UnsupportedStorageError
from pixano.datasets.io.jobs import JobStore, boot_recover
from tests.datasets.io._toy_importer import ToyImporter


def _spec(name: str, mode: str = "create") -> ImportSpec:
    return ImportSpec.model_validate({"dataset": {"name": name, "workspace": "image"}, "mode": mode})


def _tree_ids(dataset_dir: Path) -> dict[str, list[str]]:
    dataset = Dataset(dataset_dir)
    return {
        name: sorted(r["id"] for r in dataset.open_table(name).search().select(["id"]).limit(None).to_list())
        for name in dataset.info.tables
    }


class TestOverwriteSwapCrashCells:
    """Crash between each journaled step of the overwrite swap -> replay converges."""

    def _seed(self, tmp_path: Path) -> tuple[Path, Path, Path, Path]:
        import_dataset(tmp_path / "s1", tmp_path / "data", _spec("ds"), importer=ToyImporter(num_records=3))
        target = tmp_path / "data" / "library" / "ds"
        # Build a fresh staging as an overwrite candidate (5 records).
        staging = state_dir(tmp_path / "data") / "staging" / "ds-jobX"
        from pixano.datasets.io.spec import resolve_dataset_info

        info = resolve_dataset_info(_spec("ds"))
        info.name = "ds"
        dataset = Dataset.create(staging, info)
        from pixano.schemas import Record

        dataset.add_records({"records": [Record(id=f"new{i}") for i in range(5)]}, check_integrity="none")
        journal_dir = state_dir(tmp_path / "data") / "journal"
        trash = state_dir(tmp_path / "data") / "trash" / "ds-jobX"
        journal_dir.mkdir(parents=True, exist_ok=True)
        trash.parent.mkdir(parents=True, exist_ok=True)
        (journal_dir / "jobX.json").write_text(
            json.dumps({"target": str(target), "staging": str(staging), "trash": str(trash)})
        )
        return target, staging, trash, journal_dir / "jobX.json"

    def test_crash_after_journal_before_any_rename(self, tmp_path: Path):
        target, staging, trash, journal = self._seed(tmp_path)
        replay_journals(tmp_path / "data")  # nothing moved yet: journal is dropped, old dataset intact
        assert target.exists() and Dataset(target).open_table("records").count_rows() == 3

    def test_crash_between_trash_and_promote(self, tmp_path: Path):
        target, staging, trash, journal = self._seed(tmp_path)
        os.rename(target, trash)  # crash here: old in trash, staging not yet promoted
        replay_journals(tmp_path / "data")
        assert target.exists()
        assert Dataset(target).open_table("records").count_rows() == 5  # swap completed forward

    def test_crash_after_promote_before_cleanup(self, tmp_path: Path):
        target, staging, trash, journal = self._seed(tmp_path)
        os.rename(target, trash)
        os.rename(staging, target)  # crash here: swap done, trash + journal left behind
        replay_journals(tmp_path / "data")
        assert Dataset(target).open_table("records").count_rows() == 5
        assert not journal.exists()


class TestWindowsRenameRetry:
    def test_promote_retries_on_permission_error(self, tmp_path: Path, monkeypatch):
        calls = {"n": 0}
        real_rename = os.rename

        def flaky_rename(src, dst):
            calls["n"] += 1
            if calls["n"] <= 2:
                raise PermissionError("simulated Windows lock")
            return real_rename(src, dst)

        import pixano.datasets.io.engine as engine_module

        monkeypatch.setattr(engine_module.os, "rename", flaky_rename)
        monkeypatch.setattr(engine_module.time, "sleep", lambda s: None)
        result = import_dataset(
            tmp_path / "src", tmp_path / "data", _spec("winds"), importer=ToyImporter(num_records=2)
        )
        assert calls["n"] >= 3  # two failures + the successful attempt
        assert Dataset(result.dataset_path).open_table("records").count_rows() == 2

    def test_retry_exhaustion_raises(self, tmp_path: Path, monkeypatch):
        import pixano.datasets.io.engine as engine_module

        monkeypatch.setattr(engine_module.os, "rename", lambda s, d: (_ for _ in ()).throw(PermissionError("lock")))
        monkeypatch.setattr(engine_module.time, "sleep", lambda s: None)
        with pytest.raises(PermissionError):
            import_dataset(tmp_path / "src", tmp_path / "data", _spec("winds2"), importer=ToyImporter(num_records=2))


class TestBootGc:
    def test_trash_and_dead_staging_reclaimed_resumable_kept(self, tmp_path: Path):
        data_dir = tmp_path / "data"
        (data_dir / "library").mkdir(parents=True)
        state = state_dir(data_dir)
        (state / "trash" / "old-ds").mkdir(parents=True)
        (state / "staging" / "ds-deadjob").mkdir(parents=True)
        (state / "staging" / "ds-livejob").mkdir(parents=True)

        store = JobStore.for_data_dir(data_dir)
        live = store.create_job("import")
        # Rename the staged dir to carry the real job id, then mark it interrupted.
        os.rename(state / "staging" / "ds-livejob", state / "staging" / f"ds-{live.id}")
        store.update_job(live.id, status="running", pid=999_999_999)

        boot_recover(data_dir)

        assert not (state / "trash").exists()
        assert not (state / "staging" / "ds-deadjob").exists()  # no job -> reclaimed
        assert (state / "staging" / f"ds-{live.id}").exists()  # interrupted -> resumable, kept


class TestTypedStorageGuards:
    def test_engine_rejects_non_path_data_dir(self):
        with pytest.raises(UnsupportedStorageError, match="local filesystem"):
            ImportEngine("s3://bucket/data")  # type: ignore[arg-type]
