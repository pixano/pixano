# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Durable import/export jobs: SQLite store + single-worker runner (spec §9).

The store lives at ``<data_dir>/.pixano/jobs.sqlite`` (WAL mode, safe for the
API process and the CLI to share). Jobs progress through
``pending → running → done | error | cancelled``; a job whose process died
mid-run is flipped to ``interrupted`` at the next boot. Analyze plans persist
alongside jobs so ``POST /io/imports {plan_id}`` executes exactly what was
previewed — a changed source fingerprint is a ``PlanMismatchError``.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

import shortuuid

from .errors import JobStateError, PixanoDataError
from .plan import ImportPlan
from .progress import ProgressEvent, ProgressSink, ThrottledSink


JOB_STATES = ("pending", "running", "interrupted", "done", "error", "cancelled", "rolled_back")
_TERMINAL_STATES = frozenset({"done", "error", "cancelled", "rolled_back"})

_SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
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
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    plan_json TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    source_fingerprint TEXT NOT NULL DEFAULT '',
    expires_at REAL NOT NULL DEFAULT 0
);
"""


@dataclass
class JobRecord:
    """One row of the jobs table, decoded."""

    id: str
    kind: str
    dataset: str
    status: str
    spec: dict[str, Any] = field(default_factory=dict)
    plan_id: str = ""
    progress: dict[str, Any] = field(default_factory=dict)
    cursor: dict[str, Any] = field(default_factory=dict)
    manifest_path: str = ""
    error: dict[str, Any] = field(default_factory=dict)
    pid: int = 0
    heartbeat: float = 0.0
    created_at: float = 0.0
    updated_at: float = 0.0


def _decode(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        id=row["id"],
        kind=row["kind"],
        dataset=row["dataset"],
        status=row["status"],
        spec=json.loads(row["spec_json"] or "{}"),
        plan_id=row["plan_id"],
        progress=json.loads(row["progress_json"] or "{}"),
        cursor=json.loads(row["cursor_json"] or "{}"),
        manifest_path=row["manifest_path"],
        error=json.loads(row["error_json"] or "{}"),
        pid=row["pid"],
        heartbeat=row["heartbeat"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except (ProcessLookupError, PermissionError):
        return False
    except OSError:
        return False
    return True


class JobStore:
    """SQLite-backed job and plan persistence, shared by the API and the CLI."""

    def __init__(self, db_path: Path):
        """Open (and initialize) the store at ``db_path``."""
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        with self._connect() as db:
            db.executescript(_SCHEMA)

    @classmethod
    def for_data_dir(cls, data_dir: Path) -> "JobStore":
        """The canonical store location for a Pixano data directory."""
        return cls(Path(data_dir) / ".pixano" / "jobs.sqlite")

    def _connect(self) -> sqlite3.Connection:
        db = getattr(self._local, "db", None)
        if db is None:
            db = sqlite3.connect(self.db_path, timeout=5.0, check_same_thread=False)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA journal_mode=WAL")
            db.execute("PRAGMA busy_timeout=5000")
            self._local.db = db
        return db

    # ------------------------------------------------------------------
    # Jobs
    # ------------------------------------------------------------------

    def create_job(self, kind: str, dataset: str = "", spec: dict | None = None, plan_id: str = "") -> JobRecord:
        """Insert a pending job and return it."""
        job_id = shortuuid.uuid()
        now = time.time()
        with self._connect() as db:
            db.execute(
                "INSERT INTO jobs (id, kind, dataset, status, spec_json, plan_id, pid, created_at, updated_at)"
                " VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?)",
                (job_id, kind, dataset, json.dumps(spec or {}), plan_id, os.getpid(), now, now),
            )
        job = self.get_job(job_id)
        assert job is not None
        return job

    def get_job(self, job_id: str) -> JobRecord | None:
        """Fetch one job, or None."""
        row = self._connect().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return _decode(row) if row else None

    def list_jobs(self, limit: int = 50) -> list[JobRecord]:
        """Most recent jobs first."""
        rows = self._connect().execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [_decode(row) for row in rows]

    def update_job(self, job_id: str, **fields: Any) -> None:
        """Update columns; dict values are JSON-encoded into their *_json columns."""
        columns: list[str] = []
        values: list[Any] = []
        for name, value in fields.items():
            if name in ("spec", "progress", "cursor", "error"):
                columns.append(f"{name if name != 'spec' else 'spec'}_json = ?")
                values.append(json.dumps(value))
            else:
                columns.append(f"{name} = ?")
                values.append(value)
        columns.append("updated_at = ?")
        values.append(time.time())
        values.append(job_id)
        with self._connect() as db:
            db.execute(f"UPDATE jobs SET {', '.join(columns)} WHERE id = ?", values)

    def request_cancel(self, job_id: str) -> JobRecord:
        """Flag a pending/running job for cooperative cancellation."""
        job = self.get_job(job_id)
        if job is None:
            raise JobStateError(f"Unknown job '{job_id}'.")
        if job.status in _TERMINAL_STATES:
            raise JobStateError(f"Job '{job_id}' is already {job.status}.")
        if job.status == "pending":
            self.update_job(job_id, status="cancelled")
        else:
            self.update_job(job_id, error={"cancel_requested": True})
        refreshed = self.get_job(job_id)
        assert refreshed is not None
        return refreshed

    def cancel_requested(self, job_id: str) -> bool:
        """True when a cooperative cancel was requested for the job."""
        job = self.get_job(job_id)
        return bool(job and (job.error.get("cancel_requested") or job.status == "cancelled"))

    def heartbeat(self, job_id: str) -> None:
        """Stamp liveness for the running job."""
        self.update_job(job_id, heartbeat=time.time())

    def mark_interrupted_on_boot(self, pid_check: Callable[[int], bool] = _pid_alive) -> list[str]:
        """Flip running/pending jobs whose process is gone to `interrupted` (boot hook)."""
        flipped: list[str] = []
        for job in self.list_jobs(limit=1000):
            if job.status in ("running", "pending") and not pid_check(job.pid):
                self.update_job(job.id, status="interrupted")
                flipped.append(job.id)
        return flipped

    # ------------------------------------------------------------------
    # Plans
    # ------------------------------------------------------------------

    def save_plan(self, plan: ImportPlan, source: str, ttl_s: float = 24 * 3600) -> str:
        """Persist an analyze plan; returns its plan_id."""
        plan_id = shortuuid.uuid()
        with self._connect() as db:
            db.execute(
                "INSERT INTO plans (id, plan_json, source, source_fingerprint, expires_at) VALUES (?, ?, ?, ?, ?)",
                (plan_id, plan.model_dump_json(), source, plan.source_fingerprint, time.time() + ttl_s),
            )
        return plan_id

    def get_plan(self, plan_id: str) -> tuple[ImportPlan, str] | None:
        """Fetch a plan and its source location; None when missing or expired."""
        row = self._connect().execute("SELECT * FROM plans WHERE id = ?", (plan_id,)).fetchone()
        if row is None or (row["expires_at"] and row["expires_at"] < time.time()):
            return None
        return ImportPlan.model_validate_json(row["plan_json"]), row["source"]


class JobSink(ProgressSink):
    """Progress sink persisting throttled engine events into the store."""

    def __init__(self, store: JobStore, job_id: str, min_interval_s: float = 0.5):
        """Wrap the store; events are throttled like ThrottledSink."""
        self.store = store
        self.job_id = job_id
        self._throttle = ThrottledSink(_CallbackSink(self._write), min_interval=min_interval_s)

    def emit(self, event: ProgressEvent) -> None:
        """Forward the event through the throttle."""
        self._throttle.emit(event)

    def close(self) -> None:
        """Flush the throttle."""
        self._throttle.close()

    def _write(self, event: ProgressEvent) -> None:
        self.store.update_job(self.job_id, progress=event.model_dump(), heartbeat=time.time())


class _CallbackSink(ProgressSink):
    def __init__(self, callback: Callable[[ProgressEvent], None]):
        self.callback = callback

    def emit(self, event: ProgressEvent) -> None:
        self.callback(event)

    def close(self) -> None:  # noqa: D102 - nothing buffered
        pass


class JobRunner:
    """Single-worker job executor: one import/export at a time, cooperatively cancellable."""

    def __init__(self, store: JobStore, data_dir: Path):
        """Bind the runner to a store and data directory."""
        self.store = store
        self.data_dir = Path(data_dir)
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    def submit_import(self, source: str, spec_payload: dict[str, Any], plan_id: str = "") -> JobRecord:
        """Create a pending import job and start it on the worker thread."""
        job = self.store.create_job(
            "import",
            dataset=str(spec_payload.get("dataset", {}).get("name", "")),
            spec={**spec_payload, "__source": source},  # resume needs the source; stripped before validation
            plan_id=plan_id,
        )
        thread = threading.Thread(target=self._run_import, args=(job.id, source, spec_payload, plan_id), daemon=True)
        self._threads.append(thread)
        thread.start()
        return job

    def submit_resume(self, job_id: str) -> JobRecord:
        """Resume an interrupted/errored job from its last committed cursor."""
        job = self.store.get_job(job_id)
        if job is None:
            raise JobStateError(f"Unknown job '{job_id}'.")
        if job.kind != "import" or job.status not in ("interrupted", "error"):
            raise JobStateError(f"Job '{job_id}' is {job.status}; only interrupted/errored imports resume.")
        if not job.cursor:
            raise JobStateError(f"Job '{job_id}' has no committed checkpoint; restart the import instead.")
        source = str(job.spec.get("__source", "")) or ""
        stored_plan = self.store.get_plan(job.plan_id) if job.plan_id else None
        if not source and stored_plan is not None:
            source = stored_plan[1]
        if not source:
            raise JobStateError(f"Job '{job_id}' recorded no source; restart the import instead.")
        self.store.update_job(job_id, status="pending", error={})
        thread = threading.Thread(
            target=self._run_import,
            args=(job_id, source, {k: v for k, v in job.spec.items() if k != "__source"}, job.plan_id),
            kwargs={"resume_cursor": dict(job.cursor)},
            daemon=True,
        )
        self._threads.append(thread)
        thread.start()
        refreshed = self.store.get_job(job_id)
        assert refreshed is not None
        return refreshed

    def _run_import(
        self,
        job_id: str,
        source: str,
        spec_payload: dict[str, Any],
        plan_id: str,
        resume_cursor: dict[str, Any] | None = None,
    ) -> None:
        from .api import import_dataset
        from .engine import ImportEngine
        from .spec import ImportSpec

        with self._lock:  # concurrency 1: imports serialize
            if self.store.cancel_requested(job_id):
                self.store.update_job(job_id, status="cancelled")
                return
            self.store.update_job(job_id, status="running", pid=os.getpid(), heartbeat=time.time())
            try:
                spec = ImportSpec.model_validate({k: v for k, v in spec_payload.items() if k != "__source"})
                plan = None
                if plan_id:
                    stored = self.store.get_plan(plan_id)
                    if stored is None:
                        raise JobStateError(f"Plan '{plan_id}' not found or expired.")
                    plan, plan_source = stored
                    source = source or plan_source
                engine = ImportEngine(
                    self.data_dir,
                    checkpoint=lambda cursor, counts: self.store.update_job(job_id, cursor=dict(cursor)),
                    cancel_check=lambda: self.store.cancel_requested(job_id),
                )
                sink = JobSink(self.store, job_id)
                result = import_dataset(
                    source,
                    self.data_dir,
                    spec,
                    plan=plan,
                    sinks=[sink],
                    engine=engine,
                    job_id=job_id,
                    resume_cursor=resume_cursor,
                )
                sink.close()
                self.store.update_job(
                    job_id,
                    status="done",
                    dataset=result.dataset_id,
                    manifest_path=str(result.manifest_path or ""),
                    progress={"phase": "done", "table_counts": result.table_counts, "final": True},
                )
            except PixanoDataError as error:
                cancelled = self.store.cancel_requested(job_id)
                self.store.update_job(
                    job_id,
                    status="cancelled" if cancelled else "error",
                    error={"type": type(error).__name__, "message": str(error)},
                )
            except Exception as error:  # pragma: no cover - defensive
                self.store.update_job(
                    job_id,
                    status="error",
                    error={
                        "type": type(error).__name__,
                        "message": str(error),
                        "trace": traceback.format_exc()[-2000:],
                    },
                )

    def submit_export(self, dataset_path: str, destination: str, format: str, media: str) -> JobRecord:
        """Create a pending export job and start it on the worker thread."""
        job = self.store.create_job("export", dataset=Path(dataset_path).name, spec={"format": format, "media": media})
        thread = threading.Thread(
            target=self._run_export, args=(job.id, dataset_path, destination, format, media), daemon=True
        )
        self._threads.append(thread)
        thread.start()
        return job

    def _run_export(self, job_id: str, dataset_path: str, destination: str, format: str, media: str) -> None:
        from .api import export_dataset

        with self._lock:
            if self.store.cancel_requested(job_id):
                self.store.update_job(job_id, status="cancelled")
                return
            self.store.update_job(job_id, status="running", pid=os.getpid(), heartbeat=time.time())
            try:
                exported = export_dataset(dataset_path, destination, format=format, media=media)
                self.store.update_job(
                    job_id, status="done", progress={"phase": "done", "message": str(exported), "final": True}
                )
            except PixanoDataError as error:
                self.store.update_job(
                    job_id, status="error", error={"type": type(error).__name__, "message": str(error)}
                )
            except Exception as error:  # pragma: no cover - defensive
                self.store.update_job(
                    job_id,
                    status="error",
                    error={
                        "type": type(error).__name__,
                        "message": str(error),
                        "trace": traceback.format_exc()[-2000:],
                    },
                )

    def join(self, timeout: float | None = None) -> None:
        """Wait for in-flight jobs (tests and CLI teardown)."""
        for thread in self._threads:
            thread.join(timeout)


def boot_recover(data_dir: Path) -> Sequence[str]:
    """Server-boot hook: replay staged journals, then mark orphaned jobs interrupted."""
    from .engine import replay_journals

    replay_journals(Path(data_dir))
    store = JobStore.for_data_dir(Path(data_dir))
    return store.mark_interrupted_on_boot()
