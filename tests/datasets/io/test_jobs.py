# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import threading
import time
from pathlib import Path

import pytest

from pixano.datasets.io import ImportPlan
from pixano.datasets.io.errors import JobStateError
from pixano.datasets.io.jobs import JobRunner, JobStore, boot_recover
from tests.datasets.io._toy_importer import ToyImporter


@pytest.fixture()
def store(tmp_path: Path) -> JobStore:
    return JobStore.for_data_dir(tmp_path)


class TestJobStore:
    def test_create_update_get_roundtrip(self, store: JobStore):
        job = store.create_job("import", dataset="ds1", spec={"format": "coco"})
        assert job.status == "pending" and job.spec == {"format": "coco"}

        store.update_job(job.id, status="running", progress={"phase": "ingest", "done": 10})
        fetched = store.get_job(job.id)
        assert fetched is not None
        assert fetched.status == "running" and fetched.progress["done"] == 10
        assert store.list_jobs()[0].id == job.id

    def test_wal_concurrent_reader_writer(self, store: JobStore):
        job = store.create_job("import")
        errors: list[Exception] = []

        def writer():
            try:
                for i in range(50):
                    store.update_job(job.id, progress={"done": i})
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        def reader():
            try:
                for _ in range(50):
                    fetched = store.get_job(job.id)
                    assert fetched is not None
            except Exception as exc:  # pragma: no cover
                errors.append(exc)

        threads = [threading.Thread(target=writer), threading.Thread(target=reader)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        assert not errors

    def test_mark_interrupted_on_boot_flips_dead_pids(self, store: JobStore):
        dead = store.create_job("import")
        store.update_job(dead.id, status="running", pid=999_999_999)
        alive = store.create_job("import")
        store.update_job(alive.id, status="running")

        flipped = store.mark_interrupted_on_boot(pid_check=lambda pid: pid != 999_999_999)
        assert flipped == [dead.id]
        assert store.get_job(dead.id).status == "interrupted"
        assert store.get_job(alive.id).status == "running"

    def test_plan_roundtrip_and_expiry(self, store: JobStore):
        plan = ImportPlan(format="coco", importer_version="1.0.0")
        plan.totals.records = 7
        plan_id = store.save_plan(plan, source="/data/src")

        stored = store.get_plan(plan_id)
        assert stored is not None
        restored, source = stored
        assert restored.totals.records == 7 and source == "/data/src"

        expired_id = store.save_plan(plan, source="/x", ttl_s=-1)
        assert store.get_plan(expired_id) is None

    def test_cancel_semantics(self, store: JobStore):
        pending = store.create_job("import")
        assert store.request_cancel(pending.id).status == "cancelled"
        with pytest.raises(JobStateError, match="already"):
            store.request_cancel(pending.id)

        running = store.create_job("import")
        store.update_job(running.id, status="running")
        store.request_cancel(running.id)
        assert store.cancel_requested(running.id)


class TestJobRunner:
    def test_import_job_end_to_end(self, tmp_path: Path):
        (tmp_path / "library").mkdir()
        store = JobStore.for_data_dir(tmp_path)
        runner = JobRunner(store, tmp_path)

        # ToyImporter isn't registry-detectable from a folder, so drive the pieces
        # the runner drives, via a registered format: use the jsonl media-only path.
        source = tmp_path / "raw_images"
        (source / "train").mkdir(parents=True)
        import PIL.Image

        for stem in ("a", "b"):
            PIL.Image.new("RGB", (8, 8), (10, 20, 30)).save(source / "train" / f"{stem}.jpg")

        job = runner.submit_import(
            str(source), {"dataset": {"name": "jobds", "workspace": "image"}, "format": "pixano_jsonl"}
        )
        runner.join(timeout=60)

        final = store.get_job(job.id)
        assert final is not None
        assert final.status == "done", final.error
        assert final.progress.get("table_counts", {}).get("records") == 2
        assert final.dataset  # dataset id recorded

    def test_cancelled_before_start(self, tmp_path: Path):
        store = JobStore.for_data_dir(tmp_path)
        job = store.create_job("import")
        store.update_job(job.id, status="cancelled")
        # A cancelled job never flips to running even if the worker picks it up.
        runner = JobRunner(store, tmp_path)
        runner._run_import(job.id, str(tmp_path), {"format": "pixano_jsonl"}, "")
        assert store.get_job(job.id).status == "cancelled"

    def test_error_recorded(self, tmp_path: Path):
        (tmp_path / "library").mkdir()
        store = JobStore.for_data_dir(tmp_path)
        runner = JobRunner(store, tmp_path)
        job = runner.submit_import(str(tmp_path / "missing_source"), {"format": "pixano_jsonl"})
        runner.join(timeout=30)
        final = store.get_job(job.id)
        assert final.status == "error"
        assert final.error.get("message")


class TestBootRecover:
    def test_boot_marks_interrupted(self, tmp_path: Path):
        store = JobStore.for_data_dir(tmp_path)
        job = store.create_job("import")
        store.update_job(job.id, status="running", pid=999_999_999)

        flipped = boot_recover(tmp_path)
        assert job.id in flipped
        assert JobStore.for_data_dir(tmp_path).get_job(job.id).status == "interrupted"
