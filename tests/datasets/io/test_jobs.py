# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import sqlite3
import threading
import time
from dataclasses import replace
from pathlib import Path

import PIL.Image
import pytest

from pixano.datasets.io import ImportPlan, PixanoDataError
from pixano.datasets.io.errors import JobStateError
from pixano.datasets.io.jobs import (
    CANCELLED,
    FAILED,
    IN_FLIGHT,
    NO_OUTCOME,
    NO_STARTER,
    FollowUp,
    JobRunner,
    JobStore,
    _add_missing_columns,
    boot_recover,
    queue_follow_ups,
    queue_import_follow_ups,
)
from tests.datasets.io._toy_importer import ToyImporter


EMBEDDINGS = FollowUp(kind="embeddings", params={"model": "clip"})

# The jobs table as the stores made before follow-ups existed have it.
STORE_BEFORE_FOLLOW_UPS = """
CREATE TABLE jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    dataset TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    spec_json TEXT NOT NULL DEFAULT '{}',
    plan_id TEXT NOT NULL DEFAULT '',
    progress_json TEXT NOT NULL DEFAULT '{}',
    cursor_json TEXT NOT NULL DEFAULT '{}',
    manifest_path TEXT NOT NULL DEFAULT '',
    error_json TEXT NOT NULL DEFAULT '{}',
    pid INTEGER NOT NULL DEFAULT 0,
    heartbeat REAL NOT NULL DEFAULT 0,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);
"""


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

        interrupted = store.create_job("import")
        store.update_job(interrupted.id, status="interrupted", cursor={"ordinal": 1})
        assert store.request_cancel(interrupted.id).status == "cancelled"
        with pytest.raises(JobStateError, match="only interrupted/errored"):
            JobRunner(store, store.db_path.parent.parent).submit_resume(interrupted.id)

    def test_dead_cancelled_worker_becomes_cancelled_on_boot(self, store: JobStore):
        job = store.create_job("import")
        store.update_job(job.id, status="running", pid=999_999_999)
        store.request_cancel(job.id)
        assert store.mark_interrupted_on_boot(pid_check=lambda pid: False) == []
        assert store.get_job(job.id).status == "cancelled"


# ToyImporter isn't registry-detectable from a folder, so the runner's tests import through a
# registered format: the jsonl media-only path, over a folder of images.
IMAGE_SPEC = {"dataset": {"name": "jobds", "workspace": "image"}, "format": "pixano_jsonl"}


def _image_source(tmp_path: Path) -> Path:
    """Two images in a split folder, as the media-only path reads them."""
    source = tmp_path / "raw_images"
    (source / "train").mkdir(parents=True)
    for stem in ("a", "b"):
        PIL.Image.new("RGB", (8, 8), (10, 20, 30)).save(source / "train" / f"{stem}.jpg")
    return source


class _Starter:
    """Queues follow-ups as a job queue would, and records each call.

    Given the store, it also records what the store held of the import job when it was called.
    """

    def __init__(self, failure: Exception | None = None, store: JobStore | None = None):
        self.calls: list[tuple[str, list[FollowUp]]] = []
        self.seen: list[tuple[str, list[FollowUp]]] = []
        self.failure = failure
        self.store = store

    def __call__(self, dataset_id: str, follow_ups: list[FollowUp]) -> list[FollowUp]:
        self.calls.append((dataset_id, follow_ups))
        if self.store is not None:
            job = self.store.list_jobs()[0]
            self.seen.append((job.status, job.follow_ups))
        if self.failure is not None:
            raise self.failure
        return [replace(follow_up, job_id=f"job-{rank}") for rank, follow_up in enumerate(follow_ups)]


class TestFollowUpsAreKept:
    def test_with_the_job_and_their_outcome_with_them(self, store: JobStore):
        job = store.create_job("import", follow_ups=[EMBEDDINGS])
        assert store.get_job(job.id).follow_ups == [EMBEDDINGS]

        queued = replace(EMBEDDINGS, job_id="job-0")
        store.update_job(job.id, follow_ups=[queued])

        assert store.get_job(job.id).follow_ups == [queued]

    def test_a_job_asked_for_none_has_none(self, store: JobStore):
        assert store.create_job("import").follow_ups == []

    def test_a_store_made_before_them_gains_their_column_and_keeps_its_jobs(self, tmp_path: Path):
        path = tmp_path / ".pixano" / "jobs.sqlite"
        path.parent.mkdir()
        with sqlite3.connect(path) as db:
            db.executescript(STORE_BEFORE_FOLLOW_UPS)
            db.execute(
                "INSERT INTO jobs (id, kind, status, created_at, updated_at) VALUES ('old', 'import', 'done', 0, 0)"
            )

        store = JobStore(path)

        assert store.get_job("old").follow_ups == []
        job = store.create_job("import", follow_ups=[EMBEDDINGS])
        assert store.get_job(job.id).follow_ups == [EMBEDDINGS]
        assert JobStore(path).get_job(job.id).follow_ups == [EMBEDDINGS], "opened again, the column is kept"


class TestQueueingFollowUps:
    def test_only_the_pending_ones_go_to_the_starter_and_the_order_is_kept(self):
        refused = FollowUp(kind="statistics", error="no worker")
        starter = _Starter()

        outcomes = queue_follow_ups(starter, "ds-1", [refused, EMBEDDINGS])

        assert starter.calls == [("ds-1", [EMBEDDINGS])]
        assert outcomes == [refused, replace(EMBEDDINGS, job_id="job-0")]

    def test_nothing_pending_calls_nothing(self):
        starter = _Starter()
        queued = replace(EMBEDDINGS, job_id="job-9")

        assert queue_follow_ups(starter, "ds-1", [queued]) == [queued]
        assert starter.calls == []

    def test_without_a_starter_they_say_nothing_could_queue_them(self):
        assert queue_follow_ups(None, "ds-1", [EMBEDDINGS]) == [replace(EMBEDDINGS, error=NO_STARTER)]

    def test_a_starter_that_fails_leaves_each_saying_why(self):
        starter = _Starter(failure=RuntimeError("the queue went away"))

        (outcome,) = queue_follow_ups(starter, "ds-1", [EMBEDDINGS])

        # The details may name a path or a host: they go to the log, not to whoever reads the job.
        assert outcome.error == FAILED

    def test_a_starter_that_answers_for_fewer_is_a_failure_too(self):
        (outcome,) = queue_follow_ups(lambda dataset_id, follow_ups: [], "ds-1", [EMBEDDINGS])

        assert outcome.error == FAILED

    def test_a_starter_that_gives_one_back_without_an_outcome_says_so(self):
        """Left pending on a done import, it would stay pending for good."""
        (outcome,) = queue_follow_ups(lambda dataset_id, follow_ups: follow_ups, "ds-1", [EMBEDDINGS])

        assert outcome.error == NO_OUTCOME


class TestQueueingAnImportsFollowUps:
    def test_they_are_recorded_as_being_queued_before_the_starter_is_called(self, store: JobStore):
        job = store.create_job("import", follow_ups=[EMBEDDINGS])
        starter = _Starter(store=store)

        outcomes = queue_import_follow_ups(store, job.id, starter, "ds-1")

        assert starter.seen == [("pending", [replace(EMBEDDINGS, error=IN_FLIGHT)])]
        assert outcomes == [replace(EMBEDDINGS, job_id="job-0")]

    def test_a_process_that_stops_after_queueing_them_never_queues_them_twice(self, store: JobStore):
        """The import's done is not recorded: a resume finds them being queued, not pending."""
        job = store.create_job("import", follow_ups=[EMBEDDINGS])
        queue_import_follow_ups(store, job.id, _Starter(), "ds-1")
        starter = _Starter()

        outcomes = queue_import_follow_ups(store, job.id, starter, "ds-1")

        assert starter.calls == []
        assert outcomes == [replace(EMBEDDINGS, error=IN_FLIGHT)]

    def test_an_import_cancelled_too_late_to_stop_queues_nothing(self, store: JobStore):
        job = store.create_job("import", follow_ups=[EMBEDDINGS])
        store.update_job(job.id, status="running")
        store.request_cancel(job.id)
        starter = _Starter()

        outcomes = queue_import_follow_ups(store, job.id, starter, "ds-1")

        assert starter.calls == []
        assert outcomes == [replace(EMBEDDINGS, error=CANCELLED)]


class TestAStoreOpenedTwiceAtOnce:
    class _Racing:
        """A connection whose table read misses the column the other process adds meanwhile."""

        def __init__(self, failure: str):
            self.failure = failure

        def execute(self, statement: str):
            if statement.startswith("PRAGMA"):
                return []
            raise sqlite3.OperationalError(self.failure)

    def test_the_column_the_other_process_added_first_is_kept(self):
        _add_missing_columns(self._Racing("duplicate column name: follow_ups_json"))  # type: ignore[arg-type]

    def test_any_other_failure_is_raised(self):
        with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
            _add_missing_columns(self._Racing("disk I/O error"))  # type: ignore[arg-type]


class TestJobRunner:
    def test_import_job_end_to_end(self, tmp_path: Path):
        (tmp_path / "library").mkdir()
        store = JobStore.for_data_dir(tmp_path)
        runner = JobRunner(store, tmp_path)

        job = runner.submit_import(str(_image_source(tmp_path)), IMAGE_SPEC)
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
        uploaded_source = tmp_path / ".pixano" / "uploads" / "session"
        uploaded_source.mkdir(parents=True)
        runner._run_import(job.id, str(uploaded_source), {"format": "pixano_jsonl"}, "")
        assert store.get_job(job.id).status == "cancelled"
        assert not uploaded_source.exists()

    def test_error_recorded(self, tmp_path: Path):
        (tmp_path / "library").mkdir()
        store = JobStore.for_data_dir(tmp_path)
        runner = JobRunner(store, tmp_path)
        job = runner.submit_import(str(tmp_path / "missing_source"), {"format": "pixano_jsonl"})
        runner.join(timeout=30)
        final = store.get_job(job.id)
        assert final.status == "error"
        assert final.error.get("message")

    def test_an_import_queues_its_follow_ups_once_done_and_records_them_with_it(self, tmp_path: Path):
        (tmp_path / "library").mkdir()
        store = JobStore.for_data_dir(tmp_path)
        starter = _Starter(store=store)
        runner = JobRunner(store, tmp_path, follow_up_starter=starter)

        job = runner.submit_import(str(_image_source(tmp_path)), IMAGE_SPEC, follow_ups=[EMBEDDINGS])
        runner.join(timeout=60)

        final = store.get_job(job.id)
        assert final.status == "done", final.error
        assert starter.calls == [(final.dataset, [EMBEDDINGS])]
        # Queued while the import still read running: whoever sees it done sees the outcome too.
        assert [status for status, _ in starter.seen] == ["running"]
        assert final.follow_ups == [replace(EMBEDDINGS, job_id="job-0")]

    def test_a_failed_import_queues_nothing(self, tmp_path: Path):
        (tmp_path / "library").mkdir()
        store = JobStore.for_data_dir(tmp_path)
        starter = _Starter()
        runner = JobRunner(store, tmp_path, follow_up_starter=starter)

        job = runner.submit_import(
            str(tmp_path / "missing_source"), {"format": "pixano_jsonl"}, follow_ups=[EMBEDDINGS]
        )
        runner.join(timeout=30)

        final = store.get_job(job.id)
        assert final.status == "error"
        assert starter.calls == []
        assert final.follow_ups == [EMBEDDINGS], "still pending: a resume that succeeds queues it"

    def test_a_follow_up_that_cannot_be_queued_leaves_the_import_done(self, tmp_path: Path):
        (tmp_path / "library").mkdir()
        store = JobStore.for_data_dir(tmp_path)
        runner = JobRunner(store, tmp_path, follow_up_starter=_Starter(failure=RuntimeError("queue unreachable")))

        job = runner.submit_import(str(_image_source(tmp_path)), IMAGE_SPEC, follow_ups=[EMBEDDINGS])
        runner.join(timeout=60)

        final = store.get_job(job.id)
        assert final.status == "done", final.error
        assert final.follow_ups == [replace(EMBEDDINGS, error=FAILED)]

    def test_an_import_run_again_from_its_stored_job_queues_what_its_first_run_was_asked(self, tmp_path: Path):
        """As a resume does: the follow-ups come from the store, not from the call that runs it."""
        (tmp_path / "library").mkdir()
        store = JobStore.for_data_dir(tmp_path)
        job = store.create_job("import", dataset="jobds", follow_ups=[EMBEDDINGS])
        starter = _Starter()

        JobRunner(store, tmp_path, follow_up_starter=starter)._run_import(
            job.id, str(_image_source(tmp_path)), IMAGE_SPEC, ""
        )

        final = store.get_job(job.id)
        assert final.status == "done", final.error
        assert starter.calls == [(final.dataset, [EMBEDDINGS])]

    def test_a_resumed_import_queues_what_its_first_run_was_asked_once(self, tmp_path: Path, monkeypatch):
        """The real resume: an import that failed after a committed flush, resumed through the runner."""
        from pixano.datasets.io.engine import ImportEngine
        from pixano.datasets.io.formats.pixano_jsonl.importer import PixanoJsonlImporter

        (tmp_path / "library").mkdir()
        store = JobStore.for_data_dir(tmp_path)
        starter = _Starter()
        runner = JobRunner(store, tmp_path, follow_up_starter=starter)
        original_batches = PixanoJsonlImporter.iter_batches

        def fail_after_first(self, source, spec, plan, cursor=None):
            for ordinal, bundle in enumerate(original_batches(self, source, spec, plan, cursor)):
                if ordinal == 1:
                    raise PixanoDataError("interrupted import")
                yield bundle

        class SmallFlushEngine(ImportEngine):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, flush_rows=1, **kwargs)

        with monkeypatch.context() as patch:
            patch.setattr(PixanoJsonlImporter, "iter_batches", fail_after_first)
            patch.setattr("pixano.datasets.io.engine.ImportEngine", SmallFlushEngine)
            job = runner.submit_import(str(_image_source(tmp_path)), IMAGE_SPEC, follow_ups=[EMBEDDINGS])
            runner.join(timeout=60)
        failed = store.get_job(job.id)
        assert failed.status == "error" and failed.cursor, failed.error
        assert starter.calls == []

        runner.submit_resume(job.id)
        runner.join(timeout=60)

        final = store.get_job(job.id)
        assert final.status == "done", final.error
        assert starter.calls == [(final.dataset, [EMBEDDINGS])]


class TestBootRecover:
    def test_boot_marks_interrupted(self, tmp_path: Path):
        store = JobStore.for_data_dir(tmp_path)
        job = store.create_job("import")
        store.update_job(job.id, status="running", pid=999_999_999)

        flipped = boot_recover(tmp_path)
        assert job.id in flipped
        assert JobStore.for_data_dir(tmp_path).get_job(job.id).status == "interrupted"
