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

An import job also keeps its follow-ups: the processing jobs to queue once it is
done, such as the embeddings of what it imported. This module knows nothing of
the processing queue: whoever runs the import hands it a starter, which queues
them, and the outcome of each is kept with the job.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import threading
import time
import traceback
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path
from typing import Any, Callable, Sequence

import shortuuid

from pixano.datasets.locking import dataset_mutation_lock
from pixano.datasets.utils.errors import DatasetBusyError

from .errors import JobStateError, PixanoDataError
from .plan import ImportPlan
from .progress import ProgressEvent, ProgressSink, ThrottledSink


logger = logging.getLogger(__name__)

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
    updated_at REAL NOT NULL,
    follow_ups_json TEXT NOT NULL DEFAULT '[]'
);
CREATE TABLE IF NOT EXISTS plans (
    id TEXT PRIMARY KEY,
    plan_json TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    source_fingerprint TEXT NOT NULL DEFAULT '',
    expires_at REAL NOT NULL DEFAULT 0
);
"""

# The columns of `jobs` added after its first release, and their definitions. `CREATE TABLE IF
# NOT EXISTS` leaves an existing store's table as it was, so a store made by an earlier version
# gets them when it is opened; its rows take the default.
_ADDED_COLUMNS = {"follow_ups_json": "TEXT NOT NULL DEFAULT '[]'"}


def _add_missing_columns(db: sqlite3.Connection) -> None:
    """Bring a store made by an earlier version up to the current table."""
    present = {row["name"] for row in db.execute("PRAGMA table_info(jobs)")}
    for name, definition in _ADDED_COLUMNS.items():
        if name in present:
            continue
        try:
            db.execute(f"ALTER TABLE jobs ADD COLUMN {name} {definition}")
        except sqlite3.OperationalError as error:
            # The API and the CLI share the store: the other one, opening it at the same time,
            # added the column first.
            if "duplicate column" not in str(error):
                raise


@dataclass(frozen=True)
class FollowUp:
    """A processing job an import queues once it is done, and what became of it.

    Kept with the import job from its start, so that an import resumed after its process died
    still queues it. Neither `job_id` nor `error` is set until the import is done.

    Attributes:
        kind: The processing job kind, as a worker declares it: `embeddings`.
        params: The job's parameters.
        job_id: The queued job's identifier, once queued.
        error: Why it was not queued.
        defaulted: The parameters the request did not name, which the deployment's defaults chose:
            fitting the follow-up to the dataset written may choose otherwise.
    """

    kind: str
    params: dict[str, Any] = field(default_factory=dict)
    job_id: str = ""
    error: str = ""
    defaulted: tuple[str, ...] = ()

    @property
    def pending(self) -> bool:
        """Neither queued nor refused yet."""
        return not self.job_id and not self.error

    def to_json(self) -> dict[str, Any]:
        """The follow-up as the store keeps it, in JSON's own types."""
        return {**asdict(self), "defaulted": list(self.defaulted)}

    @classmethod
    def from_json(cls, payload: dict[str, Any]) -> FollowUp:
        """Read a follow-up back from the store."""
        return cls(
            kind=str(payload.get("kind", "")),
            params=dict(payload.get("params") or {}),
            job_id=str(payload.get("job_id") or ""),
            error=str(payload.get("error") or ""),
            defaulted=tuple(str(name) for name in payload.get("defaulted") or ()),
        )


FollowUpStarter = Callable[[str, list[FollowUp]], list[list[FollowUp]]]
"""Queues an import's pending follow-ups: given the imported dataset's identifier and them, returns
what each became, in the same order — itself, or the several jobs it stands for on that dataset,
such as the embeddings of each model the dataset holds —, each with its job identifier or the
reason it was not queued."""

# What a pending follow-up records when the process that ran its import has no starter to queue it.
NO_STARTER = "not queued: the import ran without a job queue to queue it on"

# What a follow-up records while it is being queued, and keeps if the process stops before its
# outcome is recorded. Queueing is at most once: a resumed import never queues it again, since the
# job may be queued already, and a job missing is one a person can still start by hand.
IN_FLIGHT = "not recorded: being queued, or the import stopped while queueing it — see the dataset's Jobs panel"

# What a follow-up records when its import was cancelled too late to stop: the data is in, but the
# person asked for nothing more.
CANCELLED = "not queued: the import was cancelled"

# What a follow-up records when the starter gave it back without an outcome.
NO_OUTCOME = "not queued: no outcome was given for it"

# What a follow-up records when queueing it failed unexpectedly: the details, which may name a path
# or a host, go to the log of the process that ran the import.
FAILED = "not queued: queueing it failed — the log of the process that ran the import says why"


def queue_follow_ups(
    starter: FollowUpStarter | None, dataset_id: str, follow_ups: Sequence[FollowUp]
) -> list[FollowUp]:
    """Queue an import's pending follow-ups once it is done; return them all, each pending one as what it became.

    A follow-up that cannot be queued says why, and the import stays done: the data is in, and a
    job missing is a job one can still start by hand.

    Args:
        starter: What queues them, or None when nothing can.
        dataset_id: The imported dataset.
        follow_ups: The import's follow-ups, as kept with its job.

    Returns:
        The follow-ups, in their order, each pending one in place of what it became, with its outcome.
    """
    pending = [follow_up for follow_up in follow_ups if follow_up.pending]
    if not pending:
        return list(follow_ups)
    if starter is None:
        became = [[replace(follow_up, error=NO_STARTER)] for follow_up in pending]
    else:
        try:
            became = starter(dataset_id, pending)
            if len(became) != len(pending):
                raise RuntimeError(f"{len(pending)} follow-up(s) asked, {len(became)} answered")
            became = [
                [replace(outcome, error=NO_OUTCOME) if outcome.pending else outcome for outcome in outcomes]
                or [replace(follow_up, error=NO_OUTCOME)]
                for follow_up, outcomes in zip(pending, became, strict=True)
            ]
        except Exception as error:  # noqa: BLE001 - an import is never failed by its follow-ups
            logger.warning("the follow-ups of an import into %s could not be queued: %s", dataset_id, error)
            logger.debug("the follow-ups' failure", exc_info=True)
            became = [[replace(follow_up, error=FAILED)] for follow_up in pending]
    answered = iter(became)
    return [outcome for follow_up in follow_ups for outcome in (next(answered) if follow_up.pending else [follow_up])]


def queue_import_follow_ups(
    store: JobStore, job_id: str, starter: FollowUpStarter | None, dataset_id: str
) -> list[FollowUp]:
    """Queue what an import job asked for once its data is in; return its follow-ups with their outcomes.

    The follow-ups are read from the store, so that a resumed import queues what its first run was
    asked for. The caller records them with the job's `done`, in one update. Before the starter is
    called, the pending ones are recorded as being queued (`IN_FLIGHT`): a process that stops after
    queueing them, before that update, leaves them saying so rather than pending, and a resume does
    not queue them a second time.

    Args:
        store: The job store.
        job_id: The import job, whose data is in.
        starter: What queues them, or None when nothing can.
        dataset_id: The imported dataset.

    Returns:
        The job's follow-ups, each pending one in place of what it became, with its outcome.
    """
    job = store.get_job(job_id)
    follow_ups = list(job.follow_ups) if job else []
    if not any(follow_up.pending for follow_up in follow_ups):
        return follow_ups
    if store.cancel_requested(job_id):
        return [replace(follow_up, error=CANCELLED) if follow_up.pending else follow_up for follow_up in follow_ups]
    store.update_job(
        job_id,
        follow_ups=[
            replace(follow_up, error=IN_FLIGHT) if follow_up.pending else follow_up for follow_up in follow_ups
        ],
    )
    return queue_follow_ups(starter, dataset_id, follow_ups)


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
    follow_ups: list[FollowUp] = field(default_factory=list)


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
        follow_ups=[FollowUp.from_json(item) for item in json.loads(row["follow_ups_json"] or "[]")],
    )


def _encode_follow_ups(follow_ups: Sequence[FollowUp]) -> str:
    return json.dumps([follow_up.to_json() for follow_up in follow_ups])


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
            _add_missing_columns(db)

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

    def create_job(
        self,
        kind: str,
        dataset: str = "",
        spec: dict | None = None,
        plan_id: str = "",
        follow_ups: Sequence[FollowUp] = (),
    ) -> JobRecord:
        """Insert a pending job and return it."""
        job_id = shortuuid.uuid()
        now = time.time()
        with self._connect() as db:
            db.execute(
                "INSERT INTO jobs (id, kind, dataset, status, spec_json, plan_id, pid, created_at, updated_at,"
                " follow_ups_json) VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?)",
                (
                    job_id,
                    kind,
                    dataset,
                    json.dumps(spec or {}),
                    plan_id,
                    os.getpid(),
                    now,
                    now,
                    _encode_follow_ups(follow_ups),
                ),
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

    def _jobs_in_states(self, states: Sequence[str]) -> list[JobRecord]:
        """Read all jobs needing lifecycle work, independently of UI pagination."""
        placeholders = ", ".join("?" for _ in states)
        rows = (
            self._connect()
            .execute(f"SELECT * FROM jobs WHERE status IN ({placeholders}) ORDER BY created_at DESC", states)
            .fetchall()
        )
        return [_decode(row) for row in rows]

    def update_job(self, job_id: str, **fields: Any) -> None:
        """Update columns; dict values are JSON-encoded into their *_json columns."""
        columns: list[str] = []
        values: list[Any] = []
        for name, value in fields.items():
            if name in ("spec", "progress", "cursor", "error"):
                columns.append(f"{name if name != 'spec' else 'spec'}_json = ?")
                values.append(json.dumps(value))
            elif name == "follow_ups":
                columns.append("follow_ups_json = ?")
                values.append(_encode_follow_ups(value))
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
        if job.status in ("pending", "interrupted"):
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
        for job in self._jobs_in_states(("running", "pending")):
            if not pid_check(job.pid):
                if job.error.get("cancel_requested"):
                    self.update_job(job.id, status="cancelled")
                else:
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

    def __init__(self, store: JobStore, data_dir: Path, follow_up_starter: FollowUpStarter | None = None):
        """Bind the runner to a store and data directory.

        Args:
            store: Where the jobs are kept.
            data_dir: The Pixano data directory imports write into.
            follow_up_starter: What queues an import's follow-ups once it is done. Without it, they
                are recorded as not queued.
        """
        self.store = store
        self.data_dir = Path(data_dir)
        self._follow_up_starter = follow_up_starter
        self._lock = threading.Lock()
        self._threads: list[threading.Thread] = []

    def submit_import(
        self,
        source: str,
        spec_payload: dict[str, Any],
        plan_id: str = "",
        prepare: Callable[[], tuple[str, dict[str, Any]]] | None = None,
        follow_ups: Sequence[FollowUp] = (),
    ) -> JobRecord:
        """Create a pending import job and start it on the worker thread.

        ``prepare`` (optional) runs FIRST on the job thread and returns the
        real (source, dataset-extras) pair — heavy source arrangement (e.g.
        the legacy alias's frame extraction) must never run on a request
        thread. A prepare failure marks the job errored.

        ``follow_ups`` are kept with the job and queued once the import is done.
        """
        job = self.store.create_job(
            "import",
            dataset=str(spec_payload.get("dataset", {}).get("name", "")),
            spec={**spec_payload, "__source": source},  # resume needs the source; stripped before validation
            plan_id=plan_id,
            follow_ups=follow_ups,
        )

        def run() -> None:
            resolved_source, payload = source, spec_payload
            if prepare is not None:
                try:
                    resolved_source, extras = prepare()
                    payload = {
                        **spec_payload,
                        "dataset": {**spec_payload.get("dataset", {}), **extras},
                    }
                    self.store.update_job(job.id, spec={**payload, "__source": resolved_source})
                except Exception as error:  # noqa: BLE001 - surfaced on the job record
                    self.store.update_job(job.id, status="error", error={"message": str(error)})
                    return
            self._run_import(job.id, resolved_source, payload, plan_id)

        thread = threading.Thread(target=run, daemon=True)
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
                self._discard_upload_source(source)
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
                # Queued before the job reads done, and recorded with it, so that whoever sees the
                # import done also sees what became of its follow-ups.
                follow_ups = queue_import_follow_ups(self.store, job_id, self._follow_up_starter, result.dataset_id)
                self.store.update_job(
                    job_id,
                    status="done",
                    dataset=result.dataset_id,
                    manifest_path=str(result.manifest_path or ""),
                    progress={"phase": "done", "table_counts": result.table_counts, "final": True},
                    follow_ups=follow_ups,
                )
                self._discard_upload_source(source)
            except PixanoDataError as error:
                cancelled = self.store.cancel_requested(job_id)
                self.store.update_job(
                    job_id,
                    status="cancelled" if cancelled else "error",
                    error={"type": type(error).__name__, "message": str(error)},
                )
                if cancelled:  # cancelled imports cannot resume; errored ones keep their upload
                    self._discard_upload_source(source)
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

    def _discard_upload_source(self, source: str) -> None:
        """Remove a staged client upload once its import can never resume again."""
        from .engine import state_dir

        uploads_root = state_dir(self.data_dir) / "uploads"
        try:
            session_dir = Path(source).resolve()
            if session_dir.parent == uploads_root.resolve():
                shutil.rmtree(session_dir, ignore_errors=True)
        except OSError:  # pragma: no cover - defensive
            pass

    def submit_export(
        self,
        dataset_path: str,
        destination: str,
        format: str,
        media: str,
        options: dict[str, Any] | None = None,
        review_statuses: Sequence[str] = (),
    ) -> JobRecord:
        """Create a pending export job and start it on the worker thread.

        ``review_statuses`` is the export's review-status selection (see ``ExportSpec``); the job
        spec records it when there is one.
        """
        spec: dict[str, Any] = {"format": format, "media": media, **(options or {})}
        if review_statuses:
            spec["review_statuses"] = list(review_statuses)
        job = self.store.create_job("export", dataset=Path(dataset_path).name, spec=spec)
        thread = threading.Thread(
            target=self._run_export,
            args=(job.id, dataset_path, destination, format, media, options, review_statuses),
            daemon=True,
        )
        self._threads.append(thread)
        thread.start()
        return job

    def _run_export(
        self,
        job_id: str,
        dataset_path: str,
        destination: str,
        format: str,
        media: str,
        options: dict[str, Any] | None = None,
        review_statuses: Sequence[str] = (),
    ) -> None:
        from .api import export_dataset

        with self._lock:
            if self.store.cancel_requested(job_id):
                self.store.update_job(job_id, status="cancelled")
                return
            self.store.update_job(job_id, status="running", pid=os.getpid(), heartbeat=time.time())
            try:
                exported = export_dataset(
                    dataset_path,
                    destination,
                    format=format,
                    media=media,
                    options=options,
                    review_statuses=review_statuses,
                )
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

    def rollback(self, job_id: str) -> dict[str, int]:
        """Roll back a finished add-mode import; the job flips to rolled_back."""
        from pixano.utils import to_snake_case

        from .engine import ImportEngine

        job = self.store.get_job(job_id)
        if job is None:
            raise JobStateError(f"Unknown job '{job_id}'.")
        if job.kind != "import" or job.status != "done":
            raise JobStateError(f"Job '{job_id}' is {job.status}; only completed imports roll back.")
        spec = job.spec
        dataset_name = to_snake_case(str(spec.get("dataset", {}).get("name", "")) or job.dataset)
        target_dir = self.data_dir / "library" / dataset_name
        if job.manifest_path:
            target_dir = Path(job.manifest_path).parent.parent
        removed = ImportEngine(self.data_dir).rollback(target_dir, job_id)
        self.store.update_job(job_id, status="rolled_back", progress={"phase": "rolled_back", "removed": removed})
        return removed

    def join(self, timeout: float | None = None) -> None:
        """Wait for in-flight jobs (tests and CLI teardown)."""
        for thread in self._threads:
            thread.join(timeout)


def _referenced_by_swap_journal(state: Path, artifact: Path) -> bool:
    """Keep recovery artifacts whenever an unresolved journal may need them."""
    for journal_file in (state / "journal").glob("*.json"):
        try:
            journal = json.loads(journal_file.read_text(encoding="utf-8"))
            paths = {Path(journal[key]).resolve() for key in ("target", "staging", "trash")}
        except FileNotFoundError:
            continue  # another dataset's completed promotion removed its journal
        except (OSError, ValueError, TypeError, KeyError):
            return True  # an unreadable journal cannot prove anything is garbage
        if artifact.resolve() in paths:
            return True
    return False


def boot_recover(data_dir: Path) -> Sequence[str]:
    """Server-boot hook: replay journals, mark orphaned jobs, reclaim dead state dirs."""
    from .engine import replay_journals, state_dir

    data_dir = Path(data_dir)
    replay_journals(data_dir)
    store = JobStore.for_data_dir(data_dir)
    flipped = store.mark_interrupted_on_boot()

    # Replay may skip a busy target or fail. Clean individual artifacts only
    # under their writer locks, then recheck journals and current job state.
    state = state_dir(data_dir)
    trash_root = state / "trash"
    if trash_root.is_dir():
        for trashed in trash_root.iterdir():
            target = data_dir / "library" / trashed.name.partition("-")[0]
            try:
                with dataset_mutation_lock(target):
                    if not _referenced_by_swap_journal(state, trashed):
                        shutil.rmtree(trashed, ignore_errors=True)
            except DatasetBusyError:
                continue
        try:
            trash_root.rmdir()  # never remove entries created after our scan
        except OSError:
            pass
    resumable = [
        job
        for job in store._jobs_in_states(("interrupted", "pending", "running", "error"))
        if job.kind == "import" and (job.status != "error" or job.cursor)
    ]
    staging_root = state / "staging"
    if staging_root.is_dir():
        for staged in staging_root.iterdir():
            dataset_name, _, job_id = staged.name.partition("-")
            target = data_dir / "library" / dataset_name
            try:
                with dataset_mutation_lock(staged), dataset_mutation_lock(target):
                    if _referenced_by_swap_journal(state, staged):
                        continue
                    job = store.get_job(job_id)
                    if (
                        job is not None
                        and job.kind == "import"
                        and (
                            job.status in ("pending", "running", "interrupted")
                            or (job.status == "error" and job.cursor)
                        )
                    ):
                        continue
                    shutil.rmtree(staged, ignore_errors=True)
            except DatasetBusyError:
                continue

    # Staged client uploads: kept while a resumable job imports from them, or
    # while fresh (an open wizard may still be uploading); orphans are garbage.
    uploads_root = state / "uploads"
    if uploads_root.is_dir():
        resumable_sources = {
            str(Path(source).resolve()) for job in resumable if (source := str(job.spec.get("__source", "")))
        }
        cutoff = time.time() - 24 * 3600
        for session_dir in uploads_root.iterdir():
            if str(session_dir.resolve()) in resumable_sources:
                continue
            try:
                if session_dir.stat().st_mtime >= cutoff:
                    continue
            except OSError:
                continue
            shutil.rmtree(session_dir, ignore_errors=True)
    return flipped
