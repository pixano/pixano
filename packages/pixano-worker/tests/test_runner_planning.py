# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A chunk's wait for its dataset, without PostgreSQL.

The wait for this worker's write lock of a dataset is bounded for a chunk's write: a write that
never returns holds the lock for good, and must hold up no more than its own dataset's writes. The
dataset is a real one, and the chunk goes through `runner._execute`; only PostgreSQL's part is
scripted.
"""

import asyncio
import threading
from collections import OrderedDict
from collections.abc import Callable
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any

import pytest
from pixano_worker import queue, runner
from pixano_worker.kinds import FakeKind, Registry
from pixano_worker.schema import SCHEMA_NAME
from pixano_worker.threads import WorkerThreads

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import BBox, Entity, Image, Record


#: Someone else writing a dataset for the length of a block: the `writing` fixture (conftest.py).
Writing = Callable[..., AbstractContextManager[threading.Event]]

JOB_ID = "job-1"
DATASET_ID = "boxes-only"
# One chunk of one task, done at once: the job's work is not what these tests look at.
ONE_TASK = {"task_count": 1, "chunk_size": 1, "seconds_per_task": 0.0}
# Stands in for the runner's wait for this worker's write lock of a dataset (five minutes, for a
# chunk): long enough for a thread to reach the lock, short enough that a test reaching it stays
# quick.
SHORT_WAIT_S = 0.2
# A chunk's own time limit, standing for the half hour: far beyond `SHORT_WAIT_S`, so that a chunk
# that reaches it waited for the lock with no bound of its own.
CHUNK_TIME_LIMIT_S = 2.0
# How long a test waits for a chunk before calling it hung: beyond every wait the runner is given
# here, and below the other writer's own hold (`LOCK_HANDOVER_TIMEOUT_S`, ten seconds), so that
# only a wait with no bound reaches it.
HUNG_AFTER_S = 5.0
# The statement `runner._execute` reads a chunk's job with, built as it builds it.
SELECT_CHUNKS_JOB = f"SELECT kind, params, dataset FROM {SCHEMA_NAME}.jobs WHERE id = %s"


class _Answer:
    """What `execute` returns: the cursor the runner reads a row or a row count from."""

    def __init__(self, row: tuple[Any, ...] | None = None, rowcount: int = 0) -> None:
        self.row, self.rowcount = row, rowcount

    async def fetchone(self) -> tuple[Any, ...] | None:
        return self.row


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
