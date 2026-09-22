# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The threads where the job kinds' code runs.

A dedicated pool rather than asyncio's, for a precise reason: a thread cannot be interrupted
from the outside. A chunk that exceeds its time limit is handed back to the queue, but its
thread goes on until the blocked call returns — maybe never. In asyncio's default pool, these
threads pile up without anything noticing, until no work can start any more, planning included;
and the heartbeat, which runs on the event loop, keeps saying the worker is fine.

Here, stuck threads are counted. Past a threshold, the pool declares itself saturated and
renews itself: the stuck threads are abandoned to their fate, a fresh executor takes over, and
the worker goes on. Renewing rather than exiting the process: the compose's automatic restart
is bounded — Docker does not reset its counter, verified — and a worker that relied on it would
end up stopped for good at the third incident.
"""

import asyncio
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, TypeVar


T = TypeVar("T")


class WorkerThreads:
    """A bounded pool, which knows how many of its threads are stuck.

    Attributes:
        stuck_limit: Number of stuck threads from which the pool is saturated.
    """

    def __init__(self, workers: int, stuck_limit: int) -> None:
        """Create the pool.

        Args:
            workers: Number of threads. It must exceed `stuck_limit`: this is what leaves the
                worker enough to notice the saturation before being entirely blocked.
            stuck_limit: Number of stuck threads that makes the pool saturated.

        Raises:
            ValueError: The pool does not have more threads than the saturation threshold.
        """
        if workers <= stuck_limit:
            raise ValueError(f"{workers} thread(s) for a saturation threshold of {stuck_limit}")
        self._workers = workers
        self._executor = self._new_executor()
        self.stuck_limit = stuck_limit
        self._stuck = 0
        # Incremented on every renewal: an abandoned thread that finishes afterwards must not
        # decrement the counter of the executor that replaced it.
        self._generation = 0
        self._lock = threading.Lock()

    def _new_executor(self) -> ThreadPoolExecutor:
        return ThreadPoolExecutor(max_workers=self._workers, thread_name_prefix="pixano-job")

    @classmethod
    def for_concurrency(cls, concurrency: int) -> "WorkerThreads":
        """Size the pool for a number of in-flight chunks.

        One thread per in-flight chunk, one for planning, and as many in reserve as there are
        chunks: saturated when as many threads are stuck as there are in-flight chunks, the
        pool can still serve the whole concurrency at the moment it reports it.
        """
        return cls(workers=2 * concurrency + 1, stuck_limit=concurrency)

    @property
    def stuck(self) -> int:
        """Threads still busy with work whose result we stopped waiting for."""
        with self._lock:
            return self._stuck

    @property
    def saturated(self) -> bool:
        """The pool has too many stuck threads for the worker to go on."""
        return self.stuck >= self.stuck_limit

    async def run(self, work: Callable[[], T], timeout_s: float | None = None) -> T:
        """Run `work` in a thread of the pool, waiting at most `timeout_s`.

        Raises:
            TimeoutError: The time limit is exceeded. The thread, if it had started, goes on and
                is counted as stuck until it finishes. A cancellation of the wait — a chunk
                abandoned at the worker's stop — leaves the same thread behind, and counts it
                the same way.
        """
        with self._lock:
            executor, generation = self._executor, self._generation
        future = executor.submit(work)
        try:
            return await asyncio.wait_for(asyncio.wrap_future(future), timeout_s)
        except (TimeoutError, asyncio.CancelledError):
            # Work still queued is cancelled for good and blocks nothing; only work already
            # started leaves a thread behind.
            if not future.cancelled():
                self._count_stuck(future, generation)
            raise

    def _count_stuck(self, future: Future, generation: int) -> None:
        with self._lock:
            if generation == self._generation:
                self._stuck += 1

        def release(_: Future) -> None:
            with self._lock:
                if generation == self._generation:
                    self._stuck -= 1

        future.add_done_callback(release)

    def renew(self) -> int:
        """Abandon the stuck threads and start over with a fresh executor.

        The abandoned threads go on until their call returns — the inference call has its own
        time limit, which will free them — but they no longer count, and nothing awaits them.

        Returns:
            The number of abandoned threads.
        """
        with self._lock:
            abandoned = self._stuck
            old, self._executor = self._executor, self._new_executor()
            self._stuck = 0
            self._generation += 1
        old.shutdown(wait=False, cancel_futures=True)
        return abandoned

    def shutdown(self) -> None:
        """Release the pool without waiting for the stuck threads."""
        self._executor.shutdown(wait=False, cancel_futures=True)
