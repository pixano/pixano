# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests of a job's closing step: a kind's `finalize`, run as the job's final chunk.

The final chunk waits until every other chunk of its job is done, then joins the queue like
any chunk. The job settles only once it ran. Cancellation and retry go through the
application's own statements (`pixano.api.jobs`), since they are the ones that touch a waiting
chunk in production.
"""

import asyncio
from pathlib import Path
from typing import Any

import psycopg
import pytest
from pixano_worker import queue, runner
from pixano_worker.kinds import FakeKind, Registry, TransientError
from pixano_worker.schema import SCHEMA_NAME
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from pixano.api import jobs as app_jobs
from pixano.datasets.utils.errors import DatasetBusyError


# Four chunks of work of ten tasks each, which take no time.
WORK = {"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0}
WORK_CHUNKS = 4

#: Beyond the grace the worker gives its in-flight chunks, how long a stop may take.
STOP_MARGIN_S = 5.0

#: How often, and how many times, a test looks at a job run by the real loop before giving up on it:
#: eight seconds, far beyond the fraction of a second the job takes.
POLL_INTERVAL_S = 0.02
POLLS = 400

#: How long a settlement paused in a test leaves another chunk to finish: far beyond what a finish
#: takes on a local database, so that a finish nothing holds back is over by then.
OTHER_CHUNK_FINISH_S = 1.0


class _Finalizes(FakeKind):
    """The fake kind, with a closing step that records each of its runs.

    `failures` are raised by the next runs, in order: a test arms them to make the closing
    step fail as a real one would.
    """

    name = "finalizes"

    def __init__(self) -> None:
        self.finalized: list[str] = []
        self.failures: list[Exception] = []

    def finalize(self, reader: Any, writer: Any, params: Any) -> None:
        self.finalized.append(writer.job_id)
        if self.failures:
            raise self.failures.pop(0)


@pytest.fixture
def kind() -> _Finalizes:
    return _Finalizes()


@pytest.fixture
def registry(db: psycopg.Connection, kind: _Finalizes) -> Registry:
    """A worker that knows the finalizing kind, and the plain fake kind, which has no closing step."""
    registry = Registry()
    registry.register(kind)
    registry.register(FakeKind())
    registry.declare(db, "worker-test")
    return registry


def _submit(db: psycopg.Connection, kind: str = _Finalizes.name, params: dict | None = None) -> str:
    row = db.execute(
        f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, params) VALUES (%s, 'ds', %s) RETURNING id",
        (kind, Jsonb(params if params is not None else WORK)),
    ).fetchone()
    assert row is not None
    return str(row[0])


def _state(db: psycopg.Connection, job_id: str) -> tuple:
    row = db.execute(
        f"SELECT state, done_tasks, total_tasks FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job_id,)
    ).fetchone()
    assert row is not None
    return row


def _final_chunks(db: psycopg.Connection, job_id: str) -> list[tuple]:
    """The job's final chunks — one at most: rank, state, task count, and what it produced."""
    return db.execute(
        f"SELECT seq, state, task_count, produced FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s AND final",
        (job_id,),
    ).fetchall()


def _final_chunk(db: psycopg.Connection, job_id: str) -> tuple:
    """The job's final chunk: its rank, state, task count, and what it produced."""
    (final,) = _final_chunks(db, job_id)
    return final


def _states(db: psycopg.Connection, job_id: str) -> list[dict]:
    """The job's state events, in the order of their identifiers."""
    rows = db.execute(
        f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'state' ORDER BY id", (job_id,)
    ).fetchall()
    return [row[0] for row in rows]


async def _drain(adb: psycopg.AsyncConnection, registry: Registry, library: Path | None = None) -> None:
    while await runner.run_batch(adb, registry, "worker-test", 8, library=library):
        pass


class TestTheKindSaysWhetherItFinalizes:
    def test_overriding_finalize_is_what_gives_a_closing_step(self, kind: _Finalizes) -> None:
        """A kind that does nothing at the end must not make its jobs wait for an empty step."""
        assert kind.finalizes
        assert not FakeKind().finalizes


class TestPlanning:
    async def test_a_kind_that_finalizes_gets_a_final_chunk_waiting_for_the_others(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Last in rank, without a task, out of the queue: the progress counts the work only."""
        job = _submit(db)

        await runner.plan_one(adb, registry)

        assert _state(db, job) == ("pending", 0, 40)
        assert _final_chunk(db, job) == (WORK_CHUNKS, "waiting", 0, None)

    async def test_a_kind_without_one_gets_none(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(db, kind=FakeKind.name)

        await runner.plan_one(adb, registry)

        assert _final_chunks(db, job) == []


class TestTheFinalChunkRunsLast:
    async def test_it_is_not_claimed_while_work_remains(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry, kind: _Finalizes
    ) -> None:
        job = _submit(db)
        await runner.plan_one(adb, registry)

        await runner.run_batch(adb, registry, "worker-test", WORK_CHUNKS - 1)

        assert _final_chunk(db, job)[1] == "waiting"
        assert kind.finalized == []

    async def test_it_joins_the_queue_once_the_work_is_done_and_the_job_waits_for_it(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry, kind: _Finalizes
    ) -> None:
        """The job is not done when its work is: its closing step has not run yet."""
        job = _submit(db)
        await runner.plan_one(adb, registry)

        await runner.run_batch(adb, registry, "worker-test", WORK_CHUNKS)

        assert _state(db, job) == ("running", 40, 40)
        assert _final_chunk(db, job)[1] == "pending"
        assert kind.finalized == []

        await _drain(adb, registry)

        assert _state(db, job) == ("done", 40, 40)
        assert kind.finalized == [job]

    async def test_the_outcome_is_the_works_not_the_closing_steps(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """The final chunk produced nothing: the job's outcome, the event's and the application's, reads its work."""
        job = _submit(db)
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        assert _final_chunk(db, job) == (WORK_CHUNKS, "done", 0, 0)
        assert _states(db, job)[-1] == {"state": "done", "produced": 40, "skipped": 0, "quarantined": 0}
        seen = app_jobs.get(db, job)
        assert (seen.state, seen.done_tasks, seen.total_tasks, seen.produced) == ("done", 40, 40, 40)

    async def test_the_job_says_when_it_is_finalizing(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Between a full bar and the end, an interface can say what the job is doing."""
        job = _submit(db)
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        assert [event["state"] for event in _states(db, job)] == ["pending", "running", "running", "done"]
        assert _states(db, job)[2] == {"state": "running", "finalizing": True}

    async def test_the_real_loop_runs_it(
        self, db: psycopg.Connection, postgres_url: str, registry: Registry, kind: _Finalizes
    ) -> None:
        """The loop claims the final chunk like any other once it is released, and settles the job after it."""
        job = _submit(db)
        stop = asyncio.Event()
        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=5, kwargs={"autocommit": True}) as pool:
            worker = asyncio.create_task(runner.work(pool, registry, "worker-test", 4, idle_poll_s=0.05, stop=stop))
            try:
                for _ in range(POLLS):
                    if _state(db, job)[0] in ("done", "error", "cancelled"):
                        break
                    await asyncio.sleep(POLL_INTERVAL_S)
            finally:
                stop.set()
                stopped, _ = await asyncio.wait({worker}, timeout=runner.SHUTDOWN_GRACE_S + STOP_MARGIN_S)
                assert stopped, "the worker did not stop when asked"
                await worker

        assert _state(db, job) == ("done", 40, 40)
        assert kind.finalized == [job]


class TestAJobThatEndsBadlyIsNotFinalized:
    async def test_a_failed_chunk_leaves_the_closing_step_waiting(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry, kind: _Finalizes
    ) -> None:
        """An index built over a job that lost a chunk would describe a result that is not there."""
        job = _submit(db, params={**WORK, "fail_at_chunk": 1})
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        assert _state(db, job)[0] == "error"
        assert _final_chunk(db, job)[1] == "waiting"
        assert kind.finalized == []

    async def test_a_retry_finalizes_the_job_once_its_chunks_pass(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry, kind: _Finalizes
    ) -> None:
        """The application's retry reopens the failed chunk; the closing step follows it."""
        job = _submit(db)
        await runner.plan_one(adb, registry)
        process = kind.process
        failing = [RuntimeError("the inference refused the chunk")]

        def process_failing_once(reader, payload, params):
            if failing and payload["first_task"] == 10:
                raise failing.pop()
            return process(reader, payload, params)

        kind.process = process_failing_once  # type: ignore[method-assign]
        await _drain(adb, registry)
        assert _state(db, job)[0] == "error"

        app_jobs.retry(db, job)
        await _drain(adb, registry)

        assert _state(db, job) == ("done", 40, 40)
        assert kind.finalized == [job]

    async def test_a_job_cancelled_while_working_is_not_finalized(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry, kind: _Finalizes
    ) -> None:
        job = _submit(db)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-test", 2)

        app_jobs.cancel(db, job)
        await _drain(adb, registry)

        assert _state(db, job)[0] == "cancelled"
        assert _final_chunk(db, job)[1] == "waiting"
        assert kind.finalized == []

    async def test_a_cancel_while_finalizing_drops_the_step_and_a_retry_runs_it(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry, kind: _Finalizes
    ) -> None:
        """Queued, the final chunk leaves the queue with the job's other pending chunks; a retry puts it back."""
        job = _submit(db)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-test", WORK_CHUNKS)

        app_jobs.cancel(db, job)
        await _drain(adb, registry)

        assert _state(db, job)[0] == "cancelled"
        assert _final_chunk(db, job)[1] == "cancelled"
        assert kind.finalized == []

        app_jobs.retry(db, job)
        await _drain(adb, registry)

        assert _state(db, job) == ("done", 40, 40)
        assert kind.finalized == [job]
        # The retry, then the start on the closing step alone, both say the job is finalizing.
        assert _states(db, job)[-3:-1] == [
            {"state": "pending", "cancel_requested": False, "finalizing": True},
            {"state": "running", "finalizing": True},
        ]


class TestAFailingClosingStep:
    @pytest.mark.parametrize(
        "failure",
        [
            TransientError("the inference is restarting"),
            DatasetBusyError("Dataset is being modified; retry when the current operation finishes."),
        ],
        ids=["transient", "dataset written elsewhere"],
    )
    async def test_a_failure_of_circumstance_hands_it_back_to_the_queue(
        self,
        db: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        registry: Registry,
        kind: _Finalizes,
        failure: Exception,
    ) -> None:
        """Someone saving the dataset says nothing about a job whose chunks are all done: it is not failed for it."""
        job = _submit(db)
        await runner.plan_one(adb, registry)
        kind.failures = [failure]

        await _drain(adb, registry)

        final = db.execute(
            f"SELECT state, error->>'reason', available_at > now() FROM {SCHEMA_NAME}.job_chunks "
            "WHERE job_id = %s AND final",
            (job,),
        ).fetchone()
        assert final == ("pending", "transient failure", True)
        assert _state(db, job)[0] == "running"

        db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET available_at = now() WHERE job_id = %s AND final", (job,))
        await _drain(adb, registry)

        assert _state(db, job) == ("done", 40, 40)
        assert kind.finalized == [job, job]

    async def test_a_definitive_failure_fails_the_job_and_says_why(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry, kind: _Finalizes
    ) -> None:
        job = _submit(db)
        await runner.plan_one(adb, registry)
        kind.failures = [RuntimeError("the index cannot be built")]

        await _drain(adb, registry)

        assert _state(db, job)[0] == "error"
        error = app_jobs.get(db, job).error
        assert error is not None and error["reason"] == "the index cannot be built"


class TestRecovery:
    async def test_a_worker_that_dies_while_finalizing_leaves_it_to_another(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry, kind: _Finalizes
    ) -> None:
        """Its lease expires like any chunk's, and another worker runs the closing step."""
        job = _submit(db)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-test", WORK_CHUNKS)
        claimed = await queue.claim(adb, "worker-dead", 1)
        assert [chunk.final for chunk in claimed] == [True]

        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() - interval '1 minute' WHERE state = 'running'"
        )
        await queue.reclaim_expired(adb)
        await _drain(adb, registry)

        assert _state(db, job) == ("done", 40, 40)
        assert kind.finalized == [job]

    async def test_the_last_two_chunks_finishing_together_still_finalize(
        self,
        db: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        postgres_url: str,
        registry: Registry,
        kind: _Finalizes,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """One chunk's settlement checks the release while the other still runs, then settles.

        Read committed, the other chunk's result could commit between the two: the release check
        saw it running, the settlement saw it done, and the job read `done` without its closing
        step. The settlement now locks the job first, as `finish` does to count a chunk: the other
        chunk's result waits for the settlement, and its own settlement releases the final chunk.
        """
        job = _submit(db, params={**WORK, "task_count": 20})
        await runner.plan_one(adb, registry)
        first, second = await queue.claim(adb, "worker-test", 2)
        await queue.start_jobs(adb, [job])
        await queue.finish(adb, first)
        release_final = queue.release_final
        checked, finished = asyncio.Event(), asyncio.Event()

        async def check_then_let_the_other_finish(conn: psycopg.AsyncConnection, job_id: str) -> bool:
            released = await release_final(conn, job_id)
            checked.set()
            # The other chunk's result commits here, unless something holds it back.
            waiting = asyncio.ensure_future(finished.wait())
            await asyncio.wait({waiting}, timeout=OTHER_CHUNK_FINISH_S)
            waiting.cancel()
            return released

        async def finish_the_other(conn: psycopg.AsyncConnection) -> None:
            await queue.finish(conn, second)
            finished.set()

        monkeypatch.setattr(queue, "release_final", check_then_let_the_other_finish)
        async with await psycopg.AsyncConnection.connect(postgres_url, autocommit=True) as other:
            settling = asyncio.create_task(runner.settle(adb, job))
            await checked.wait()
            monkeypatch.setattr(queue, "release_final", release_final)
            finishing = asyncio.create_task(finish_the_other(other))
            await settling
            await finishing
            await runner.settle(other, job)
        await _drain(adb, registry)

        assert _state(db, job) == ("done", 20, 20)
        assert kind.finalized == [job]

    async def test_two_settlements_at_once_release_it_once(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, postgres_url: str, registry: Registry
    ) -> None:
        """The last two chunks finishing together each settle the job: one release, one announcement."""
        job = _submit(db, params={**WORK, "task_count": 20})
        await runner.plan_one(adb, registry)
        for chunk in await queue.claim(adb, "worker-test", 2):
            await queue.finish(adb, chunk)

        async with await psycopg.AsyncConnection.connect(postgres_url, autocommit=True) as other:
            await asyncio.gather(runner.settle(adb, job), runner.settle(other, job))

        assert _final_chunk(db, job)[1] == "pending"
        assert sum(1 for event in _states(db, job) if event.get("finalizing")) == 1


class TestTheClosingStepSeesTheDataset:
    async def test_it_reads_the_dataset_reopened_outside_the_cache(
        self,
        db: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        registry: Registry,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """What other workers wrote — an embeddings table one of them created — must be seen.

        The chunks of work read nothing here: only the closing step reopens the dataset.
        """
        reopened: list[tuple[Path, str]] = []
        monkeypatch.setattr(
            runner, "_reopen_dataset", lambda library, dataset_id: reopened.append((library, dataset_id))
        )
        job = _submit(db)
        await runner.plan_one(adb, registry)
        reopened.clear()

        await _drain(adb, registry, library=tmp_path)

        assert _state(db, job)[0] == "done"
        assert reopened == [(tmp_path, "ds")]
