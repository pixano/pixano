# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests of the pool where the job kinds' code runs."""

import asyncio
import threading

import pytest
from pixano_worker.threads import WorkerThreads


async def test_returns_what_the_work_returns() -> None:
    threads = WorkerThreads(workers=2, stuck_limit=1)

    assert await threads.run(lambda: 42) == 42


async def test_a_timed_out_thread_counts_as_stuck_until_it_finishes() -> None:
    """The thread does not stop with the time limit: it occupies the pool until it returns."""
    threads = WorkerThreads(workers=2, stuck_limit=1)
    release = threading.Event()

    with pytest.raises(TimeoutError):
        await threads.run(release.wait, timeout_s=0.05)

    assert threads.stuck == 1
    assert threads.saturated

    release.set()
    for _ in range(100):
        if threads.stuck == 0:
            break
        await asyncio.sleep(0.01)
    assert threads.stuck == 0
    assert not threads.saturated


async def test_work_still_queued_when_it_times_out_is_not_stuck() -> None:
    """Work that had not started is cancelled for good: it blocks no thread."""
    threads = WorkerThreads(workers=2, stuck_limit=1)
    release = threading.Event()
    occupying = [asyncio.ensure_future(threads.run(release.wait)) for _ in range(2)]
    await asyncio.sleep(0.05)

    with pytest.raises(TimeoutError):
        await threads.run(lambda: None, timeout_s=0.05)

    assert threads.stuck == 0
    release.set()
    await asyncio.gather(*occupying)


def test_the_pool_must_outnumber_its_saturation_threshold() -> None:
    """Otherwise it would be entirely blocked before it could report its saturation."""
    with pytest.raises(ValueError, match="threshold"):
        WorkerThreads(workers=2, stuck_limit=2)


def test_sized_for_concurrency() -> None:
    threads = WorkerThreads.for_concurrency(4)

    assert threads.stuck_limit == 4


async def test_a_cancelled_wait_leaves_a_thread_behind_and_counts_it() -> None:
    """The case of a chunk abandoned at the worker's stop: the same lost thread as after a time limit."""
    threads = WorkerThreads(workers=2, stuck_limit=1)
    release = threading.Event()
    waiting = asyncio.ensure_future(threads.run(release.wait))
    await asyncio.sleep(0.05)

    waiting.cancel()
    with pytest.raises(asyncio.CancelledError):
        await waiting

    assert threads.stuck == 1
    release.set()


async def test_renewing_abandons_the_stuck_threads_and_resets_the_count() -> None:
    threads = WorkerThreads(workers=2, stuck_limit=1)
    release = threading.Event()
    with pytest.raises(TimeoutError):
        await threads.run(release.wait, timeout_s=0.05)
    assert threads.saturated

    abandoned = threads.renew()

    assert abandoned == 1
    assert threads.stuck == 0
    assert await threads.run(lambda: "fresh") == "fresh", "the renewed pool works"
    # The abandoned thread finishes afterwards: it must not decrement the pool that replaced it.
    release.set()
    await asyncio.sleep(0.05)
    assert threads.stuck == 0
