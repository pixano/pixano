# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Claiming and returning chunks.

The primitives the runner calls. They live here, apart from the loop, because they carry the
only properties that matter — no duplicate, no loss, and a recovery that depends on no live
process — and because we want to test them without a runner.

They are asynchronous because the runner is: it runs several chunks at once, and each one
mostly waits on the network.

Nothing here joins the jobs table. Claiming must remain a query over a single partial index:
that is why cancelling a job flips its pending chunks, rather than having the queue ask for
the job's state on every round.
"""

import os
import socket
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Iterable, Protocol, Sequence

import psycopg
from psycopg.types.json import Jsonb

from .config import MAX_HEARTBEAT_AGE_S
from .schema import NOTIFY_CHANNEL, SCHEMA_NAME


# The lease must outlast the window after which docker declares the worker dead, otherwise a
# chunk would be stolen before we even noticed that its holder no longer answers.
LEASE_TTL = timedelta(seconds=max(120, MAX_HEARTBEAT_AGE_S * 4))

# A running chunk extends its lease well before it expires: three opportunities per lease, so
# that one slow query or one hiccupping connection is not enough to lose it.
LEASE_REFRESH_INTERVAL = LEASE_TTL / 3

# Beyond this, a chunk is set aside rather than making the queue loop forever — whether it
# brings its worker down on every attempt or keeps hitting a failure that does not pass.
# Five, because with the delay below that leaves nearly four minutes for an inference to come
# back: the time of a restart with the model reloaded.
MAX_ATTEMPTS = 5

# Delay before replaying a chunk after a transient failure, doubled on each attempt. The cap
# keeps a chunk from vanishing for an hour over a failure already repaired.
RETRY_BASE_DELAY = timedelta(seconds=15)
RETRY_MAX_DELAY = timedelta(minutes=5)

CLAIM = f"""
UPDATE {SCHEMA_NAME}.job_chunks AS c
SET state = 'running',
    attempts = c.attempts + 1,
    claimed_by = %s,
    lease_until = now() + %s,
    updated_at = now()
FROM (
    SELECT id FROM {SCHEMA_NAME}.job_chunks
    WHERE state = 'pending' AND available_at <= now()
    ORDER BY id
    FOR UPDATE SKIP LOCKED
    LIMIT %s
) AS picked
WHERE c.id = picked.id
RETURNING c.id, c.job_id, c.seq, c.payload, c.task_count, c.attempts
"""

# `attempts` serves as a fencing token: a worker whose lease expired while it was working must
# not overwrite the result of the one that took its chunk over.
FINISH = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'done', lease_until = NULL, error = NULL, produced = %s, skipped = %s, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
RETURNING job_id, task_count
"""

# An item replayed with its chunk replaces its row: the quarantine reflects the last attempt,
# not the history of all of them.
QUARANTINE = f"""
INSERT INTO {SCHEMA_NAME}.job_items (job_id, chunk_id, item_id, reason, detail)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (job_id, item_id) DO UPDATE
SET chunk_id = EXCLUDED.chunk_id, reason = EXCLUDED.reason, detail = EXCLUDED.detail, created_at = now()
"""

# A transient failure returns the chunk to the queue after a delay — or sets it aside, if it
# has used up its attempts. Same fencing token as FINISH. Attempts are counted from the floor:
# a retried job starts over with a fresh count without `attempts` going backwards.
RETRY = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = CASE WHEN attempts - attempts_floor < %(max_attempts)s THEN 'pending' ELSE 'error' END,
    lease_until = NULL,
    claimed_by = CASE WHEN attempts - attempts_floor < %(max_attempts)s THEN NULL ELSE claimed_by END,
    available_at = now() + least(%(base)s * power(2, attempts - attempts_floor - 1), %(cap)s),
    error = %(error)s,
    updated_at = now()
WHERE id = %(id)s AND state = 'running' AND attempts = %(attempts)s
RETURNING state
"""

# The lease of a chunk still running. Same fencing token: a worker that lost its chunk cannot
# extend its successor's lease.
REFRESH_LEASE = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET lease_until = now() + %s, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
"""

FAIL = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'error', lease_until = NULL, error = %s, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
RETURNING job_id
"""

# A chunk whose job is cancelled does not go back to the queue: it leaves it. Making it
# "pending" would have it claimed again on the next round, released, claimed again — endlessly,
# and the job would never conclude for want of seeing its queue drain.
CANCEL_CHUNK = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'cancelled', lease_until = NULL, claimed_by = NULL, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
"""

RELEASE = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'pending', lease_until = NULL, claimed_by = NULL, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
"""

# What the worker does with its own chunks after a hard stop: return them right away, instead
# of waiting for their lease to expire. With the same cap as the lease recovery: a chunk that
# brings its worker down on every attempt would otherwise make an automatically restarted
# worker loop, since this path never looked at the attempts.
RELEASE_OWN = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'pending', lease_until = NULL, claimed_by = NULL, updated_at = now()
WHERE state = 'running' AND claimed_by = %s AND attempts - attempts_floor < %s
RETURNING id
"""

ABANDON_OWN = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'error', lease_until = NULL, updated_at = now(),
    error = jsonb_build_object('reason', 'abandoned after its attempts', 'attempts', attempts - attempts_floor)
WHERE state = 'running' AND claimed_by = %s AND attempts - attempts_floor >= %s
RETURNING job_id
"""

RECLAIM_EXPIRED = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'pending', lease_until = NULL, claimed_by = NULL, updated_at = now()
WHERE state = 'running' AND lease_until < now() AND attempts - attempts_floor < %s
RETURNING id
"""

ABANDON_EXHAUSTED = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'error', lease_until = NULL, updated_at = now(),
    error = jsonb_build_object('reason', 'abandoned after its attempts', 'attempts', attempts - attempts_floor)
WHERE state = 'running' AND lease_until < now() AND attempts - attempts_floor >= %s
RETURNING job_id
"""

# A job becomes running when its first chunk is claimed (START_JOBS), not when it finishes: a
# five-minute first chunk showed "pending" for five minutes under a bar that was about to move.
# This mark is set by a second query, after the tasks are launched, so that the claim itself
# never joins `jobs` and so that a crash right after leaves the chunks to their threads rather
# than to their lease. Jobs are locked in the order of their identifiers, as everywhere several
# `jobs` rows are taken at once.
START_JOBS = f"""
WITH picked AS (
    SELECT id FROM {SCHEMA_NAME}.jobs
    WHERE id = ANY(%s) AND state = 'pending'
    ORDER BY id
    FOR UPDATE
)
UPDATE {SCHEMA_NAME}.jobs AS j
SET state = 'running', updated_at = now()
FROM picked
WHERE j.id = picked.id
RETURNING j.id
"""

# The safety net of START_JOBS: if the mark was missed — a crash between the claim and it — the
# first finished chunk sets it. The previous state is read under the row lock, so that the
# caller knows whether it is the one that made the transition, and announces it only once.
ADVANCE_JOB = f"""
WITH previous AS (
    SELECT state FROM {SCHEMA_NAME}.jobs WHERE id = %(job)s FOR UPDATE
)
UPDATE {SCHEMA_NAME}.jobs AS j
SET done_tasks = j.done_tasks + %(tasks)s,
    state = CASE WHEN j.state = 'pending' THEN 'running' ELSE j.state END,
    updated_at = now()
FROM previous
WHERE j.id = %(job)s
RETURNING previous.state = 'pending', j.done_tasks, j.total_tasks
"""

# The insert and the doorbell in the same statement, hence the same transaction: PostgreSQL
# only delivers a NOTIFY at commit, which gives the "no event announced before it is readable"
# guarantee for free. The payload carries only identifiers — it is capped at 8 KB, and a reader
# must re-read the row anyway to catch up on what it missed.
RECORD_EVENT = f"""
WITH inserted AS (
    INSERT INTO {SCHEMA_NAME}.job_events (job_id, type, payload)
    VALUES (%s, %s, %s)
    RETURNING id, job_id, type
)
SELECT pg_notify(%s, json_build_object(
    'job_id', job_id, 'event_id', id, 'type', type
)::text) FROM inserted
"""

IS_CANCELLED = f"SELECT cancel_requested_at IS NOT NULL FROM {SCHEMA_NAME}.jobs WHERE id = %s"


@dataclass(frozen=True)
class Chunk:
    """A claimed batch of tasks, with the token that authorises writing its result."""

    id: int
    job_id: str
    seq: int
    payload: dict[str, Any]
    task_count: int
    attempts: int


# A stable identity, given by the deployment. Without it, the identity is host:pid — stable in
# a container, whose hostname is fixed and where the worker is process 1, but not for a worker
# launched by hand, whose pid changes on every relaunch: its chunks would only be taken back
# when their lease expires, two minutes, instead of right away.
WORKER_ID_VARIABLE = "PIXANO_WORKER_ID"


def worker_identity() -> str:
    """Name this worker, for diagnostics and for returning chunks after a hard stop.

    Two live workers must never carry the same name: the second would take over the first's
    chunks as if they were orphans.
    """
    given = os.environ.get(WORKER_ID_VARIABLE, "").strip()
    return given or f"{socket.gethostname()}:{os.getpid()}"


async def claim(conn: psycopg.AsyncConnection, worker_id: str, batch_size: int) -> list[Chunk]:
    """Claim up to `batch_size` pending chunks.

    Two workers claiming at the same time get disjoint sets: the row lock and `SKIP LOCKED`
    take care of it, without either one waiting for the other.
    """
    cursor = await conn.execute(CLAIM, (worker_id, LEASE_TTL, batch_size))
    rows = await cursor.fetchall()
    return [
        Chunk(id=row[0], job_id=str(row[1]), seq=row[2], payload=row[3], task_count=row[4], attempts=row[5])
        for row in rows
    ]


async def start_jobs(conn: psycopg.AsyncConnection, job_ids: Iterable[str]) -> list[str]:
    """Mark as running the jobs still pending among these, and announce it.

    The transition and its state event share a transaction, under each row's lock: the
    identifier of the `running` thus precedes those of the progress events and of the `done`,
    however many chunks finish at the same time.

    Returns:
        The jobs this call has made running.
    """
    ids = sorted(set(job_ids))
    if not ids:
        return []
    async with conn.transaction():
        rows = await (await conn.execute(START_JOBS, (ids,))).fetchall()
        started = [str(row[0]) for row in rows]
        for job_id in started:
            await record_event(conn, job_id, "state", {"state": "running"})
    return started


@dataclass(frozen=True)
class Recovery:
    """What a recovery of orphaned chunks did.

    Attributes:
        requeued: Chunks put back in the queue.
        abandoned_jobs: Jobs of which at least one chunk has just been set aside after its
            attempts. That chunk may have been the last of its job: the caller must conclude
            these jobs, otherwise a job with nothing left running would stay "running" forever.
    """

    requeued: int
    abandoned_jobs: frozenset[str]


@dataclass(frozen=True)
class Finished:
    """What finishing a chunk produced, beyond the chunk itself.

    Attributes:
        started_job: This chunk is the first finished of its job, which has just become
            running. This is the moment to announce the transition: without an event, an
            interface would keep showing "pending" under a bar that moves.
    """

    started_job: bool


class QuarantinedItem(Protocol):
    """What the queue reads from a quarantined item.

    A protocol rather than the model from the job kinds' contract: the queue is the bottom
    layer, it must import nothing from what builds on it.
    """

    @property
    def item_id(self) -> str: ...  # noqa: D102

    @property
    def reason(self) -> str: ...  # noqa: D102

    @property
    def detail(self) -> dict[str, Any] | None: ...  # noqa: D102


async def record_event(conn: psycopg.AsyncConnection, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
    """Record a progress event.

    Its counters are **absolute**, never increments: sequence identifiers are assigned before
    the commit, so two concurrent transactions can make their events visible out of order. A
    reader that skips one must be able to rely on the next.

    A **state** event, on the other hand, has no next one to repair it: it must be written in
    the transaction that changes the state, so that the order of identifiers is the order of
    states.
    """
    await conn.execute(RECORD_EVENT, (job_id, event_type, Jsonb(payload), NOTIFY_CHANNEL))


async def finish(
    conn: psycopg.AsyncConnection,
    chunk: Chunk,
    produced: int | None = None,
    skipped: int = 0,
    quarantined: Sequence[QuarantinedItem] = (),
) -> Finished | None:
    """Mark a chunk finished, record its outcome, and advance its job's progress.

    The outcome, the quarantine, the progress and its events are written in a single
    transaction: a chunk cannot be counted done without its set-aside items being recorded
    nor without the interface learning of it. The `running` event of the first finished chunk
    is written here too, under the job row's lock: this is what guarantees that its identifier
    precedes that of the `done` the last chunk will write — independent review, D2/D6.

    Args:
        conn: The chunk's connection.
        chunk: The claimed chunk.
        produced: Tasks produced. By default, all those that are neither skipped nor
            quarantined.
        skipped: Tasks not applicable.
        quarantined: Failed items.

    Returns:
        None if the chunk had been taken over by another worker in the meantime; the caller
        must then discard its result rather than overwrite its successor's.
    """
    if produced is None:
        produced = chunk.task_count - skipped - len(quarantined)
    async with conn.transaction():
        row = await (await conn.execute(FINISH, (produced, skipped, chunk.id, chunk.attempts))).fetchone()
        if row is None:
            return None
        for item in quarantined:
            await conn.execute(
                QUARANTINE,
                (chunk.job_id, chunk.id, item.item_id, item.reason, Jsonb(item.detail) if item.detail else None),
            )
        advanced = await (await conn.execute(ADVANCE_JOB, {"job": row[0], "tasks": row[1]})).fetchone()
        started = bool(advanced and advanced[0])
        if started:
            await record_event(conn, chunk.job_id, "state", {"state": "running"})
        if advanced is not None:
            await record_event(conn, chunk.job_id, "progress", {"done_tasks": advanced[1], "total_tasks": advanced[2]})
    return Finished(started_job=started)


async def retry_later(
    conn: psycopg.AsyncConnection, chunk: Chunk, error: dict[str, Any], max_attempts: int = MAX_ATTEMPTS
) -> str | None:
    """Return to the queue, after a delay, a chunk that hit a transient failure.

    Returns:
        `pending` if it will be replayed, `error` if it has used up its attempts, None if the
        chunk no longer belonged to it.
    """
    row = await (
        await conn.execute(
            RETRY,
            {
                "max_attempts": max_attempts,
                "base": RETRY_BASE_DELAY,
                "cap": RETRY_MAX_DELAY,
                "error": Jsonb(error),
                "id": chunk.id,
                "attempts": chunk.attempts,
            },
        )
    ).fetchone()
    return row[0] if row is not None else None


async def refresh_lease(conn: psycopg.AsyncConnection, chunk: Chunk) -> bool:
    """Extend the lease of a running chunk.

    Returns:
        False if the chunk no longer belongs to it: its lease expired and another took it over.
    """
    return (await conn.execute(REFRESH_LEASE, (LEASE_TTL, chunk.id, chunk.attempts))).rowcount > 0


async def fail(conn: psycopg.AsyncConnection, chunk: Chunk, error: dict[str, Any]) -> bool:
    """Mark a chunk failed. Same guard as `finish`."""
    cursor = await conn.execute(FAIL, (Jsonb(error), chunk.id, chunk.attempts))
    return await cursor.fetchone() is not None


async def release(conn: psycopg.AsyncConnection, chunk: Chunk) -> bool:
    """Put a chunk back in the queue without executing it."""
    return (await conn.execute(RELEASE, (chunk.id, chunk.attempts))).rowcount > 0


async def cancel_chunk(conn: psycopg.AsyncConnection, chunk: Chunk) -> bool:
    """Take out of the queue a chunk whose job was cancelled."""
    return (await conn.execute(CANCEL_CHUNK, (chunk.id, chunk.attempts))).rowcount > 0


async def release_own(conn: psycopg.AsyncConnection, worker_id: str, max_attempts: int = MAX_ATTEMPTS) -> Recovery:
    """Return the chunks left behind by a previous run of this same worker.

    The lease would eventually free them anyway; returning them at startup turns a two-minute
    recovery into an immediate one. Those that have used up their attempts are set aside, as
    by the lease recovery.
    """
    async with conn.transaction():
        requeued = len(await (await conn.execute(RELEASE_OWN, (worker_id, max_attempts))).fetchall())
        abandoned = await (await conn.execute(ABANDON_OWN, (worker_id, max_attempts))).fetchall()
    return Recovery(requeued=requeued, abandoned_jobs=frozenset(str(row[0]) for row in abandoned))


async def reclaim_expired(conn: psycopg.AsyncConnection, max_attempts: int = MAX_ATTEMPTS) -> Recovery:
    """Put back in the queue the chunks whose lease expired, set aside those that keep failing."""
    async with conn.transaction():
        requeued = len(await (await conn.execute(RECLAIM_EXPIRED, (max_attempts,))).fetchall())
        abandoned = await (await conn.execute(ABANDON_EXHAUSTED, (max_attempts,))).fetchall()
    return Recovery(requeued=requeued, abandoned_jobs=frozenset(str(row[0]) for row in abandoned))


async def is_cancelled(conn: psycopg.AsyncConnection, job_id: str) -> bool:
    """Has a cancellation been requested for this job?"""
    row = await (await conn.execute(IS_CANCELLED, (job_id,))).fetchone()
    return row is not None and bool(row[0])
