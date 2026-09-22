# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The worker's execution loop.

Two jobs, in this order on every turn: split the jobs waiting to be split, then consume chunks.
Planning goes first because a job that has not been split has no chunk to claim — otherwise a
lone worker could sleep in front of pending work.

Cancellation is checked **before each chunk**, never in the middle: a chunk is the atomic unit,
and interrupting it would leave half-done work nobody knows anything about.

The loop is asynchronous, the job kinds' code is not. `plan`, `process` and `write` are ordinary
functions — that is the published contract, and LanceDB reads and writes are blocking anyway.
So they go to a thread; the loop keeps for itself what benefits from being asynchronous: the
database, the delays and the lease.
"""

import asyncio
import logging
import threading
import traceback
from collections import OrderedDict, defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from collections.abc import Set as AbstractSet
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from pixano.datasets import Dataset

from . import queue
from .kinds import Chunk, JobKind, JobParams, Outcome, Registry, TransientError
from .media import MediaResolver
from .reader import JobReader
from .schema import SCHEMA_NAME
from .threads import WorkerThreads
from .writer import JobWriter


log = logging.getLogger("pixano-worker")

# What an unreachable database raises: connection dropped, server restarted, pool with no
# connection available. Nothing a job kind does — only access to the queue.
DATABASE_UNAVAILABLE = (psycopg.OperationalError, psycopg.InterfaceError)

# Spacing of the attempts when the database stops answering. Capped low, like the listener on
# the application side: a PostgreSQL restart lasts a few seconds, and a worker that comes back
# quickly resumes the work where it left it.
OUTAGE_BACKOFF_S = (1.0, 2.0, 5.0, 10.0)

# The time left to in-flight chunks to finish when the worker is stopped. Below the delay docker
# grants before killing the process (the compose's stop_grace_period), so that the chunks that
# did not finish in time are handed back to the queue rather than abandoned to their lease.
SHUTDOWN_GRACE_S = 30.0

# Pause after an unexpected exception in a loop turn: short, because the next turn has every
# chance of passing, and non-zero so that a fault that repeats does not fill the log.
UNEXPECTED_ERROR_PAUSE_S = 1.0

# A fault that repeats on every turn is logged with its traceback the first time, then once
# every N occurrences: the log says it persists, without a traceback per second.
UNEXPECTED_ERROR_LOG_EVERY = 60

# That many failures in a row — one minute, with the pause above — and the worker stops cleanly
# in error: a fault that does not pass in one minute will not pass in one hour, and a fresh
# process, relaunched by the restart policy, stands a better chance than one more turn. The
# in-flight chunks get their grace, then are handed back, as on any stop.
UNEXPECTED_ERROR_LIMIT = 60

# Beyond this delay, the queue is re-examined even with nothing new to do there: this is what
# hands the expired leases of a dead worker back to a busy worker, not only to an idle one.
RECLAIM_INTERVAL_S = 30.0

# Writes to a same dataset go one at a time. Several chunks of a dataset run at the same time,
# and LanceDB is not made for concurrent writes on a same table. The lock is a thread lock:
# `write` runs in a thread.
_write_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
_write_locks_guard = threading.Lock()


@lru_cache(maxsize=1)
def default_threads() -> WorkerThreads:
    """The pool for the calls that do not supply one — the tests, and the sequential form of the runner."""
    return WorkerThreads.for_concurrency(1)


def _write_lock(dataset_id: str) -> threading.Lock:
    with _write_locks_guard:
        return _write_locks[dataset_id]


# The job stays in `planning` while it is split: it is the lease that reserves it, not a state
# change. A planner that dies lets its lease expire, and the job becomes claimable again —
# instead of staying "running" with no chunk, which no recovery saw.
CLAIM_PLANNING = f"""
UPDATE {SCHEMA_NAME}.jobs SET planning_until = now() + %s, updated_at = now()
WHERE id = (
    SELECT id FROM {SCHEMA_NAME}.jobs
    WHERE state = 'planning' AND cancel_requested_at IS NULL
      AND (planning_until IS NULL OR planning_until < now())
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id, kind, dataset, params
"""

REFRESH_PLANNING = f"""
UPDATE {SCHEMA_NAME}.jobs SET planning_until = now() + %s
WHERE id = %s AND state = 'planning'
"""

INSERT_CHUNKS = f"""
INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, payload, task_count)
SELECT %s, chunk.seq, chunk.payload, chunk.task_count
FROM unnest(%s::int[], %s::jsonb[], %s::int[]) AS chunk(seq, payload, task_count)
"""

# Finishing the planning only applies to a job still being planned. Two planners can overlap —
# the first too slow, its lease taken over by a second: the update locks the row, the second
# waits, then no longer finds the job in `planning` and gives up instead of doubling the
# chunks.
FINISH_PLANNING = f"""
UPDATE {SCHEMA_NAME}.jobs
SET state = 'pending', total_tasks = %s, planning_until = NULL, updated_at = now()
WHERE id = %s AND state = 'planning'
RETURNING id
"""

FAIL_JOB = f"""
UPDATE {SCHEMA_NAME}.jobs SET state = 'error', error = %s, planning_until = NULL, updated_at = now()
WHERE id = %s AND state = 'planning'
RETURNING id
"""

# A job with no chunk left pending or running is finished. Cancellation wins over error: a job
# that was stopped is not a job that failed.
SETTLE = f"""
UPDATE {SCHEMA_NAME}.jobs AS j
SET state = CASE
        WHEN j.cancel_requested_at IS NOT NULL THEN 'cancelled'
        WHEN EXISTS (
            SELECT 1 FROM {SCHEMA_NAME}.job_chunks c
            WHERE c.job_id = j.id AND c.state = 'error'
        ) THEN 'error'
        ELSE 'done' END,
    updated_at = now()
WHERE j.id = %s
  AND j.state IN ('planning', 'pending', 'running')
  AND NOT EXISTS (
      SELECT 1 FROM {SCHEMA_NAME}.job_chunks c
      WHERE c.job_id = j.id AND c.state IN ('pending', 'running')
  )
RETURNING j.state
"""


OUTCOME = f"""
SELECT coalesce(sum(produced), 0)::int, coalesce(sum(skipped), 0)::int,
       (SELECT count(*) FROM {SCHEMA_NAME}.job_items WHERE job_id = %s)::int
FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s AND state = 'done'
"""


async def plan_one(
    conn: psycopg.AsyncConnection,
    registry: Registry,
    library: Path | None = None,
    media: MediaResolver | None = None,
    threads: WorkerThreads | None = None,
) -> str | None:
    """Split a job waiting to be planned.

    Returns:
        The identifier of the job that was split, or None if there was none.
    """
    row = await (await conn.execute(CLAIM_PLANNING, (queue.LEASE_TTL,))).fetchone()
    if row is None:
        return None
    job_id, kind_name, dataset_id, raw_params = str(row[0]), row[1], row[2], row[3]

    kind = registry.get(kind_name)
    if kind is None:
        # No live worker declares this kind. The job will never be runnable: saying so right
        # away is better than leaving it waiting with no explanation.
        await _fail_job(conn, job_id, {"reason": "unknown job kind", "kind": kind_name})
        log.warning("job %s: kind '%s' unknown to this worker", job_id, kind_name)
        return job_id

    async def refresh() -> bool:
        return (await conn.execute(REFRESH_PLANNING, (queue.LEASE_TTL, job_id))).rowcount > 0

    try:
        params = kind.validate_params(raw_params)
        reader = _reader_for(library, dataset_id, media, fresh=True)
        async with _kept_alive(refresh, f"planning of job {job_id}"):
            pool = threads or default_threads()
            writer = await pool.run(lambda: _writer_for(library, dataset_id, kind, job_id, params))
            # Preparation precedes the split, under the same lease: a planner that dies between
            # the two leaves a `prepare` done and no chunk, and the next one redoes both — that
            # is why `prepare` must be idempotent.
            await pool.run(lambda: kind.prepare(writer, params))
            chunks = await pool.run(lambda: list(kind.plan(reader, params)))
    except Exception as error:
        await _fail_job(conn, job_id, {"reason": "planning failed", "detail": str(error)})
        log.exception("job %s: planning failed", job_id)
        return job_id

    if not chunks:
        await _fail_job(conn, job_id, {"reason": "planning produced no work"})
        return job_id

    try:
        recorded = await record_plan(conn, job_id, chunks)
    except DATABASE_UNAVAILABLE:
        raise
    except Exception as error:
        # A chunk the schema refuses — with no task, a payload that does not serialise — is a
        # fault of the job kind, not of the worker: the job fails and says so, the worker goes
        # on. Left to propagate, it killed the worker and left the job in planning under its lease.
        await _fail_job(conn, job_id, {"reason": "the planned chunks were refused by the queue", "detail": str(error)})
        log.exception("job %s: chunks refused at recording", job_id)
        return job_id
    if recorded:
        log.info("job %s split into %d chunks (%d tasks)", job_id, len(chunks), sum(c.task_count for c in chunks))
    else:
        log.info("job %s: split abandoned, the job is no longer in planning", job_id)
    return job_id


async def record_plan(conn: psycopg.AsyncConnection, job_id: str, chunks: list[Chunk]) -> bool:
    """Record a job's chunks and move it to pending, if it is still in planning.

    The job update goes first: it locks its row, so that a second planner waits, then finds
    that the job is no longer to be planned.

    Returns:
        False if the job was no longer in planning — already split by another worker —, in
        which case nothing is written.
    """
    total = sum(chunk.task_count for chunk in chunks)
    async with conn.transaction():
        finished = await (await conn.execute(FINISH_PLANNING, (total, job_id))).fetchone()
        if finished is None:
            return False
        await conn.execute(
            INSERT_CHUNKS,
            (
                job_id,
                list(range(len(chunks))),
                [Jsonb(chunk.payload) for chunk in chunks],
                [chunk.task_count for chunk in chunks],
            ),
        )
        await queue.record_event(
            conn, job_id, "state", {"state": "pending", "total_tasks": total, "chunks": len(chunks)}
        )
    return True


async def _fail_job(conn: psycopg.AsyncConnection, job_id: str, error: dict[str, Any]) -> None:
    async with conn.transaction():
        if await (await conn.execute(FAIL_JOB, (Jsonb(error), job_id))).fetchone() is not None:
            await queue.record_event(conn, job_id, "state", {"state": "error", **error})


# The open datasets, few at a time: a worker rarely handles more than a handful in a same
# period. An ordered dictionary rather than an `lru_cache`, to be able to invalidate a single
# one — clearing the whole cache to reopen one dataset made the others reopen too.
_OPEN_DATASETS_MAX = 8
_open_datasets: OrderedDict[tuple[Path, str], Dataset] = OrderedDict()
_open_datasets_guard = threading.Lock()


def _open_dataset(library: Path, dataset_id: str) -> Dataset:
    """Open a dataset, once; serve it from the cache afterwards."""
    key = (library, dataset_id)
    with _open_datasets_guard:
        cached = _open_datasets.get(key)
        if cached is not None:
            _open_datasets.move_to_end(key)
            return cached
    opened = Dataset.find(dataset_id, library)
    with _open_datasets_guard:
        _open_datasets[key] = opened
        _open_datasets.move_to_end(key)
        while len(_open_datasets) > _OPEN_DATASETS_MAX:
            _open_datasets.popitem(last=False)
    return opened


def _reopen_dataset(library: Path, dataset_id: str) -> Dataset:
    """Reopen this dataset bypassing the cache, and replace what the cache held of it."""
    with _open_datasets_guard:
        _open_datasets.pop((library, dataset_id), None)
    return _open_dataset(library, dataset_id)


def _reader_for(library: Path | None, dataset_id: str, media: MediaResolver | None, fresh: bool = False) -> JobReader:
    """Bind a reader to a job's dataset, opened only if the kind uses it.

    Args:
        library: The dataset library; None if none is configured.
        dataset_id: The job's dataset.
        media: The media resolver.
        fresh: Reopen the dataset bypassing the cache. Planning asks for it: it is a job's
            first look at its dataset, and a dataset recreated under the worker — reimported,
            its embeddings table dropped — was otherwise seen as it was at the previous
            opening, until the worker restarted. The chunks, for their part, read what
            planning reopened.
    """

    def open_dataset() -> Dataset:
        if library is None:
            raise RuntimeError("no dataset library configured: PIXANO_LIBRARY_DIR is empty")
        return _reopen_dataset(library, dataset_id) if fresh else _open_dataset(library, dataset_id)

    return JobReader(open_dataset, media or MediaResolver.unconfigured())


def _writer_for(
    library: Path | None, dataset_id: str, kind: JobKind, job_id: str, params: JobParams | None = None
) -> JobWriter:
    """Bind a writer to a job's dataset, carrying the job's provenance.

    Opening is deferred to first use: a kind that writes nothing must not fail for lack of a
    dataset, and the absence of a library only shows if someone writes. With `params`, the
    writer records them and asks the kind which model it runs — a call that may reach the
    inference server, so this runs in the job's thread, never on the loop.
    """

    def open_dataset() -> Dataset:
        if library is None:
            raise RuntimeError("no dataset library configured: PIXANO_LIBRARY_DIR is empty")
        return _open_dataset(library, dataset_id)

    def reopen_dataset() -> Dataset:
        if library is None:
            raise RuntimeError("no dataset library configured: PIXANO_LIBRARY_DIR is empty")
        return _reopen_dataset(library, dataset_id)

    return JobWriter(
        open_dataset,
        kind.name,
        job_id,
        kind.source_type,
        reopen_dataset,
        dataset_id,
        params=kind.provenance_params(params) if params is not None else None,
        model=kind.model_identity(params) if params is not None else None,
    )


async def work(
    pool: AsyncConnectionPool,
    registry: Registry,
    worker_id: str,
    concurrency: int,
    library: Path | None = None,
    media: MediaResolver | None = None,
    idle_poll_s: float = 5.0,
    chunk_timeout_s: float | None = None,
    threads: WorkerThreads | None = None,
    stop: asyncio.Event | None = None,
) -> None:
    """Keep up to `concurrency` chunks in flight, until a stop is requested.

    Claiming never takes more than the free slots: a claimed chunk carries a running lease, and
    claiming it to leave it waiting for a slot would expose it to expiring before it started.

    A stop requested through `stop` cuts nothing: the loop stops claiming, gives the in-flight
    chunks `SHUTDOWN_GRACE_S` to finish, then returns. Those still running remain claimed by
    this worker; it is up to the caller to hand them back.

    A saturated pool — too many threads stuck on chunks handed back for exceeding their time
    limit — is renewed in place, and the loop goes on.

    Raises:
        PersistentFailure: The loop failed `UNEXPECTED_ERROR_LIMIT` times in a row. The
            in-flight chunks had their grace; the caller hands back those that remain, as on
            any stop.
    """
    owns_threads = threads is None
    threads = threads or WorkerThreads.for_concurrency(concurrency)
    stop = stop or asyncio.Event()
    try:
        await _loop(
            pool, registry, worker_id, concurrency, library, media, idle_poll_s, chunk_timeout_s, threads, stop
        )
    finally:
        if owns_threads:
            threads.shutdown()


class PersistentFailure(RuntimeError):
    """The loop failed `UNEXPECTED_ERROR_LIMIT` times in a row and stopped."""


async def _loop(
    pool: AsyncConnectionPool,
    registry: Registry,
    worker_id: str,
    concurrency: int,
    library: Path | None,
    media: MediaResolver | None,
    idle_poll_s: float,
    chunk_timeout_s: float | None,
    threads: WorkerThreads,
    stop: asyncio.Event,
) -> None:
    in_flight: set[asyncio.Task[None]] = set()
    loop = asyncio.get_running_loop()
    last_reclaim = loop.time()
    outages = 0
    failures = 0
    broken = False

    while not stop.is_set():
        if threads.saturated:
            abandoned = threads.renew()
            log.error(
                "%d thread(s) stuck on chunks handed back for exceeding their time limit: abandoned, "
                "the worker starts over with fresh threads",
                abandoned,
            )
        # A database that restarts must not kill the worker: it waits for it to come back, as at
        # startup. In-flight chunks are not touched — each manages its own connection, and an
        # interrupted chunk keeps its lease until recovery hands it back.
        try:
            async with pool.connection() as conn:
                planned = await plan_one(conn, registry, library, media, threads)

            claimed: list[queue.Chunk] = []
            free = concurrency - len(in_flight)
            if free > 0:
                async with pool.connection() as conn:
                    claimed = await queue.claim(conn, worker_id, free)
            # Started as soon as claimed, before any other database access: a claimed chunk
            # carries a running lease, and an outage right after would leave it with nobody to
            # do it.
            for chunk in claimed:
                task = asyncio.create_task(
                    _run_pooled(pool, registry, chunk, library, media, chunk_timeout_s, threads)
                )
                in_flight.add(task)
                task.add_done_callback(in_flight.discard)
            # Only once the tasks are started: their jobs move to running, and the interface
            # learns it, without the work depending on this second query.
            if claimed:
                async with pool.connection() as conn:
                    await queue.start_jobs(conn, (chunk.job_id for chunk in claimed))

            if loop.time() - last_reclaim >= RECLAIM_INTERVAL_S:
                last_reclaim = loop.time()
                async with pool.connection() as conn:
                    recovery = await queue.reclaim_expired(conn)
                    await settle_abandoned(conn, recovery)
                if recovery.requeued or recovery.abandoned_jobs:
                    log.info(
                        "expired leases: %d chunk(s) put back in the queue, %d job(s) with a chunk set aside",
                        recovery.requeued,
                        len(recovery.abandoned_jobs),
                    )
        except DATABASE_UNAVAILABLE as error:
            delay = OUTAGE_BACKOFF_S[min(outages, len(OUTAGE_BACKOFF_S) - 1)]
            outages += 1
            log.warning("database unreachable (%s) — retrying in %ss", error, delay)
            await _pause(stop, delay)
            continue
        except Exception:
            # An unexpected fault in a loop turn — a database response the code does not
            # anticipate, a bug — is logged with its traceback, and the next turn takes place.
            # Letting it propagate stopped the worker for good, in-flight chunks included,
            # without making anything more visible than that traceback.
            failures += 1
            if failures >= UNEXPECTED_ERROR_LIMIT:
                log.exception("loop turn failed %d times in a row: the worker stops", failures)
                stop.set()
                broken = True
                break
            if failures == 1 or failures % UNEXPECTED_ERROR_LOG_EVERY == 0:
                log.exception("loop turn failed (%d times in a row), the worker goes on", failures)
            await _pause(stop, UNEXPECTED_ERROR_PAUSE_S)
            continue
        if failures:
            log.info("the loop passes again after %d failed turn(s)", failures)
            failures = 0
        if outages:
            log.info("database reachable again after %d attempt(s)", outages)
            outages = 0

        if len(in_flight) >= concurrency:
            # Bounded: a full worker must still hand back expired leases and plan. Without a
            # bound, recovery waited for the end of its first chunk — independent review, D7.
            await _pause(stop, RECLAIM_INTERVAL_S, in_flight)
        elif planned is None and not claimed:
            # Nothing new: wait for a slot to free up or for work to arrive.
            await _pause(stop, idle_poll_s, in_flight)

    if in_flight:
        log.info("stop requested: %d chunk(s) in flight, %ss to finish", len(in_flight), SHUTDOWN_GRACE_S)
        _, unfinished = await asyncio.wait(in_flight, timeout=SHUTDOWN_GRACE_S)
        for task in unfinished:
            task.cancel()
        if unfinished:
            await asyncio.wait(unfinished)
            log.info("%d chunk(s) did not finish in time", len(unfinished))
    if broken:
        raise PersistentFailure(f"{UNEXPECTED_ERROR_LIMIT} loop turns failed in a row")


async def _pause(
    stop: asyncio.Event, timeout_s: float | None, in_flight: AbstractSet[asyncio.Task[None]] = frozenset()
) -> None:
    """Wait for a chunk to finish, for the delay to pass, or for a stop to be requested.

    A stop interrupts the wait: a worker stopped during a pause of several seconds must not
    make docker wait for nothing.
    """
    stopping = asyncio.ensure_future(stop.wait())
    try:
        await asyncio.wait({stopping, *in_flight}, timeout=timeout_s, return_when=asyncio.FIRST_COMPLETED)
    finally:
        stopping.cancel()


async def _run_pooled(
    pool: AsyncConnectionPool,
    registry: Registry,
    chunk: queue.Chunk,
    library: Path | None,
    media: MediaResolver | None,
    chunk_timeout_s: float | None,
    threads: WorkerThreads,
) -> None:
    """Run a chunk on its own connection, without ever bringing the loop down.

    A database outage in the middle of a chunk leaves it running with its lease: expiry will
    hand it back. Letting the exception propagate would not hand it back any sooner, and would
    silently kill a task nobody awaits.
    """
    try:
        async with pool.connection() as conn:
            await run_chunk(conn, registry, chunk, library, media, chunk_timeout_s, threads)
    except DATABASE_UNAVAILABLE as error:
        # Expected during an outage: a warning, not a traceback per in-flight chunk.
        log.warning(
            "chunk %s of job %s: database unreachable (%s), it will come back through its lease",
            chunk.seq,
            chunk.job_id,
            error,
        )
    except Exception:
        log.exception("chunk %s of job %s: failure outside the job kind", chunk.seq, chunk.job_id)


async def run_batch(
    conn: psycopg.AsyncConnection,
    registry: Registry,
    worker_id: str,
    batch_size: int,
    library: Path | None = None,
    media: MediaResolver | None = None,
) -> int:
    """Claim a batch of chunks and run them one after the other on one connection.

    The sequential form of `work`, with no pool and no tasks: it is the one the tests drive,
    because it makes the order of events deterministic.

    Returns:
        The number of chunks processed — zero when the queue is empty.
    """
    chunks = await queue.claim(conn, worker_id, batch_size)
    await queue.start_jobs(conn, (chunk.job_id for chunk in chunks))
    for chunk in chunks:
        await run_chunk(conn, registry, chunk, library, media)
    return len(chunks)


async def run_chunk(
    conn: psycopg.AsyncConnection,
    registry: Registry,
    chunk: queue.Chunk,
    library: Path | None = None,
    media: MediaResolver | None = None,
    timeout_s: float | None = None,
    threads: WorkerThreads | None = None,
) -> None:
    """Run a claimed chunk, record what comes out of it, and settle its job if need be.

    Args:
        conn: The connection specific to this chunk.
        registry: The known job kinds.
        chunk: The claimed chunk.
        library: The dataset library.
        media: The media resolver.
        timeout_s: Maximum duration of the chunk. Beyond it, it is handed back to the queue as
            after a transient failure. None: no limit.
        threads: The pool where the job kind's code runs.
    """
    await _execute(conn, registry, chunk, library, media, timeout_s, threads or default_threads())
    await settle(conn, chunk.job_id)


async def _execute(
    conn: psycopg.AsyncConnection,
    registry: Registry,
    chunk: queue.Chunk,
    library: Path | None,
    media: MediaResolver | None,
    timeout_s: float | None,
    threads: WorkerThreads,
) -> None:
    if await queue.is_cancelled(conn, chunk.job_id):
        await queue.cancel_chunk(conn, chunk)
        return

    row = await (
        await conn.execute(f"SELECT kind, params, dataset FROM {SCHEMA_NAME}.jobs WHERE id = %s", (chunk.job_id,))
    ).fetchone()
    kind = registry.get(row[0]) if row is not None else None
    if row is None or kind is None:
        await queue.fail(conn, chunk, {"reason": "unknown job kind"})
        return
    kind_name, raw_params, dataset_id = row

    def work() -> Outcome:
        params = kind.validate_params(raw_params)
        result = kind.process(_reader_for(library, dataset_id, media), chunk.payload, params)
        outcome = kind.outcome(result, chunk.payload, chunk.task_count)
        if outcome.total != chunk.task_count:
            # A wrong outcome would distort everything displayed about the job; better a failed
            # chunk that points at the kind's fault than a count that lies silently.
            raise ValueError(
                f"the outcome of kind '{kind_name}' covers {outcome.total} task(s), "
                f"the chunk counts {chunk.task_count}"
            )
        writer = _writer_for(library, dataset_id, kind, chunk.job_id, params)
        with _write_lock(dataset_id):
            kind.write(writer, result, chunk.payload, params)
        return outcome

    try:
        async with _kept_alive(lambda: queue.refresh_lease(conn, chunk), f"chunk {chunk.seq} of job {chunk.job_id}"):
            outcome = await threads.run(work, timeout_s)
    except TimeoutError:
        # The thread does not stop: a blocked call cannot be interrupted from the outside. The
        # chunk is handed back, and if the thread eventually completes, its result will be
        # refused by the guard token — and its write, idempotent, will have doubled nothing. The
        # pool counts this thread as stuck; if there are too many, the loop will stop the worker.
        await _retry_later(conn, chunk, {"reason": "time limit exceeded", "timeout_s": timeout_s})
        return
    except TransientError as error:
        await _retry_later(conn, chunk, {"reason": "transient failure", "detail": str(error)})
        return
    except DATABASE_UNAVAILABLE:
        # Never a failure of the job kind: the chunk keeps its lease, recovery will hand it back.
        raise
    except Exception as error:
        await queue.fail(conn, chunk, {"reason": str(error), "trace": traceback.format_exc(limit=3)})
        log.warning("chunk %s of job %s failed: %s", chunk.seq, chunk.job_id, error)
        return

    finished = await queue.finish(
        conn, chunk, produced=outcome.produced, skipped=outcome.skipped, quarantined=outcome.quarantined
    )
    if finished is None:
        # The lease had expired and another worker took the chunk over: its result is
        # authoritative.
        log.info("chunk %s of job %s taken over elsewhere, result dropped", chunk.seq, chunk.job_id)
        return
    if outcome.quarantined:
        log.info("chunk %s of job %s: %d item(s) quarantined", chunk.seq, chunk.job_id, len(outcome.quarantined))


async def _retry_later(conn: psycopg.AsyncConnection, chunk: queue.Chunk, error: dict[str, Any]) -> None:
    state = await queue.retry_later(conn, chunk, error)
    if state == "pending":
        log.info(
            "chunk %s of job %s handed back to the queue (%s), attempt %d",
            chunk.seq,
            chunk.job_id,
            error["reason"],
            chunk.attempts,
        )
    elif state == "error":
        log.warning(
            "chunk %s of job %s set aside after %d attempts: %s",
            chunk.seq,
            chunk.job_id,
            chunk.attempts,
            error["reason"],
        )


@asynccontextmanager
async def _kept_alive(refresh: Callable[[], Awaitable[bool]], label: str) -> AsyncIterator[None]:
    """Extend a lease as long as the block runs — a chunk's or a planning's.

    Refreshing stops through a signal, not a cancellation: cancelling a task in the middle of a
    query can leave the connection in an unusable state, and it is that connection the caller
    reuses right after.

    A database unreachable at refresh time is not an error of the protected work: the keeper
    logs it and retries at the next interval. Letting it propagate made a chunk whose
    computation had succeeded be classed as fatal — seen in review. If the database stays
    down, the lease expires and the guard token will refuse the result: that is the intended
    path.

    Args:
        refresh: Extends the lease; returns False if the lease no longer belongs to this worker.
        label: What the lease protects, for the log.
    """
    stop = asyncio.Event()

    async def keep() -> None:
        interval = queue.LEASE_REFRESH_INTERVAL.total_seconds()
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), interval)
            except TimeoutError:
                try:
                    kept = await refresh()
                except DATABASE_UNAVAILABLE as error:
                    log.warning("%s: lease not refreshed, database unreachable (%s)", label, error)
                    continue
                if not kept:
                    log.warning("%s: lease lost while running", label)
                    return

    keeper = asyncio.create_task(keep())
    try:
        yield
    finally:
        stop.set()
        await keeper


async def settle_abandoned(conn: psycopg.AsyncConnection, recovery: queue.Recovery) -> None:
    """Settle the jobs from which a recovery has just set a chunk aside.

    No chunk of these jobs will finish to settle them if that one was the last: recovery itself
    has to take care of it.
    """
    for job_id in sorted(recovery.abandoned_jobs):
        await settle(conn, job_id)


async def settle(conn: psycopg.AsyncConnection, job_id: str) -> None:
    """Settle a job with nothing left pending or running, saying what it produced."""
    # Settlement and event in one transaction: a worker killed between the two left a `done` job
    # whose end the interface only learned on reload — independent review, D6.
    async with conn.transaction():
        row = await (await conn.execute(SETTLE, (job_id,))).fetchone()
        if row is None:
            return
        outcome = await job_outcome(conn, job_id)
        await queue.record_event(conn, job_id, "state", {"state": row[0], **outcome})
    log.info(
        "job %s finished: %s — %d produced, %d skipped, %d quarantined",
        job_id,
        row[0],
        outcome["produced"],
        outcome["skipped"],
        outcome["quarantined"],
    )


async def job_outcome(conn: psycopg.AsyncConnection, job_id: str) -> dict[str, int]:
    """A job's outcome, aggregated from its chunks and its quarantine.

    Aggregated at read time rather than kept as counters on the job: that would be one more
    count that could drift from what it summarises.
    """
    row = await (await conn.execute(OUTCOME, (job_id, job_id))).fetchone()
    assert row is not None
    return {"produced": row[0], "skipped": row[1], "quarantined": row[2]}
