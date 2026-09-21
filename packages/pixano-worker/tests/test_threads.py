# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests du pool où tourne le code des types de jobs."""

import asyncio
import threading

import pytest
from pixano_worker.threads import WorkerThreads


async def test_returns_what_the_work_returns() -> None:
    threads = WorkerThreads(workers=2, stuck_limit=1)

    assert await threads.run(lambda: 42) == 42


async def test_a_timed_out_thread_counts_as_stuck_until_it_finishes() -> None:
    """Le thread ne s'arrête pas avec le délai : il occupe le pool jusqu'à ce qu'il revienne."""
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
    """Un travail qui n'avait pas commencé est annulé pour de bon : il ne bloque aucun thread."""
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
    """Sinon il serait entièrement bloqué avant d'avoir pu signaler sa saturation."""
    with pytest.raises(ValueError, match="seuil"):
        WorkerThreads(workers=2, stuck_limit=2)


def test_sized_for_concurrency() -> None:
    threads = WorkerThreads.for_concurrency(4)

    assert threads.stuck_limit == 4


async def test_a_cancelled_wait_leaves_a_thread_behind_and_counts_it() -> None:
    """Le cas d'un chunk abandonné à l'arrêt du worker : même thread perdu qu'après un délai."""
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
    assert await threads.run(lambda: "neuf") == "neuf", "le pool renouvelé travaille"
    # Le thread abandonné finit après coup : il ne doit pas décompter le pool qui l'a remplacé.
    release.set()
    await asyncio.sleep(0.05)
    assert threads.stuck == 0
