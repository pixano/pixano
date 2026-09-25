# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Entry point of the Pixano worker.

The worker waits for its dependencies, then loops. It shares nothing with the API: no
process, no memory, no file system — everything goes through PostgreSQL. This is what lets
it run on a different machine than the application, which is the normal situation as soon
as we leave local mode.

Startup is synchronous — waiting for dependencies, installing the schema and declaring its
kinds happens once and in order. Only the work loop is asynchronous.
"""

import asyncio
import logging
import os
import signal
import sys
import time
from pathlib import Path
from typing import Callable

import httpx
import psycopg
from psycopg_pool import AsyncConnectionPool

from . import queue, runner
from .config import MAX_HEARTBEAT_AGE_S, MissingConfigurationError, WorkerConfig
from .kinds import Registry, default_registry
from .media import MediaResolver
from .schema import SchemaVersionError, ensure_schema
from .threads import WorkerThreads


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("pixano-worker")

# The worker beats once per waiting round: the maximum spacing between attempts therefore
# bounds the age of the heartbeat. Keeping it well under MAX_HEARTBEAT_AGE_S avoids declaring
# dead a worker that is waiting for an absent dependency.
MAX_BACKOFF_S = MAX_HEARTBEAT_AGE_S / 3
IDLE_POLL_INTERVAL_S = 5
CONNECT_TIMEOUT_S = 5

# The heartbeat no longer depends on a loop iteration: a long chunk must not get a working
# worker declared dead. What it proves from now on is that the event loop is not blocked. A
# hung chunk, for its part, is a matter for the maximum duration of a chunk.
HEARTBEAT_INTERVAL_S = MAX_HEARTBEAT_AGE_S / 3


def _wait_for(label: str, probe: Callable[[], None], on_attempt: Callable[[], None]) -> None:
    """Retry a probe until it passes, spacing out the attempts.

    `on_attempt` is called on every round: a worker waiting for an absent dependency is alive
    and doing its job, it must not be declared dead by the docker probe. The missing
    dependency shows on the service concerned, not here.
    """
    backoff = 1.0
    while True:
        on_attempt()
        try:
            probe()
            log.info("%s: available", label)
            return
        except Exception as exc:
            log.warning("%s: unavailable (%s: %s) — retrying in %ss", label, exc.__class__.__name__, exc, backoff)
            time.sleep(backoff)
            backoff = min(backoff * 2, MAX_BACKOFF_S)


def wait_for_database(database_url: str, on_attempt: Callable[[], None]) -> None:
    """Wait until PostgreSQL accepts a connection."""

    def probe() -> None:
        with psycopg.connect(database_url, connect_timeout=CONNECT_TIMEOUT_S) as conn, conn.cursor() as cur:
            cur.execute("SELECT 1")

    _wait_for("postgresql", probe, on_attempt)


def wait_for_inference(inference_url: str, api_key: str, on_attempt: Callable[[], None]) -> None:
    """Wait until the inference server answers on /health."""
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}

    def probe() -> None:
        httpx.get(f"{inference_url.rstrip('/')}/health", headers=headers, timeout=3).raise_for_status()

    _wait_for("pixano-inference", probe, on_attempt)


def beat(heartbeat_path: str) -> None:
    """Mark the worker alive for the docker probe.

    Opening the file for writing is enough: it is its modification time that the probe reads.
    """
    with open(heartbeat_path, "w"):
        pass


def main() -> int:
    """Start the worker."""
    try:
        config = WorkerConfig.from_env()
    except MissingConfigurationError as exc:
        log.error("incomplete configuration: %s", exc)
        return 1

    log.info("worker configuration:\n%s", config.describe())

    def alive() -> None:
        beat(config.heartbeat_path)

    alive()
    wait_for_database(config.database_url, alive)

    # The schema is checked before waiting for the inference: an incompatible schema is fatal,
    # and the operator must learn it in two seconds, not after five minutes of politely
    # waiting for a server this worker will never use.
    try:
        with psycopg.connect(config.database_url, connect_timeout=CONNECT_TIMEOUT_S) as conn:
            ensure_schema(conn)
    except SchemaVersionError as exc:
        log.error("%s", exc)
        return 1
    except psycopg.Error as exc:
        log.error("cannot install the schema: %s", exc)
        return 1

    alive()
    wait_for_inference(config.inference_url, config.inference_api_key, alive)

    registry = default_registry(config.inference_url, config.inference_api_key, config.demo_kinds)
    worker_id = queue.worker_identity()

    with psycopg.connect(config.database_url, connect_timeout=CONNECT_TIMEOUT_S, autocommit=True) as conn:
        declared = registry.declare(conn, worker_id)
    log.info("worker %s: %d kind(s) declared — %s", worker_id, declared, ", ".join(registry.names()))

    media = MediaResolver(config.media_root, config.inference_media_root)
    code = asyncio.run(
        serve(
            config.database_url,
            registry,
            worker_id,
            alive,
            Path(config.library_dir),
            media,
            config.concurrency,
            config.chunk_timeout_s,
        )
    )
    # Without waiting for the threads: after a shutdown, some may stay stuck on a call that
    # never returns, and a normal exit would wait for them forever.
    _exit_now(code)
    return code


def _exit_now(code: int) -> None:
    """Exit without waiting for the threads.

    A normal exit waits for every thread to finish — yet some never finish. The logs are
    flushed first, so that the shutdown message is readable.
    """
    logging.shutdown()
    os._exit(code)


async def serve(
    database_url: str,
    registry: Registry,
    worker_id: str,
    alive: Callable[[], None],
    library: Path,
    media: MediaResolver,
    concurrency: int,
    chunk_timeout_s: float,
) -> int:
    """Beat, then plan, execute, and recover what others have abandoned.

    Returns:
        The exit code: 0 after a requested shutdown, 1 when the loop stopped on its own on a
        persistent failure — so that the restart policy launches a fresh process.
    """
    heartbeat = asyncio.create_task(_beat_forever(alive))
    threads = WorkerThreads.for_concurrency(concurrency)

    # `docker compose stop` sends SIGTERM. The worker is process 1 of the container, and the
    # kernel ignores SIGTERM for a process 1 without a handler: docker waited out its grace
    # period then killed the worker, in-flight chunks included.
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stop.set)

    # One connection per in-flight chunk, plus one to plan, claim and recover.
    async with AsyncConnectionPool(
        database_url,
        min_size=1,
        max_size=concurrency + 1,
        kwargs={"autocommit": True, "connect_timeout": CONNECT_TIMEOUT_S},
        # The pool does not wait for a connection longer than we wait to open one. Its default
        # timeout is 30 s, paid on every borrow during an outage: a shutdown requested during
        # the outage then exceeded docker's grace period and ended up killed.
        timeout=CONNECT_TIMEOUT_S,
        # Check a connection before lending it: after a PostgreSQL restart, the pool keeps dead
        # connections, and without a check it would hand them to the loop one by one.
        check=AsyncConnectionPool.check_connection,
        open=False,
    ) as pool:
        async with pool.connection() as conn:
            # What this same identity left behind during a brutal shutdown. The lease would
            # eventually release them; handing them back right away avoids waiting for it to
            # expire.
            recovery = await queue.release_own(conn, worker_id)
            await runner.settle_abandoned(conn, recovery)
        if recovery.requeued:
            log.info("%d chunk(s) recovered from a previous run", recovery.requeued)
        if recovery.abandoned_jobs:
            log.warning(
                "%d job(s) with a chunk set aside: it brought this worker down on each of its attempts",
                len(recovery.abandoned_jobs),
            )

        log.info("worker started, waiting for jobs")
        code = 0
        try:
            try:
                await runner.work(
                    pool,
                    registry,
                    worker_id,
                    concurrency,
                    library,
                    media,
                    IDLE_POLL_INTERVAL_S,
                    chunk_timeout_s,
                    threads,
                    stop,
                )
            except runner.PersistentFailure as error:
                log.error("%s — stopping in error, a fresh worker will take over", error)
                code = 1
            # Requested shutdown, or shutdown on a persistent failure: the same tidying up. What
            # is still running is handed back right away: waiting for the lease to expire would
            # cost two minutes, and the next worker may not have the same identity to recover
            # them at startup.
            try:
                async with pool.connection() as conn:
                    handed_back = await queue.release_own(conn, worker_id)
                    await runner.settle_abandoned(conn, handed_back)
                log.info("worker stopped, %d chunk(s) handed back to the queue", handed_back.requeued)
            except runner.DATABASE_UNAVAILABLE as error:
                # Stopped during a database outage: the in-flight chunks will come back through
                # their lease.
                log.warning(
                    "worker stopped, database unreachable (%s) — in-flight chunks will return through their lease",
                    error,
                )
        finally:
            heartbeat.cancel()
            threads.shutdown()
    return code


async def _beat_forever(alive: Callable[[], None]) -> None:
    while True:
        alive()
        await asyncio.sleep(HEARTBEAT_INTERVAL_S)


if __name__ == "__main__":
    sys.exit(main())
