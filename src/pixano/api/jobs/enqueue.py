# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Recording a job request on the queue.

The application records the request; the worker plans and executes it. Splitting work is
kind-specific logic — by video, by image, by selection — and kind code only ever runs in the
worker, so a job is written here without chunks, in state `planning`, and the worker expands
it. What the application does own is refusing a request that cannot succeed: an unknown kind,
or parameters that do not fit the kind's declared schema.

The worker owns the schema: this module never creates anything. On a database where the
worker has never run, the tables are simply absent and callers get `QueueUnavailableError`.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

import jsonschema
import psycopg
from psycopg.types.json import Jsonb

from . import queries


DEFAULT_LISTED_JOBS = 50


class QueueUnavailableError(RuntimeError):
    """The queue does not exist: the worker, which owns the schema, has never started."""


class JobNotFoundError(LookupError):
    """No job carries this identifier."""


class JobNotRetryableError(ValueError):
    """The job has not ended in error or cancellation, so there is nothing to retry."""


class UnknownKindError(ValueError):
    """No worker has declared it can run this job kind."""


class InvalidParamsError(ValueError):
    """The parameters do not match the schema the kind declared."""


@dataclass(frozen=True)
class JobRecord:
    """Un job tel que l'interface le voit."""

    id: str
    kind: str
    dataset: str
    state: str
    total_tasks: int
    done_tasks: int
    created_at: datetime
    produced: int = 0
    skipped: int = 0
    quarantined: int = 0
    cancel_requested: bool = False
    error: dict[str, Any] | None = None

    @classmethod
    def from_row(cls, row: Sequence[Any]) -> "JobRecord":
        """Build from a row of the projection every query shares."""
        return cls(
            id=str(row[0]),
            kind=row[1],
            dataset=row[2],
            state=row[3],
            total_tasks=row[4],
            done_tasks=row[5],
            created_at=row[6],
            produced=row[7],
            skipped=row[8],
            quarantined=row[9],
            cancel_requested=row[10],
            error=row[11],
        )


@dataclass(frozen=True)
class QuarantinedItem:
    """Un item qu'un job n'a pas su traiter, et pourquoi."""

    item_id: str
    reason: str
    detail: dict[str, Any] | None
    created_at: datetime


def connect(database_url: str | None) -> psycopg.Connection:
    """Open a connection to the queue, or refuse clearly.

    Raises:
        QueueUnavailableError: No URL is configured, or the database is unreachable.
    """
    if not database_url:
        raise QueueUnavailableError("no job queue is configured — set PIXANO_DATABASE_URL and start pixano-worker")
    try:
        return psycopg.connect(database_url)
    except psycopg.Error as error:
        raise QueueUnavailableError(f"the job queue is unreachable: {error}") from error


def _require_queue(conn: psycopg.Connection) -> None:
    """Check that the worker has installed the schema."""
    row = conn.execute(queries.QUEUE_EXISTS).fetchone()
    if row is None or row[0] is None:
        raise QueueUnavailableError("the job queue does not exist yet — start pixano-worker, which installs it")


def available_kinds(conn: psycopg.Connection) -> dict[str, dict[str, Any]]:
    """The job kinds a worker has declared it can run, with their parameter schemas."""
    _require_queue(conn)
    return {row[0]: row[1] for row in conn.execute(queries.LIST_KINDS).fetchall()}


def check_params(conn: psycopg.Connection, kind: str, params: dict[str, Any]) -> None:
    """Refuse a request no worker could run.

    Validating here spares the user a job that is queued only to fail, and spares the worker
    discovering a typo at planning time.

    Raises:
        UnknownKindError: No worker has declared this kind.
        InvalidParamsError: The parameters do not match the declared schema.
    """
    _require_queue(conn)
    row = conn.execute(queries.SELECT_KIND, (kind,)).fetchone()
    if row is None:
        declared = sorted(available_kinds(conn))
        known = ", ".join(declared) if declared else "none"
        raise UnknownKindError(f"no worker has declared the job kind '{kind}' — declared kinds: {known}")

    try:
        jsonschema.validate(params, row[0])
    except jsonschema.ValidationError as error:
        raise InvalidParamsError(f"invalid parameters for '{kind}': {error.message}") from error


def submit(
    conn: psycopg.Connection,
    *,
    kind: str,
    dataset_id: str,
    params: dict[str, Any] | None = None,
) -> JobRecord:
    """Record a job request; splitting it is the worker's business.

    Raises:
        QueueUnavailableError: The schema is not installed.
        UnknownKindError: No worker has declared this kind.
        InvalidParamsError: The parameters do not match the declared schema.
    """
    params = params or {}
    check_params(conn, kind, params)
    with conn.transaction():
        row = conn.execute(queries.INSERT_JOB, (kind, dataset_id, Jsonb(params))).fetchone()
        if row is None:  # pragma: no cover - RETURNING guarantees a row
            raise RuntimeError("inserting the job returned nothing")
    return JobRecord.from_row(row)


def get(conn: psycopg.Connection, job_id: str) -> JobRecord:
    """Read one job.

    Raises:
        JobNotFoundError: No job carries this identifier.
    """
    _require_queue(conn)
    try:
        uuid.UUID(job_id)
    except ValueError as error:
        # The schema types the identifier as uuid: any other string made the query itself fail,
        # answering 500 for what is an unknown job.
        raise JobNotFoundError(job_id) from error
    row = conn.execute(queries.SELECT_JOB, (job_id,)).fetchone()
    if row is None:
        raise JobNotFoundError(job_id)
    return JobRecord.from_row(row)


def list_jobs(conn: psycopg.Connection, limit: int = DEFAULT_LISTED_JOBS) -> list[JobRecord]:
    """List jobs, most recent first."""
    _require_queue(conn)
    return [JobRecord.from_row(row) for row in conn.execute(queries.LIST_JOBS, (limit,)).fetchall()]


def quarantine(conn: psycopg.Connection, job_id: str, limit: int) -> list[QuarantinedItem]:
    """The items a job set aside.

    Raises:
        JobNotFoundError: No job carries this identifier.
    """
    job = get(conn, job_id)
    rows = conn.execute(queries.LIST_QUARANTINE, (job.id, limit)).fetchall()
    return [QuarantinedItem(item_id=r[0], reason=r[1], detail=r[2], created_at=r[3]) for r in rows]


def cancel(conn: psycopg.Connection, job_id: str) -> JobRecord:
    """Ask for a job to stop.

    Pending chunks leave the queue at once; running ones are left to their worker, which stops
    before its next chunk. A job with nothing running becomes terminal immediately.

    The cancellation is announced on the event stream, in the same transaction: it is the one
    state change the application makes itself, and without an event every other client kept
    the job "running" until a reload. The event carries the job's state after the
    cancellation — settled, or still running while its chunks finish — and the request flag.

    Raises:
        JobNotFoundError: No job carries this identifier.
    """
    with conn.transaction():
        job = get(conn, job_id)
        requested = conn.execute(queries.REQUEST_CANCEL, (job.id,)).rowcount
        conn.execute(queries.CANCEL_PENDING_CHUNKS, (job.id,))
        settled = conn.execute(queries.SETTLE_IF_IDLE, (job.id, job.id)).fetchone()
        if requested:
            # Settled on the spot, or still in its previous state: a cancellation does not change it.
            payload = {"state": settled[0] if settled else job.state, "cancel_requested": True}
            conn.execute(queries.RECORD_EVENT, (job.id, "state", Jsonb(payload), queries.NOTIFY_CHANNEL))
    return get(conn, job_id)


def retry(conn: psycopg.Connection, job_id: str) -> JobRecord:
    """Run a job that ended in error or cancellation again, from where it stopped.

    Chunks that completed keep their results; those in error or cancelled go back to the
    queue with a fresh count of attempts. A job that never got chunks — its plan failed, or it
    was cancelled before a worker reached it — goes back to planning. The retry is announced
    on the event stream in the same transaction, like a cancellation.

    Raises:
        JobNotFoundError: No job carries this identifier.
        JobNotRetryableError: The job is not in error or cancelled.
    """
    with conn.transaction():
        job = get(conn, job_id)
        conn.execute(queries.RETRY_CHUNKS, (job.id,))
        reopened = conn.execute(queries.RETRY_JOB, (job.id,)).fetchone()
        if reopened is None:
            raise JobNotRetryableError(f"job {job.id} is {job.state}, only a job in error or cancelled can be retried")
        payload = {"state": reopened[0], "cancel_requested": False}
        conn.execute(queries.RECORD_EVENT, (job.id, "state", Jsonb(payload), queries.NOTIFY_CHANNEL))
    return get(conn, job_id)
