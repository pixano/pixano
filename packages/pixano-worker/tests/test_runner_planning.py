# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Bounds on a planning and on a chunk's wait for its dataset, without PostgreSQL.

The dataset is a real one, and the planning is `runner.plan_one` itself, with the runner's writer;
only PostgreSQL's part is scripted: one job waiting to be planned, and what the planning tells the
queue about it.

Two bounds are tested here, which are not the same wait. The planning has a time limit of its
own; it never takes the dataset's write lock. A chunk's write waits a bounded time for this
worker's write lock of its dataset, which a write that never returns holds for good; that test
goes through `runner._execute`, with PostgreSQL's part scripted the same way.
"""

import asyncio
import threading
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractContextManager, asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any

import pytest
from pixano_worker import queue, runner
from pixano_worker.kinds import FakeKind, Registry
from pixano_worker.kinds.fake import FakeParams
from pixano_worker.reader import JobReader
from pixano_worker.schema import SCHEMA_NAME
from pixano_worker.threads import WorkerThreads

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import BBox, Entity, Image, Record


#: Another chunk writing a dataset for the length of a block: the `writing` fixture (conftest.py).
Writing = Callable[..., AbstractContextManager[threading.Event]]

JOB_ID = "job-1"
DATASET_ID = "boxes-only"
# One chunk of one task, done at once: the job's work is not what these tests look at.
ONE_TASK = {"task_count": 1, "chunk_size": 1, "seconds_per_task": 0.0}
# Stand in for the runner's wait for this worker's write lock of a dataset (five minutes, for a
# chunk) and for its limit on a planning (ten minutes): long enough for a thread to reach the
# lock, short enough that a test reaching them stays quick.
SHORT_WAIT_S = 0.2
# A chunk's own time limit, standing for the half hour: far beyond `SHORT_WAIT_S`, so that a chunk
# that reaches it waited for the lock with no bound of its own.
CHUNK_TIME_LIMIT_S = 2.0
# How long a test waits for a planning or a chunk before calling it hung: beyond every wait the
# runner is given here, and below the other writer's own hold (`LOCK_HANDOVER_TIMEOUT_S`, ten
# seconds), so that only a wait with no bound reaches it.
HUNG_AFTER_S = 5.0
# How long storage that stopped answering stays silent before it answers again, at the latest:
# beyond `HUNG_AFTER_S`, so that a planning waiting for it with no bound is seen hung first.
SILENT_STORAGE_S = 10.0
# The statement `runner._execute` reads a chunk's job with, built as it builds it.
SELECT_CHUNKS_JOB = f"SELECT kind, params, dataset FROM {SCHEMA_NAME}.jobs WHERE id = %s"


class _Answer:
    """What `execute` returns: the cursor the runner reads a row or a row count from."""

    def __init__(self, row: tuple[Any, ...] | None = None, rowcount: int = 0) -> None:
        self.row, self.rowcount = row, rowcount

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.row


class _JobsTable:
    """PostgreSQL's part of planning, for one job: each statement the runner sends, answered as
    PostgreSQL answers it for that job.

    Statements are told apart by identity — the runner's own constants —, and one this table does
    not know fails the test: a statement the planning adds is not silently misread.

    Attributes:
        state: The job's state.
        lease: For how long the last claim or refresh reserved the job; None once it can be
            claimed again.
        errors: What each failure of the job said, in order.
    """

    def __init__(self, kind: str, params: dict[str, Any]) -> None:
        self.job = (JOB_ID, kind, DATASET_ID, params)
        self.state = "planning"
        self.lease: timedelta | None = None
        self.errors: list[dict[str, Any]] = []

    async def execute(self, query: str, params: Any = None) -> _Answer:
        if query is runner.CLAIM_PLANNING:
            if self.state != "planning" or self.lease is not None:
                return _Answer()
            self.lease = params[0]
            return _Answer(self.job)
        if query is runner.REFRESH_PLANNING:
            self.lease = params[0]
            return _Answer(rowcount=1)
        if query is runner.FINISH_PLANNING:
            self.state, self.lease = "pending", None
            return _Answer((self.job[0],))
        if query is runner.FAIL_JOB:
            self.state, self.lease = "error", None
            self.errors.append(params[0].obj)
            return _Answer((self.job[0],))
        assert query is runner.INSERT_CHUNKS or query is queue.RECORD_EVENT, f"unexpected statement: {query}"
        return _Answer()

    @asynccontextmanager
    async def transaction(self) -> AsyncIterator[None]:
        yield


class _ChunksJob:
    """PostgreSQL's part of running one chunk of a job that is not cancelled: its job read, and
    the chunk handed back to the queue — the only ways these tests let a chunk end.

    Attributes:
        retried: Why the chunk was handed back, each time it was.
    """

    def __init__(self, kind: str, params: dict[str, Any]) -> None:
        self.job = (kind, params, DATASET_ID)
        self.retried: list[dict[str, Any]] = []

    async def execute(self, query: str, params: Any = None) -> _Answer:
        if query is queue.IS_CANCELLED:
            return _Answer((False,))
        if query == SELECT_CHUNKS_JOB:
            return _Answer(self.job)
        assert query is queue.RETRY, f"unexpected statement: {query}"
        self.retried.append(params["error"].obj)
        return _Answer(("pending",))


class _SplitsOnSilentStorage(FakeKind):
    """A kind whose split reads a dataset on storage that stopped answering, until it answers.

    Attributes:
        storage_answers: Set when the storage answers again.
    """

    name = "silent-storage"

    def __init__(self) -> None:
        super().__init__()
        self.storage_answers = threading.Event()

    def plan(self, reader: JobReader, params: FakeParams) -> list[Any]:
        self.storage_answers.wait(SILENT_STORAGE_S)
        return list(super().plan(reader, params))


class _SplitTimesOut(FakeKind):
    """A kind whose split meets a timeout of its own: a socket to the storage, say."""

    name = "socket-timeout"

    def plan(self, reader: JobReader, params: FakeParams) -> list[Any]:
        raise TimeoutError("the storage did not answer the socket in time")


def _boxes_dataset(library: Path, dataset_id: str) -> None:
    """A dataset of boxes, as Demo shapes is imported."""
    Dataset.create(
        library / dataset_id,
        DatasetInfo(id=dataset_id, name="Boxes only", record=Record, entity=Entity, bbox=BBox, views={"image": Image}),
    )


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A library holding a dataset of boxes, as Demo shapes is imported."""
    # The runner keeps the datasets it opened in a module-level cache: empty, the tests stay
    # independent of each other.
    monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
    library = tmp_path / "library"
    _boxes_dataset(library, DATASET_ID)
    return library


@pytest.fixture
def threads() -> WorkerThreads:
    """A pool of the test's own: a thread a test leaves behind counts in it, and nowhere else."""
    return WorkerThreads(workers=2, stuck_limit=1)


def _planning(kind: FakeKind) -> tuple[Registry, _JobsTable]:
    """A worker that knows this kind, and one job of it waiting to be planned."""
    registry = Registry()
    registry.register(kind)
    return registry, _JobsTable(kind.name, ONE_TASK)


async def test_a_planning_that_never_ends_fails_its_job(
    library: Path, monkeypatch: pytest.MonkeyPatch, threads: WorkerThreads
) -> None:
    """A planning stuck in its reads held the loop's turn with no
    bound. The loop now stops waiting after a limit and fails the job."""
    monkeypatch.setattr(runner, "PLANNING_TIMEOUT_S", SHORT_WAIT_S)
    kind = _SplitsOnSilentStorage()
    registry, jobs = _planning(kind)

    try:
        planned = runner.plan_one(jobs, registry, library, threads=threads)  # type: ignore[arg-type]
        assert await asyncio.wait_for(planned, HUNG_AFTER_S) == JOB_ID

        assert jobs.state == "error"
        assert jobs.errors == [{"reason": runner.PLANNING_TIMED_OUT, "timeout_s": SHORT_WAIT_S}]
    finally:
        kind.storage_answers.set()


async def test_a_timeout_the_planning_meets_itself_is_its_failure_not_the_limit(
    library: Path, threads: WorkerThreads
) -> None:
    """A socket's timeout inside the split is the planning's failure, said with its detail: taken for
    the loop's limit, the job would say it ran out of a time it never used up."""
    registry, jobs = _planning(_SplitTimesOut())

    assert await runner.plan_one(jobs, registry, library, threads=threads) == JOB_ID  # type: ignore[arg-type]

    assert jobs.state == "error"
    assert jobs.errors == [{"reason": "planning failed", "detail": "the storage did not answer the socket in time"}]


async def test_a_chunk_behind_a_write_that_hangs_is_handed_back_as_transient(
    library: Path, writing: Writing, monkeypatch: pytest.MonkeyPatch, threads: WorkerThreads
) -> None:
    """Behind a write that never returns, a chunk waited for the lock
    until its own time limit, half an hour, then left its thread stuck on the lock for good — five
    times over, one per attempt. It now gives up after a bounded wait, its thread free, and is
    handed back as after a transient failure."""
    monkeypatch.setattr(runner, "CHUNK_WRITE_LOCK_WAIT_S", SHORT_WAIT_S)
    kind = FakeKind()
    registry = Registry()
    registry.register(kind)
    job = _ChunksJob(kind.name, ONE_TASK)
    chunk = queue.Chunk(
        id=1, job_id=JOB_ID, seq=0, payload={"first_task": 0, "task_count": 1}, task_count=1, attempts=1
    )

    with writing(library / DATASET_ID, DATASET_ID):
        executed = runner._execute(job, registry, chunk, library, None, CHUNK_TIME_LIMIT_S, threads)  # type: ignore[arg-type]
        await asyncio.wait_for(executed, HUNG_AFTER_S)

        assert [error["reason"] for error in job.retried] == ["transient failure"]
        assert f"write lock of dataset '{DATASET_ID}'" in job.retried[0]["detail"]
        assert threads.stuck == 0
