# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The P5.4 hardening matrix (spec §8/§14.15): crash cells, retries, GC, typed guards."""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from pixano.datasets import Dataset
from pixano.datasets.io import ImportSpec, import_dataset
from pixano.datasets.io.engine import ImportEngine, replay_journals, state_dir
from pixano.datasets.io.errors import UnsupportedStorageError
from pixano.datasets.io.jobs import JobStore, boot_recover
from pixano.datasets.locking import dataset_mutation_lock
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
    @pytest.mark.parametrize("replay_failure", ["busy", "rename_error", "invalid_journal"])
    def test_failed_or_busy_replay_preserves_both_swap_candidates(self, tmp_path, monkeypatch, replay_failure):
        import pixano.datasets.io.engine as engine_module

        target, staged, trash, journal = TestOverwriteSwapCrashCells()._seed(tmp_path)
        os.rename(target, trash)
        journal_contents = journal.read_text()
        if replay_failure == "busy":
            with dataset_mutation_lock(target), ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(boot_recover, tmp_path / "data").result(timeout=10)
        elif replay_failure == "rename_error":
            with monkeypatch.context() as patch:

                def cannot_promote(*args):
                    raise PermissionError("promotion temporarily unavailable")

                patch.setattr(engine_module.os, "rename", cannot_promote)
                boot_recover(tmp_path / "data")
        else:
            journal.write_text("{incomplete journal")
            boot_recover(tmp_path / "data")

        assert not target.exists()
        assert Dataset(trash).open_table("records").count_rows() == 3
        assert Dataset(staged).open_table("records").count_rows() == 5
        assert journal.exists()

        journal.write_text(journal_contents)
        boot_recover(tmp_path / "data")
        assert Dataset(target).open_table("records").count_rows() == 5
        assert not staged.exists() and not trash.exists() and not journal.exists()

    def test_python_build_without_job_row_survives_concurrent_boot_gc(self, tmp_path):
        data_dir = tmp_path / "data"
        staged = state_dir(data_dir) / "staging" / "ds-python-job"
        checkpoints = []

        def run_gc_between_flushes(cursor, counts):
            with ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(boot_recover, data_dir).result(timeout=10)
            assert staged.is_dir()
            checkpoints.append(cursor)

        result = import_dataset(
            tmp_path / "source",
            data_dir,
            _spec("ds"),
            importer=ToyImporter(num_records=6, batch_size=2),
            engine=ImportEngine(data_dir, flush_rows=1, checkpoint=run_gc_between_flushes),
            job_id="python-job",
        )
        assert checkpoints
        assert Dataset(result.dataset_path).open_table("records").count_rows() == 6

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

    def test_old_recoverable_jobs_survive_more_than_1000_completed_jobs(self, tmp_path: Path):
        store = JobStore.for_data_dir(tmp_path)
        state = state_dir(tmp_path)
        upload = state / "uploads" / "old-session"
        upload.mkdir(parents=True)
        os.utime(upload, (time.time() - 48 * 3600,) * 2)
        failed = store.create_job("import", spec={"__source": str(upload)})
        store.update_job(failed.id, status="error", cursor={"ordinal": 1})
        dead = store.create_job("import")
        store.update_job(dead.id, status="running", pid=999_999_999)
        for job in (failed, dead):
            (state / "staging" / f"ds-{job.id}").mkdir(parents=True)
        for _ in range(1001):
            completed = store.create_job("import")
            store.update_job(completed.id, status="done")

        assert dead.id in boot_recover(tmp_path)
        assert store.get_job(dead.id).status == "interrupted"
        for job in (failed, dead):
            assert (state / "staging" / f"ds-{job.id}").is_dir()
        assert upload.is_dir()

    @pytest.mark.parametrize("status", ["done", "cancelled", "rolled_back", "error"])
    def test_non_resumable_staging_is_removed(self, tmp_path: Path, status: str):
        store = JobStore.for_data_dir(tmp_path)
        job = store.create_job("import")
        store.update_job(job.id, status=status)
        staged = state_dir(tmp_path) / "staging" / f"ds-{job.id}"
        staged.mkdir(parents=True)
        boot_recover(tmp_path)
        assert not staged.exists()

    def test_orphan_uploads_have_a_24_hour_grace_period(self, tmp_path: Path):
        uploads = state_dir(tmp_path) / "uploads"
        fresh, expired = uploads / "fresh", uploads / "expired"
        fresh.mkdir(parents=True)
        expired.mkdir()
        os.utime(expired, (time.time() - 48 * 3600,) * 2)
        boot_recover(tmp_path)
        assert fresh.is_dir()
        assert not expired.exists()


class TestTypedStorageGuards:
    def test_engine_rejects_non_path_data_dir(self):
        with pytest.raises(UnsupportedStorageError, match="local filesystem"):
            ImportEngine("s3://bucket/data")  # type: ignore[arg-type]
