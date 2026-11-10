# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Planning beside the other writers of its dataset, without PostgreSQL.

A job's `prepare` may write into its dataset — a table emptied before it is refilled — while this
worker's chunks of other jobs, a person's save or another worker may be writing it too. The
dataset is a real one, and the planning is `runner.plan_one` itself, with the runner's writer; only
PostgreSQL's part is scripted: one job waiting to be planned, and what the planning tells the queue
about it. The same behaviour against a live PostgreSQL is in test_runner.py (`TestPreparation`).

The wait for this worker's write lock of a dataset is bounded, at planning and for a chunk's
write alike, and so is the planning itself: a write that never returns holds the lock for good.
A chunk's part of that is here too, through `runner._execute`, with PostgreSQL's part scripted
the same way.
"""

import asyncio
import threading
from collections import OrderedDict
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractContextManager, asynccontextmanager
from datetime import timedelta
from pathlib import Path
from typing import Any, cast

import pytest
from pixano_worker import queue, runner
from pixano_worker.kinds import FakeKind, Registry
from pixano_worker.kinds.fake import FakeParams
from pixano_worker.reader import JobReader
from pixano_worker.schema import SCHEMA_NAME
from pixano_worker.threads import WorkerThreads
from pixano_worker.writer import JobWriter

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import BBox, Entity, Image, Record


#: Someone else writing a dataset for the length of a block: the `writing` fixture (conftest.py).
Writing = Callable[..., AbstractContextManager[threading.Event]]

JOB_ID = "job-1"
DATASET_ID = "boxes-only"
# One chunk of one task, done at once: the job's work is not what these tests look at.
ONE_TASK = {"task_count": 1, "chunk_size": 1, "seconds_per_task": 0.0}
# The embeddings table the stand-in kind's `prepare` resets: any model, any width will do.
EMBEDDING_MODEL, EMBEDDING_DIM = "stand-in", 4
# How long another job's chunk goes on writing while the planning waits for it: far longer than
# planning takes to reach `prepare` here, so that a `prepare` that did not wait would have run.
CHUNK_WRITE_S = 0.3
# A job on another dataset, planned while the first one's dataset is held.
OTHER_JOB_ID, OTHER_DATASET_ID = "job-2", "other-boxes"
# Stand in for the runner's waits for this worker's write lock of a dataset (ten seconds at
# planning, five minutes for a chunk) and for its limit on a planning (ten minutes): long enough
# for a thread to reach the lock, short enough that a test reaching them stays quick.
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
    PostgreSQL answers it for that job, and kept.

    Statements are told apart by identity — the runner's own constants —, and one this table does
    not know fails the test: a statement the planning adds is not silently misread.

    Attributes:
        state: The job's state.
        lease: For how long the last claim or refresh reserved the job; None once it can be
            claimed again.
        sent: Every statement received, in order.
        errors: What each failure of the job said, in order.
    """

    def __init__(self, kind: str, params: dict[str, Any], job_id: str = JOB_ID, dataset_id: str = DATASET_ID) -> None:
        self.job = (job_id, kind, dataset_id, params)
        self.state = "planning"
        self.lease: timedelta | None = None
        self.sent: list[str] = []
        self.errors: list[dict[str, Any]] = []

    async def execute(self, query: str, params: Any = None) -> _Answer:
        self.sent.append(query)
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

    def lease_expires(self) -> None:
        """Time passes beyond the lease: any planner can claim the job again."""
        self.lease = None


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


class _ResetsTheEmbeddings(FakeKind):
    """A kind whose `prepare` writes, through a call that takes the dataset's lock: it creates the
    embeddings table of its model, emptying any it had, and notes each time it starts."""

    name = "resets-embeddings"

    def __init__(self) -> None:
        self.prepared: list[str] = []

    def prepare(self, writer: JobWriter, params: FakeParams) -> None:
        self.prepared.append(writer.job_id)
        # A call of the dataset itself, past the writer's contract: no kind creates a model's table
        # empty, but this one only needs a write that takes the lock.
        dataset = cast(Dataset, writer.dataset)
        dataset.create_record_embedding_table(dim=EMBEDDING_DIM, model_id=EMBEDDING_MODEL)


class _RefusesItsDataset(FakeKind):
    """A kind whose `prepare` fails for a reason of its own."""

    name = "refuses"

    def prepare(self, writer: JobWriter, params: FakeParams) -> None:
        raise ValueError("this dataset cannot hold what the job writes")


class _SplitsOnSilentStorage(_ResetsTheEmbeddings):
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
    """A dataset of boxes, with no embeddings table, as a dataset imported with boxes only has."""
    Dataset.create(
        library / dataset_id,
        DatasetInfo(id=dataset_id, name="Boxes only", record=Record, entity=Entity, bbox=BBox, views={"image": Image}),
    )


@pytest.fixture
def library(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A library holding a dataset of boxes, with no embeddings table, as one imported with boxes only."""
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


async def _until_free(threads: WorkerThreads) -> None:
    """Wait for the threads a test left behind to finish what they were running."""

    async def drained() -> None:
        while threads.stuck:
            await asyncio.sleep(SHORT_WAIT_S)

    await asyncio.wait_for(drained(), HUNG_AFTER_S)


def _planning(kind: FakeKind) -> tuple[Registry, _JobsTable]:
    """A worker that knows this kind, and one job of it waiting to be planned."""
    registry = Registry()
    registry.register(kind)
    return registry, _JobsTable(kind.name, ONE_TASK)


def _has_embeddings(library: Path) -> bool:
    """Whether the dataset has an embeddings table, as an instance opened now reads it."""
    return Dataset(library / DATASET_ID).has_record_embeddings()


async def test_prepare_waits_for_a_chunk_of_another_job_writing_the_same_dataset(
    library: Path, writing: Writing
) -> None:
    """A `prepare` that writes, run beside another job's chunk writing the same dataset, met the
    dataset's lock, which never waits, and the job failed. It now waits for the chunk's write, as
    another chunk's write does."""
    kind = _ResetsTheEmbeddings()
    registry, jobs = _planning(kind)

    with writing(library / DATASET_ID, DATASET_ID) as write_done:
        planning = asyncio.create_task(runner.plan_one(jobs, registry, library))  # type: ignore[arg-type]
        await asyncio.sleep(CHUNK_WRITE_S)
        assert kind.prepared == [], "prepare ran in the middle of the chunk's write"
        write_done.set()
        assert await planning == JOB_ID

    assert jobs.state == "pending"
    assert kind.prepared == [JOB_ID]
    assert _has_embeddings(library)


async def test_a_dataset_busy_at_planning_leaves_the_job_to_be_planned_again(library: Path, writing: Writing) -> None:
    """The embeddings table must be reset while a person saves: the dataset refuses, and that says
    nothing about the job. It stays to be planned, after a delay, instead of failing."""
    kind = _ResetsTheEmbeddings()
    registry, jobs = _planning(kind)

    with writing(library / DATASET_ID):
        assert await runner.plan_one(jobs, registry, library) == JOB_ID  # type: ignore[arg-type]

        assert (jobs.state, jobs.lease) == ("planning", runner.PLANNING_RETRY_DELAY)
        assert runner.FAIL_JOB not in jobs.sent
        assert not _has_embeddings(library)

    jobs.lease_expires()
    assert await runner.plan_one(jobs, registry, library) == JOB_ID  # type: ignore[arg-type]

    assert jobs.state == "pending"
    assert _has_embeddings(library)
    assert kind.prepared == [JOB_ID, JOB_ID], "the second planning prepared again"


async def test_a_preparation_that_fails_for_its_own_reason_still_fails_the_job(library: Path) -> None:
    """Only a busy dataset is worth planning again: any other failure is the job's."""
    registry, jobs = _planning(_RefusesItsDataset())

    assert await runner.plan_one(jobs, registry, library) == JOB_ID  # type: ignore[arg-type]

    assert jobs.state == "error"
    assert runner.REFRESH_PLANNING not in jobs.sent


async def test_a_write_of_this_worker_that_hangs_postpones_the_planning_of_its_dataset(
    library: Path, writing: Writing, monkeypatch: pytest.MonkeyPatch, threads: WorkerThreads
) -> None:
    """A chunk's write that never returns keeps this worker's
    write lock of its dataset for good. Planning waited for it with no bound, inside the loop's
    turn: the worker stopped claiming and recovering, its healthcheck still green. It now gives up
    after a bounded wait and postpones the job, as when someone else writes the dataset, and the
    loop's next turn plans a job of another dataset."""
    monkeypatch.setattr(runner, "PLANNING_WRITE_LOCK_WAIT_S", SHORT_WAIT_S)
    _boxes_dataset(library, OTHER_DATASET_ID)
    kind = _ResetsTheEmbeddings()
    registry, jobs = _planning(kind)
    other = _JobsTable(kind.name, ONE_TASK, job_id=OTHER_JOB_ID, dataset_id=OTHER_DATASET_ID)

    with writing(library / DATASET_ID, DATASET_ID):
        planned = runner.plan_one(jobs, registry, library, threads=threads)  # type: ignore[arg-type]
        assert await asyncio.wait_for(planned, HUNG_AFTER_S) == JOB_ID

        assert (jobs.state, jobs.lease) == ("planning", runner.PLANNING_RETRY_DELAY)
        assert runner.FAIL_JOB not in jobs.sent
        assert kind.prepared == []

        planned = runner.plan_one(other, registry, library, threads=threads)  # type: ignore[arg-type]
        assert await asyncio.wait_for(planned, HUNG_AFTER_S) == OTHER_JOB_ID

        assert other.state == "pending"

    jobs.lease_expires()
    assert await runner.plan_one(jobs, registry, library, threads=threads) == JOB_ID  # type: ignore[arg-type]

    assert jobs.state == "pending"
    assert kind.prepared == [OTHER_JOB_ID, JOB_ID]


async def test_a_planning_that_never_ends_fails_its_job_and_prepares_nothing_afterwards(
    library: Path, monkeypatch: pytest.MonkeyPatch, threads: WorkerThreads
) -> None:
    """A planning stuck in its reads held the loop's turn with no
    bound. The loop now stops waiting after a limit and fails the job. The thread goes on, and once
    the storage answers it reaches `prepare`, which must not start: nobody awaits it any more, and
    it would clear what a job submitted again has written meanwhile."""
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
    await _until_free(threads)

    assert kind.prepared == []
    assert not _has_embeddings(library)


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
