# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A long chunk while it runs: the progress it reports, the cancellation it hears, the time its weight gives it.

The demo kind `fake` reports a task done at a time and stops between two of them on a cancellation,
as a kind whose chunk runs for minutes would.
"""

import asyncio
import time
from datetime import timedelta

import psycopg
import pytest
from pixano_worker import queue, runner
from pixano_worker.kinds import Registry, default_registry
from pixano_worker.schema import SCHEMA_NAME
from pixano_worker.threads import WorkerThreads
from psycopg.types.json import Jsonb


#: One chunk of twenty tasks of a twentieth of a second: a second of work, long enough to watch.
SLOW = {"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.05}
#: How often the tests have the keeper record progress and look up a cancellation.
FAST_INTERVAL_S = 0.05


@pytest.fixture
def registry() -> Registry:
    return default_registry(demo_kinds=True)


@pytest.fixture
def declared(db: psycopg.Connection, registry: Registry) -> psycopg.Connection:
    registry.declare(db, "worker-test")
    return db


@pytest.fixture(autouse=True)
def often(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "PROGRESS_INTERVAL_S", FAST_INTERVAL_S)


def _submit(db: psycopg.Connection, params: dict) -> str:
    row = db.execute(
        f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, params) VALUES ('fake', 'ds', %s) RETURNING id",
        (Jsonb(params),),
    ).fetchone()
    assert row is not None
    return str(row[0])


def _progress_events(db: psycopg.Connection, job_id: str) -> list[int]:
    rows = db.execute(
        f"SELECT payload->>'done_tasks' FROM {SCHEMA_NAME}.job_events "
        "WHERE job_id = %s AND type = 'progress' ORDER BY id",
        (job_id,),
    ).fetchall()
    return [int(row[0]) for row in rows]


def _job_progress(db: psycopg.Connection, job_id: str) -> int:
    row = db.execute(queue.JOB_PROGRESS, (job_id,)).fetchone()
    assert row is not None
    return int(row[0])


class TestProgressWithinAChunk:
    async def test_a_running_chunk_counts_in_its_jobs_progress(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, SLOW)
        await runner.plan_one(adb, registry)
        [chunk] = await queue.claim(adb, "worker-test", 1)

        running = asyncio.create_task(runner.run_chunk(adb, registry, chunk))
        await asyncio.sleep(0.5)
        midway = _job_progress(declared, job)
        await running

        assert 0 < midway < 20
        events = _progress_events(declared, job)
        assert events == sorted(events) and events[-1] == 20
        assert len(events) > 2, "the chunk announced its progress before its end"

    async def test_a_chunk_claimed_again_starts_over_and_says_so(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, {**SLOW, "seconds_per_task": 0.0})
        await runner.plan_one(adb, registry)
        # A previous attempt got halfway, then its worker died: its chunk is back in the queue.
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET progress = 10")

        [chunk] = await queue.claim(adb, "worker-test", 1)

        assert chunk.previous_progress == 10
        assert _job_progress(declared, job) == 0
        await runner.run_chunk(adb, registry, chunk)
        assert _progress_events(declared, job)[0] == 0

    async def test_progress_is_not_recorded_for_a_chunk_taken_over(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        _submit(declared, SLOW)
        await runner.plan_one(adb, registry)
        [chunk] = await queue.claim(adb, "worker-test", 1)
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET attempts = attempts + 1")

        assert not await queue.record_progress(adb, chunk, 5)
        row = declared.execute(f"SELECT progress FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row == (0,)


class TestCancellationWithinAChunk:
    async def test_a_running_chunk_stops_between_two_tasks_and_its_job_is_cancelled(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, {**SLOW, "seconds_per_task": 0.1})
        await runner.plan_one(adb, registry)
        [chunk] = await queue.claim(adb, "worker-test", 1)
        started = time.monotonic()

        running = asyncio.create_task(runner.run_chunk(adb, registry, chunk))
        await asyncio.sleep(0.3)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))
        await running

        assert time.monotonic() - started < 1.5, "the chunk stopped well before its two seconds"
        chunk_state = declared.execute(f"SELECT state FROM {SCHEMA_NAME}.job_chunks").fetchone()
        job_state = declared.execute(f"SELECT state, done_tasks FROM {SCHEMA_NAME}.jobs").fetchone()
        assert chunk_state == ("cancelled",)
        assert job_state == ("cancelled", 0)


class TestALeaseTakenOver:
    async def test_a_chunk_another_worker_took_over_stops_and_is_left_to_it(
        self,
        declared: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        # The lease checked every tenth of a second; a second of work.
        monkeypatch.setattr(queue, "LEASE_REFRESH_INTERVAL", timedelta(seconds=FAST_INTERVAL_S * 2))
        _submit(declared, SLOW)
        await runner.plan_one(adb, registry)
        [chunk] = await queue.claim(adb, "worker-test", 1)
        started = time.monotonic()

        running = asyncio.create_task(runner.run_chunk(adb, registry, chunk))
        await asyncio.sleep(0.2)
        # Another worker claimed it meanwhile: its attempt is the chunk's now.
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET attempts = attempts + 1, claimed_by = 'other'")
        await running

        assert time.monotonic() - started < 0.8, "the chunk ran on after its lease went"
        row = declared.execute(f"SELECT state, claimed_by FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row == ("running", "other")


class TestTimeLimitOfTheWork:
    async def test_a_chunk_runs_its_weight_times_the_workers_limit(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        # A second of work, against a limit of a tenth of a second for a chunk of weight one.
        _submit(declared, SLOW)
        await runner.plan_one(adb, registry)
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET weight = 40")
        [chunk] = await queue.claim(adb, "worker-test", 1)

        await runner.run_chunk(adb, registry, chunk, timeout_s=0.1)

        row = declared.execute(f"SELECT state FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row == ("done",)

    async def test_a_chunk_beyond_its_weights_limit_is_handed_back(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        _submit(declared, SLOW)
        await runner.plan_one(adb, registry)
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET weight = 2")
        [chunk] = await queue.claim(adb, "worker-test", 1)

        await runner.run_chunk(adb, registry, chunk, timeout_s=0.1)

        row = declared.execute(
            f"SELECT state, error->>'reason', (error->>'timeout_s')::float FROM {SCHEMA_NAME}.job_chunks"
        ).fetchone()
        assert row == ("pending", "time limit exceeded", 0.2)

    async def test_a_chunk_past_its_limit_stops_its_work_at_the_next_task(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        # A second of work, a tenth of a second allowed: handed back, and its thread told to stop,
        # rather than left to run its chunk to the end beside the attempt that takes it over.
        _submit(declared, SLOW)
        await runner.plan_one(adb, registry)
        [chunk] = await queue.claim(adb, "worker-test", 1)
        threads = WorkerThreads.for_concurrency(1)

        await runner.run_chunk(adb, registry, chunk, timeout_s=0.1, threads=threads)
        await asyncio.sleep(0.3)

        assert threads.stuck == 0, "the thread ran on past its next task"

    async def test_a_planned_chunk_keeps_the_weight_its_kind_gave(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        job = _submit(declared, SLOW)
        chunks = [runner.Chunk(payload={"first_task": 0, "task_count": 20}, task_count=20, weight=3)]

        await runner.record_plan(adb, job, chunks)

        row = declared.execute(f"SELECT weight FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row == (3.0,)
