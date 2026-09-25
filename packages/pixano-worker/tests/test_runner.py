# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests of the execution loop: planning, execution, cancellation, recovery."""

import asyncio
import json
import logging
import threading
from datetime import timedelta
from pathlib import Path

import psycopg
import psycopg_pool
import pytest
from pixano_worker import queue, runner
from pixano_worker.kinds import Chunk, FakeKind, Outcome, Registry, default_registry
from pixano_worker.schema import NOTIFY_CHANNEL, SCHEMA_NAME
from pixano_worker.threads import WorkerThreads
from psycopg_pool import AsyncConnectionPool


FAST = {"task_count": 200, "chunk_size": 20, "seconds_per_task": 0.0}

#: Beyond the grace the worker gives its in-flight chunks, how long a stop may take.
STOP_MARGIN_S = 5.0


@pytest.fixture
def registry() -> Registry:
    """The registry shipped with the worker."""
    return default_registry(demo_kinds=True)


@pytest.fixture
def declared(db: psycopg.Connection, registry: Registry) -> psycopg.Connection:
    """A database where this worker has declared what it can do."""
    registry.declare(db, "worker-test")
    return db


def _submit(db: psycopg.Connection, params: dict | None = None, kind: str = "fake") -> str:
    from psycopg.types.json import Jsonb

    row = db.execute(
        f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, params) VALUES (%s, 'ds', %s) RETURNING id",
        (kind, Jsonb(params if params is not None else FAST)),
    ).fetchone()
    assert row is not None
    return str(row[0])


def _state(db: psycopg.Connection, job_id: str) -> tuple:
    row = db.execute(
        f"SELECT state, done_tasks, total_tasks FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job_id,)
    ).fetchone()
    assert row is not None
    return row


class TestDeclaration:
    def test_publishes_every_kind_with_its_parameter_schema(self, db: psycopg.Connection, registry: Registry) -> None:
        """This is the only bridge between the application and the worker: they share no code."""
        registry.declare(db, "worker-test")

        rows = db.execute(f"SELECT name, params_schema FROM {SCHEMA_NAME}.job_kinds ORDER BY name").fetchall()

        assert [row[0] for row in rows] == registry.names()
        published = dict(rows)
        assert published["fake"]["properties"]["task_count"]["type"] == "integer"

    def test_the_published_schema_refuses_an_unknown_parameter(self, registry: Registry) -> None:
        """This is the property that lets the application catch a typo.

        Without `additionalProperties: false` in the published schema, a misspelled parameter
        passes validation and gets silently ignored at execution.
        """
        kind = registry.get("fake")
        assert kind is not None

        assert kind.params_schema()["additionalProperties"] is False

    def test_an_unknown_parameter_is_refused_at_execution_too(self, registry: Registry) -> None:
        import pydantic

        kind = registry.get("fake")
        assert kind is not None

        with pytest.raises(pydantic.ValidationError):
            kind.validate_params({"task_count": 10, "tsak_size": 4})

    def test_declaring_again_refreshes_rather_than_duplicates(
        self, db: psycopg.Connection, registry: Registry
    ) -> None:
        """A redeployed worker updates its schema with no intervention."""
        registry.declare(db, "worker-a")
        registry.declare(db, "worker-b")

        row = db.execute(
            f"SELECT count(*), count(DISTINCT declared_by), max(declared_by) FROM {SCHEMA_NAME}.job_kinds"
        ).fetchone()
        assert row == (len(registry.names()), 1, "worker-b")


class TestPlanning:
    async def test_splits_a_job_into_chunks(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared)

        await runner.plan_one(adb, registry)

        assert _state(declared, job) == ("pending", 0, 200)
        row = declared.execute(
            f"SELECT count(*), sum(task_count) FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s", (job,)
        ).fetchone()
        assert row == (10, 200)

    async def test_nothing_to_plan_returns_nothing(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        assert await runner.plan_one(adb, registry) is None

    async def test_an_unknown_kind_fails_the_job_instead_of_stranding_it(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Without this, a job whose kind no worker knows would wait with no explanation."""
        job = _submit(declared, kind="fantome")

        await runner.plan_one(adb, registry)

        state, _, _ = _state(declared, job)
        assert state == "error"
        row = declared.execute(f"SELECT error FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job,)).fetchone()
        assert row is not None and row[0]["kind"] == "fantome"

    async def test_invalid_parameters_fail_the_job(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={"task_count": -5})

        await runner.plan_one(adb, registry)

        assert _state(declared, job)[0] == "error"

    async def test_a_cancelled_job_is_never_planned(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Splitting the work of a job that was just stopped makes no sense."""
        job = _submit(declared)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))

        assert await runner.plan_one(adb, registry) is None
        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row is not None and row[0] == 0


class TestPlanningSeesTheDatasetAsItIs:
    """Architecture review, point 5: planning reopens the dataset outside the worker's cache.

    A dataset recreated under the worker — reimported, its embeddings table dropped — was seen
    as at its previous opening until the worker restarted; met while preparing the scenarios
    of lot 11.
    """

    class _ReadsAtPlanning(FakeKind):
        """The fake kind, but whose plan looks at the dataset and remembers what it saw."""

        name = "reads-at-planning"
        seen: list[object] = []

        def plan(self, reader, params):
            self.seen.append(reader.dataset)
            return super().plan(reader, params)

    async def test_the_plan_reads_a_dataset_reopened_outside_the_cache(
        self,
        db: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        kind = self._ReadsAtPlanning()
        registry = Registry()
        registry.register(kind)
        registry.declare(db, "worker-test")
        job = _submit(db, kind=kind.name)

        versions = iter(["as first opened", "as it is now"])
        monkeypatch.setattr(runner.Dataset, "find", lambda _id, _library: next(versions))
        # What the worker held of it before: opened by a previous job, left in the cache.
        stale = runner._open_dataset(tmp_path, "ds")
        assert stale == "as first opened"

        await runner.plan_one(adb, registry, library=tmp_path)

        assert _state(db, job)[0] == "pending"
        assert kind.seen == ["as it is now"]
        assert runner._open_dataset(tmp_path, "ds") == "as it is now", "the cache now holds the reread version"


class TestPreparation:
    """Architecture review, point 4: `prepare` runs once per job, at planning."""

    class _Prepares(FakeKind):
        name = "prepares"
        prepared: list[str] = []

        def prepare(self, writer, params):
            self.prepared.append(writer.job_id)

    @pytest.fixture
    def kind_registry(self, db: psycopg.Connection) -> tuple[Registry, "TestPreparation._Prepares"]:
        kind = self._Prepares()
        kind.prepared = []
        registry = Registry()
        registry.register(kind)
        registry.declare(db, "worker-test")
        return registry, kind

    async def test_prepare_runs_once_at_planning_and_never_with_a_chunk(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, kind_registry
    ) -> None:
        registry, kind = kind_registry
        job = _submit(db, params={"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0}, kind=kind.name)

        await runner.plan_one(adb, registry)
        assert kind.prepared == [job]

        while await runner.run_batch(adb, registry, "worker-test", 8):
            pass

        assert _state(db, job)[0] == "done"
        assert kind.prepared == [job], "no chunk prepares"

    async def test_a_refused_plan_destroys_nothing(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, kind_registry
    ) -> None:
        """Review of step 2, lot 1: `prepare` dropped the vectors, then the plan refused the job.

        A kind whose plan refuses — an unsupported media type, a model not served — or plans
        nothing must never have its `prepare` run.
        """
        registry, kind = kind_registry

        def refusing_plan(reader, params):
            raise ValueError("the job cannot process point_cloud")

        kind.plan = refusing_plan  # type: ignore[method-assign]
        refused = _submit(db, params={"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0}, kind=kind.name)
        await runner.plan_one(adb, registry)

        kind.plan = lambda reader, params: iter(())  # type: ignore[method-assign]
        empty = _submit(db, params={"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0}, kind=kind.name)
        await runner.plan_one(adb, registry)

        assert (_state(db, refused)[0], _state(db, empty)[0]) == ("error", "error")
        assert kind.prepared == []

    async def test_a_retried_job_with_chunks_is_not_prepared_again(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, kind_registry
    ) -> None:
        """A retry puts the chunks back in the queue without going through planning again."""
        registry, kind = kind_registry
        job = _submit(db, params={"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0}, kind=kind.name)
        await runner.plan_one(adb, registry)
        # What POST /jobs/{id}/retry does on a job that already has its chunks.
        db.execute(f"UPDATE {SCHEMA_NAME}.jobs SET state = 'pending' WHERE id = %s", (job,))

        await runner.plan_one(adb, registry)
        while await runner.run_batch(adb, registry, "worker-test", 8):
            pass

        assert _state(db, job)[0] == "done"
        assert kind.prepared == [job]


class TestInterruptedPlanning:
    """A worker that dies in the middle of a split must not leave the job stuck forever."""

    @staticmethod
    def _claim_planning_and_die(declared: psycopg.Connection) -> None:
        """What a worker leaves behind if it dies right after claiming the split."""
        declared.execute(runner.CLAIM_PLANNING, (queue.LEASE_TTL,))

    async def test_the_job_stays_in_planning_while_it_is_split(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """It used to move to "running" before it even had a chunk — a state no recovery saw."""
        job = _submit(declared)

        self._claim_planning_and_die(declared)

        assert _state(declared, job)[0] == "planning"

    async def test_a_live_planning_lease_is_respected(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        _submit(declared)
        self._claim_planning_and_die(declared)

        assert await runner.plan_one(adb, registry) is None

    async def test_a_job_whose_planner_died_is_planned_again(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared)
        self._claim_planning_and_die(declared)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET planning_until = now() - interval '1 minute'")

        await runner.plan_one(adb, registry)

        assert _state(declared, job) == ("pending", 0, 200)

    async def test_a_second_planner_does_not_double_the_chunks(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """The first planner, too slow, finishes after the one that took over its lease."""
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        late_chunks = [Chunk(payload={"first_task": 0, "task_count": 200}, task_count=200)]

        recorded = await runner.record_plan(adb, job, late_chunks)

        assert recorded is False
        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s", (job,)).fetchone()
        assert row == (10,)


class TestCancelledDuringPlanning:
    """Step 1 review: a cancellation during the split resurrected the job as `pending`."""

    @staticmethod
    def _cancel_as_the_application_does(declared: psycopg.Connection, job: str) -> None:
        declared.execute(
            f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now(), state = 'cancelled', "
            "planning_until = NULL WHERE id = %s",
            (job,),
        )

    async def test_a_plan_finished_after_a_cancel_is_dropped(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        job = _submit(declared)
        declared.execute(runner.CLAIM_PLANNING, (queue.LEASE_TTL,))
        self._cancel_as_the_application_does(declared, job)

        recorded = await runner.record_plan(adb, job, [Chunk(payload={"first_task": 0}, task_count=200)])

        assert recorded is False
        assert _state(declared, job)[0] == "cancelled"
        chunks = declared.execute(
            f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s", (job,)
        ).fetchone()
        assert chunks == (0,)
        states = declared.execute(
            f"SELECT payload->>'state' FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'state'", (job,)
        ).fetchall()
        assert ("pending",) not in states, "no event must announce the job as pending again"

    async def test_a_planning_failure_after_a_cancel_does_not_turn_it_into_an_error(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """A job that was stopped is not a job that failed."""
        job = _submit(declared)
        declared.execute(runner.CLAIM_PLANNING, (queue.LEASE_TTL,))
        self._cancel_as_the_application_does(declared, job)

        await runner._fail_job(adb, job, {"reason": "planning failed"})

        assert _state(declared, job)[0] == "cancelled"


class TestExecution:
    async def test_runs_a_job_to_completion(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """The first half of the lot's DoD: a fake job of 200 tasks runs to the end."""
        job = _submit(declared)
        await runner.plan_one(adb, registry)

        while await runner.run_batch(adb, registry, "worker-test", 8):
            pass

        assert _state(declared, job) == ("done", 200, 200)

    async def test_reports_progress_as_it_goes(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared)
        await runner.plan_one(adb, registry)

        await runner.run_batch(adb, registry, "worker-test", 3)

        assert _state(declared, job)[1] == 60
        events = declared.execute(
            f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'progress' ORDER BY id",
            (job,),
        ).fetchall()
        assert [event[0]["done_tasks"] for event in events] == [20, 40, 60]

    async def test_the_job_announces_once_that_it_is_running(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Without this event, the interface shows "pending" under a bar that moves forward.

        Seen in the browser at lot 11: the job did move to running in the database, without
        anything telling the stream.
        """
        job = _submit(declared)
        await runner.plan_one(adb, registry)

        while await runner.run_batch(adb, registry, "worker-test", 8):
            pass

        states = declared.execute(
            f"SELECT payload->>'state' FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'state' ORDER BY id",
            (job,),
        ).fetchall()
        assert [row[0] for row in states] == ["pending", "running", "done"]

    async def test_progress_events_carry_absolute_counters(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Sequence identifiers are assigned before the commit: a reader can skip one, and must
        be able to rely on the next. Increments would forbid it."""
        _submit(declared)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-test", 2)

        events = declared.execute(
            f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE type = 'progress' ORDER BY id"
        ).fetchall()
        assert all("total_tasks" in event[0] for event in events)
        assert [event[0]["done_tasks"] for event in events] == [20, 40]

    async def test_a_failing_chunk_fails_the_job(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={**FAST, "fail_at_chunk": 3})
        await runner.plan_one(adb, registry)

        while await runner.run_batch(adb, registry, "worker-test", 4):
            pass

        assert _state(declared, job)[0] == "error"

    async def test_the_other_chunks_still_run(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """A job does not stop at the first corrupted item: it finishes and reports."""
        _submit(declared, params={**FAST, "fail_at_chunk": 3})
        await runner.plan_one(adb, registry)

        while await runner.run_batch(adb, registry, "worker-test", 4):
            pass

        row = declared.execute(
            f"SELECT count(*) FILTER (WHERE state = 'done'), count(*) FILTER (WHERE state = 'error') "
            f"FROM {SCHEMA_NAME}.job_chunks"
        ).fetchone()
        assert row == (9, 1)


class TestCancellation:
    async def test_stops_between_batches(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """The second part of the DoD: a cancellation along the way stops cleanly.

        The worker sees the cancellation before the next chunk: it takes it out of the queue
        rather than running it, then settles the job.
        """
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-test", 3)

        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))
        while await runner.run_batch(adb, registry, "worker-test", 3):
            pass

        state, done, total = _state(declared, job)
        assert state == "cancelled"
        assert done == 60, "the work already done stays counted"
        assert total == 200

    async def test_a_cancelled_chunk_never_comes_back(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Handing it back as "pending" would have it reclaimed endlessly, and the job would never settle."""
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))

        tours = 0
        while await runner.run_batch(adb, registry, "worker-test", 4) and tours < 20:
            tours += 1

        assert tours < 20, "the loop does not terminate"
        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'pending'").fetchone()
        assert row is not None and row[0] == 0

    async def test_work_already_done_is_not_undone(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-test", 2)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'cancelled' WHERE state = 'pending'")

        while await runner.run_batch(adb, registry, "worker-test", 3):
            pass

        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'done'").fetchone()
        assert row is not None and row[0] == 2


class TestRecovery:
    async def test_an_interrupted_job_resumes_where_it_stopped(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """The third part of the DoD, simulated: a worker dies, another takes over.

        What a `kill -9` leaves behind is running chunks with a lease. The worker that restarts
        hands its own back; those of a worker that does not come back expire.
        """
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-dead", 2)
        await queue.claim(adb, "worker-dead", 3)

        recovery = await queue.release_own(adb, "worker-dead")
        assert recovery.requeued == 3
        while await runner.run_batch(adb, registry, "worker-alive", 8):
            pass

        assert _state(declared, job) == ("done", 200, 200)

    async def test_no_task_is_counted_twice_after_a_resume(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Resuming must not inflate the progress beyond the total."""
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-dead", 4)
        await queue.claim(adb, "worker-dead", 2)
        await queue.release_own(adb, "worker-dead")

        while await runner.run_batch(adb, registry, "worker-alive", 8):
            pass

        state, done, total = _state(declared, job)
        assert (state, done) == ("done", total)


class TestAbandonedChunk:
    """Step 1 review: a chunk set aside by the recovery did not settle its job."""

    async def test_a_job_whose_last_chunk_is_set_aside_ends_in_error(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.0})
        await runner.plan_one(adb, registry)
        for _ in range(queue.MAX_ATTEMPTS):
            await queue.claim(adb, "worker-dying", 1)
            declared.execute(
                f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() - interval '1 minute' "
                "WHERE state = 'running'"
            )
            recovery = await queue.reclaim_expired(adb)

        await runner.settle_abandoned(adb, recovery)

        assert _state(declared, job)[0] == "error"


class TestNotification:
    """The doorbell that wakes the interface."""

    async def test_an_event_rings_only_once_committed(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, postgres_url: str
    ) -> None:
        """PostgreSQL only delivers a NOTIFY at commit.

        This is what guarantees that a woken reader always finds the row in the database —
        without this property an application-level acknowledgement would be needed.
        """
        job = _submit(declared)

        with psycopg.connect(postgres_url, autocommit=True) as listener:
            listener.execute(f"LISTEN {NOTIFY_CHANNEL}")

            async with await psycopg.AsyncConnection.connect(postgres_url) as writer:
                await queue.record_event(writer, job, "state", {"state": "planning"})
                assert list(listener.notifies(timeout=0.3)) == [], "nothing must ring before the commit"
                await writer.commit()

            received = list(listener.notifies(timeout=3, stop_after=1))

        assert len(received) == 1
        payload = json.loads(received[0].payload)
        assert payload["job_id"] == job
        assert payload["type"] == "state"
        assert isinstance(payload["event_id"], int)

    async def test_the_payload_carries_identifiers_only(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, postgres_url: str
    ) -> None:
        """A NOTIFY payload is capped at 8 kB: putting the content in it would be a trap that
        would spring the day an error message gets a little long."""
        job = _submit(declared)

        with psycopg.connect(postgres_url, autocommit=True) as listener:
            listener.execute(f"LISTEN {NOTIFY_CHANNEL}")
            async with await psycopg.AsyncConnection.connect(postgres_url, autocommit=True) as writer:
                await queue.record_event(writer, job, "progress", {"done_tasks": 40, "total_tasks": 200})
            received = list(listener.notifies(timeout=3, stop_after=1))

        assert set(json.loads(received[0].payload)) == {"job_id", "event_id", "type"}


class TestConcurrency:
    """Several chunks in flight, without ever holding more than allowed."""

    @staticmethod
    async def _run_until_settled(
        pool, registry: Registry, declared: psycopg.Connection, job: str, concurrency: int, threads=None
    ):
        """Run the real loop until the job settles, recording the occupancy.

        The worker is stopped as the real one is — its stop event, which SIGTERM sets — and not
        by cancelling it. On Python 3.11, psycopg_pool waits for a free connection through
        `asyncio.wait_for`, which can swallow a cancellation that arrives as the connection is
        handed over (CPython bpo-42130, fixed in 3.12): the loop then never ended, and the suite
        hung in CI until GitHub killed the job. The wait is bounded, so that a worker that does
        not stop fails the test instead.
        """
        stop = asyncio.Event()
        worker = asyncio.create_task(
            runner.work(pool, registry, "worker-test", concurrency, idle_poll_s=0.05, threads=threads, stop=stop)
        )
        peak = 0
        try:
            for _ in range(400):
                running = declared.execute(
                    f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'running'"
                ).fetchone()
                peak = max(peak, running[0] if running else 0)
                if _state(declared, job)[0] in ("done", "error", "cancelled"):
                    break
                await asyncio.sleep(0.02)
        finally:
            stop.set()
            stopped, _ = await asyncio.wait({worker}, timeout=runner.SHUTDOWN_GRACE_S + STOP_MARGIN_S)
            assert stopped, "the worker did not stop when asked"
            await worker
        return peak

    async def test_runs_several_chunks_at_once(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        """The ceiling is reached, and never exceeded.

        Each chunk sleeps a tenth of a second: enough for the probe to see the chunks overlap,
        if the loop really overlaps them.
        """
        job = _submit(declared, params={"task_count": 200, "chunk_size": 20, "seconds_per_task": 0.005})

        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=5, kwargs={"autocommit": True}) as pool:
            peak = await self._run_until_settled(pool, registry, declared, job, concurrency=4)

        assert _state(declared, job) == ("done", 200, 200)
        assert 2 <= peak <= 4, f"peak occupancy observed: {peak}"

    async def test_a_single_slot_runs_one_chunk_at_a_time(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        job = _submit(declared, params={"task_count": 100, "chunk_size": 20, "seconds_per_task": 0.005})

        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=2, kwargs={"autocommit": True}) as pool:
            peak = await self._run_until_settled(pool, registry, declared, job, concurrency=1)

        assert _state(declared, job) == ("done", 100, 100)
        assert peak == 1

    async def test_no_task_is_counted_twice_under_concurrency(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        """The progress of concurrent chunks adds up without stepping on each other."""
        job = _submit(declared, params={"task_count": 500, "chunk_size": 10, "seconds_per_task": 0.0})

        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=9, kwargs={"autocommit": True}) as pool:
            await self._run_until_settled(pool, registry, declared, job, concurrency=8)

        assert _state(declared, job) == ("done", 500, 500)
        events = declared.execute(
            f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'progress'", (job,)
        ).fetchall()
        assert len(events) == 50
        assert max(event[0]["done_tasks"] for event in events) == 500
        # The states, read in identifier order, are in logical order even when eight chunks
        # finish together: `running` is written under the job's lock, before any `done`.
        states = declared.execute(
            f"SELECT payload->>'state' FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'state' ORDER BY id",
            (job,),
        ).fetchall()
        assert [row[0] for row in states] == ["pending", "running", "done"]


async def _drain(adb: psycopg.AsyncConnection, registry: Registry) -> None:
    while await runner.run_batch(adb, registry, "worker-test", 8):
        pass


class TestTransientFailures:
    """A transient failure is not a failure of the job."""

    async def test_the_chunk_is_retried_later_instead_of_failing_the_job(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={**FAST, "transient_at_chunk": 3})
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        assert _state(declared, job)[0] == "running", "the job waits for its replayed chunk, it has not failed"
        row = declared.execute(
            f"SELECT state, attempts, error->>'reason' FROM {SCHEMA_NAME}.job_chunks WHERE seq = 3"
        ).fetchone()
        assert row == ("pending", 1, "transient failure")

    async def test_the_job_completes_once_the_failure_has_passed(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={**FAST, "transient_at_chunk": 3})
        await runner.plan_one(adb, registry)
        await _drain(adb, registry)

        # The failure has passed: the same job, without the failure, and the delay elapsed.
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET params = params - 'transient_at_chunk' WHERE id = %s", (job,))
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET available_at = now()")
        await _drain(adb, registry)

        assert _state(declared, job) == ("done", 200, 200)

    async def test_a_failure_that_never_passes_ends_in_error(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={**FAST, "transient_at_chunk": 3})
        await runner.plan_one(adb, registry)

        for _ in range(queue.MAX_ATTEMPTS):
            await _drain(adb, registry)
            declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET available_at = now()")

        assert _state(declared, job)[0] == "error"
        row = declared.execute(f"SELECT state, attempts FROM {SCHEMA_NAME}.job_chunks WHERE seq = 3").fetchone()
        assert row == ("error", queue.MAX_ATTEMPTS)


class TestOutcome:
    """A job says what it produced, not only what it attempted."""

    async def test_the_final_event_carries_the_outcome(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={**FAST, "skip_per_chunk": 3, "quarantine_per_chunk": 1})
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        assert _state(declared, job) == ("done", 200, 200)
        final = declared.execute(
            f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'state' "
            "ORDER BY id DESC LIMIT 1",
            (job,),
        ).fetchone()
        assert final is not None
        assert final[0] == {"state": "done", "produced": 160, "skipped": 30, "quarantined": 10}

    async def test_quarantined_items_can_be_read_back(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """A quarantine that cannot be read back is useless."""
        job = _submit(declared, params={**FAST, "quarantine_per_chunk": 1})
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        items = declared.execute(
            f"SELECT item_id, reason FROM {SCHEMA_NAME}.job_items WHERE job_id = %s ORDER BY item_id", (job,)
        ).fetchall()
        assert len(items) == 10
        assert items[0] == ("task-0", "failure requested")

    async def test_an_outcome_that_does_not_add_up_fails_the_chunk(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """A wrong outcome would distort everything displayed about the job: it is a fault of the kind."""

        class Miscounting(FakeKind):
            def outcome(self, result, payload, task_count):  # noqa: ANN001, ANN202, D102
                return Outcome(produced=task_count - 1)

        registry = Registry()
        registry.register(Miscounting())
        job = _submit(declared)
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        assert _state(declared, job)[0] == "error"
        row = declared.execute(f"SELECT error->>'reason' FROM {SCHEMA_NAME}.job_chunks LIMIT 1").fetchone()
        assert row is not None and "outcome" in row[0]


class TestChunkTimeLimit:
    async def test_a_chunk_over_its_time_limit_is_sent_back(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """The worker is alive, docker's probe sees nothing: only this ceiling hands the chunk back."""
        job = _submit(declared, params={"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.05})
        await runner.plan_one(adb, registry)
        chunk = (await queue.claim(adb, "worker-test", 1))[0]

        await runner.run_chunk(adb, registry, chunk, timeout_s=0.1)

        row = declared.execute(f"SELECT state, error->>'reason' FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row == ("pending", "time limit exceeded")
        assert _state(declared, job)[0] == "pending"


class TestLeaseKeptWhileRunning:
    async def test_a_long_chunk_keeps_its_lease(
        self,
        declared: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Without refreshing, a chunk longer than its lease would be taken over in mid-flight."""
        monkeypatch.setattr(queue, "LEASE_REFRESH_INTERVAL", timedelta(milliseconds=50))
        _submit(declared, params={"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.02})
        await runner.plan_one(adb, registry)
        chunk = (await queue.claim(adb, "worker-test", 1))[0]
        # A lease about to expire, which would run out well before the end of the chunk if it
        # were not extended.
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() + interval '200 milliseconds'")

        running = asyncio.create_task(runner.run_chunk(adb, registry, chunk))
        await asyncio.sleep(0.25)
        lease = declared.execute(
            f"SELECT extract(epoch FROM lease_until - now()) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'running'"
        ).fetchone()
        await running

        assert lease is not None and float(lease[0]) > 60, "the lease was extended during execution"
        row = declared.execute(f"SELECT state FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row == ("done",)


class TestLeaseRefreshOutage:
    """Second review: a failed lease refresh classed a successful chunk as fatal."""

    async def test_a_chunk_whose_work_succeeded_is_done_despite_a_failed_refresh(
        self,
        declared: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(queue, "LEASE_REFRESH_INTERVAL", timedelta(milliseconds=30))
        job = _submit(declared, params={"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.01})
        await runner.plan_one(adb, registry)
        chunk = (await queue.claim(adb, "worker-test", 1))[0]
        real_refresh = queue.refresh_lease
        outages = {"left": 2}

        async def flaky_refresh(conn: psycopg.AsyncConnection, c: queue.Chunk) -> bool:
            if outages["left"] > 0:
                outages["left"] -= 1
                raise psycopg.OperationalError("terminating connection due to administrator command")
            return await real_refresh(conn, c)

        monkeypatch.setattr(queue, "refresh_lease", flaky_refresh)

        await runner.run_chunk(adb, registry, chunk)

        assert outages["left"] == 0, "the simulated outages did take place"
        assert _state(declared, job) == ("done", 20, 20)


class TestChunkFacingAnOutage:
    async def test_an_unreachable_database_is_a_warning_not_a_traceback(
        self, registry: Registry, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Seen on the stack: every chunk in flight during an outage wrote a full traceback."""

        class _DeadPool:
            def connection(self):  # noqa: ANN202
                raise psycopg_pool.PoolTimeout("couldn't get a connection after 5.00 sec")

        chunk = queue.Chunk(id=1, job_id="j", seq=0, payload={}, task_count=1, attempts=1)
        with caplog.at_level(logging.WARNING, logger="pixano-worker"):
            await runner._run_pooled(_DeadPool(), registry, chunk, None, None, None, WorkerThreads.for_concurrency(1))

        [record] = caplog.records
        assert record.levelno == logging.WARNING
        assert record.exc_info is None


class TestPlanningRefusedByTheSchema:
    """Independent review, D1: a chunk with no task killed the worker and left the job under lease."""

    async def test_a_kind_planning_an_empty_chunk_fails_its_job_not_the_worker(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        class EmptyChunks(FakeKind):
            def plan(self, reader, params):  # noqa: ANN001, ANN202, D102
                yield Chunk(payload={"first_task": 0, "task_count": 0}, task_count=0)

        registry = Registry()
        registry.register(EmptyChunks())
        job = _submit(declared)

        await runner.plan_one(adb, registry)

        state, _, _ = _state(declared, job)
        assert state == "error"
        row = declared.execute(
            f"SELECT error->>'reason', planning_until FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job,)
        ).fetchone()
        assert row is not None and "refused" in row[0] and row[1] is None

    async def test_an_unexpected_error_in_the_loop_does_not_kill_the_worker(
        self,
        declared: psycopg.Connection,
        postgres_url: str,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        job = _submit(declared, params={"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0})
        real_plan_one = runner.plan_one
        failures = {"left": 2}

        async def buggy_plan_one(*args: object, **kwargs: object) -> str | None:
            if failures["left"] > 0:
                failures["left"] -= 1
                raise RuntimeError("a bug nobody had foreseen")
            return await real_plan_one(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(runner, "plan_one", buggy_plan_one)
        monkeypatch.setattr(runner, "OUTAGE_BACKOFF_S", (0.01,))

        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=3, kwargs={"autocommit": True}) as pool:
            await TestConcurrency._run_until_settled(pool, registry, declared, job, concurrency=2)

        assert failures["left"] == 0
        assert _state(declared, job) == ("done", 40, 40)

    async def test_a_failure_that_never_passes_stops_the_worker_in_error(
        self,
        declared: psycopg.Connection,
        postgres_url: str,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Architecture review, point 7: surviving a fault, yes; looping on it endlessly, no.

        Past the limit, the loop stops by itself and says so through an exception, so that the
        process exits in error and the restart policy launches a fresh one.
        """
        _submit(declared, params={"task_count": 10, "chunk_size": 10, "seconds_per_task": 0.0})
        turns = {"count": 0}

        async def always_buggy_plan_one(*args: object, **kwargs: object) -> str | None:
            turns["count"] += 1
            raise RuntimeError("a bug that does not pass")

        monkeypatch.setattr(runner, "plan_one", always_buggy_plan_one)
        monkeypatch.setattr(runner, "UNEXPECTED_ERROR_PAUSE_S", 0.001)
        monkeypatch.setattr(runner, "UNEXPECTED_ERROR_LIMIT", 5)

        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=3, kwargs={"autocommit": True}) as pool:
            with pytest.raises(runner.PersistentFailure):
                await asyncio.wait_for(
                    runner.work(pool, registry, "worker-test", concurrency=2, idle_poll_s=0.01), timeout=5
                )

        assert turns["count"] == 5


class TestSaturation:
    """Step 1 review: stuck threads immobilised the worker, still "healthy".

    Second review: renew the pool in place rather than exit the process — the automatic restart
    is bounded, and a worker that relied on it ended up stopped for good.
    """

    async def test_a_saturated_pool_is_renewed_and_the_worker_goes_on(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        threads = WorkerThreads(workers=2, stuck_limit=1)
        release = threading.Event()
        with pytest.raises(TimeoutError):
            await threads.run(release.wait, timeout_s=0.01)
        assert threads.saturated
        job = _submit(declared, params={"task_count": 20, "chunk_size": 10, "seconds_per_task": 0.0})

        try:
            async with AsyncConnectionPool(postgres_url, min_size=1, max_size=2, kwargs={"autocommit": True}) as pool:
                await TestConcurrency._run_until_settled(pool, registry, declared, job, concurrency=1, threads=threads)
        finally:
            release.set()

        assert _state(declared, job) == ("done", 20, 20), "the worker kept working after the renewal"
        assert not threads.saturated


class TestDatabaseOutage:
    """Seen on the real stack: a `docker compose restart postgres` killed the worker for good."""

    async def test_the_loop_waits_for_the_database_instead_of_dying(
        self,
        declared: psycopg.Connection,
        postgres_url: str,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        job = _submit(declared, params={"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0})
        real_plan_one = runner.plan_one
        outages = {"left": 3}

        async def flaky_plan_one(*args: object, **kwargs: object) -> str | None:
            if outages["left"] > 0:
                outages["left"] -= 1
                raise psycopg.errors.AdminShutdown("terminating connection due to administrator command")
            return await real_plan_one(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(runner, "plan_one", flaky_plan_one)
        monkeypatch.setattr(runner, "OUTAGE_BACKOFF_S", (0.01,))

        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=3, kwargs={"autocommit": True}) as pool:
            await TestConcurrency._run_until_settled(pool, registry, declared, job, concurrency=2)

        assert outages["left"] == 0, "the simulated outages did take place"
        assert _state(declared, job) == ("done", 40, 40)


class TestGracefulShutdown:
    """Step 1 review: `docker compose stop` cut the running chunks without handing them back."""

    async def test_an_idle_worker_stops_at_once(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        """No waiting for the current pause: docker must not wait for nothing."""
        stop = asyncio.Event()
        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=2, kwargs={"autocommit": True}) as pool:
            worker = asyncio.create_task(runner.work(pool, registry, "worker-test", 1, idle_poll_s=60, stop=stop))
            await asyncio.sleep(0.2)

            stop.set()

            await asyncio.wait_for(worker, timeout=2)

    async def test_chunks_in_flight_finish_and_nothing_new_is_claimed(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        job = _submit(declared, params={"task_count": 200, "chunk_size": 20, "seconds_per_task": 0.01})
        stop = asyncio.Event()
        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=3, kwargs={"autocommit": True}) as pool:
            worker = asyncio.create_task(runner.work(pool, registry, "worker-test", 2, idle_poll_s=0.05, stop=stop))
            for _ in range(200):
                if _state(declared, job)[1] >= 40:
                    break
                await asyncio.sleep(0.02)

            stop.set()
            await asyncio.wait_for(worker, timeout=5)

        states = dict(
            declared.execute(f"SELECT state, count(*) FROM {SCHEMA_NAME}.job_chunks GROUP BY state").fetchall()
        )
        assert "running" not in states, "the in-flight chunks finished before the stop"
        assert states.get("pending", 0) > 0, "nothing new was claimed after the stop request"

    async def test_chunks_that_outlast_the_grace_are_left_to_be_handed_back(
        self,
        declared: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        postgres_url: str,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(runner, "SHUTDOWN_GRACE_S", 0.05)
        _submit(declared, params={"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.1})
        stop = asyncio.Event()
        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=2, kwargs={"autocommit": True}) as pool:
            worker = asyncio.create_task(runner.work(pool, registry, "worker-test", 1, idle_poll_s=0.05, stop=stop))
            for _ in range(100):
                running = declared.execute(
                    f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'running'"
                ).fetchone()
                if running and running[0]:
                    break
                await asyncio.sleep(0.02)

            stop.set()
            await asyncio.wait_for(worker, timeout=2)

        recovery = await queue.release_own(adb, "worker-test")

        assert recovery.requeued == 1
