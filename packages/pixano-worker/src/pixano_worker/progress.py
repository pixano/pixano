# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What a running chunk says of its work, and hears of its job, while it runs.

A kind's `process` runs in a thread that holds no database connection. A long chunk — many
inference calls one after the other — still has two things to exchange with the queue before it
ends: how far it got, for a progress bar that moves, and whether its job was cancelled meanwhile,
so that it stops between two of its steps rather than at its end. It writes the one here and reads
the other; the worker's loop, which holds the chunk's connection, records the first and writes the
second.
"""

import threading


#: Why a chunk was told to stop: its job was cancelled — it leaves the queue —, or the worker no
#: longer waits for it — past its time limit, or stopping —, or another worker took it over.
JOB_CANCELLED = "its job was cancelled"
NOT_AWAITED = "the worker stopped waiting for it"
TAKEN_OVER = "its lease went to another worker"


class ChunkCancelled(Exception):
    """The chunk is to stop where it is and write nothing: its job was cancelled, or nobody waits for it.

    Raised by a kind between two steps of its work (`ChunkProgress.stop_if_cancelled`). After a
    cancellation, the worker takes the chunk out of the queue, as it does a chunk it had not
    started; a chunk past its time limit, or whose lease went to another worker, was handed back
    already, and its thread just ends.
    """


class ChunkProgress:
    """How far a running chunk got, in its own tasks, and whether its job was cancelled.

    Attributes:
        task_count: The chunk's tasks: progress never goes past them.
    """

    def __init__(self, task_count: int) -> None:
        """Start a chunk's progress at none of its tasks.

        Args:
            task_count: The chunk's tasks.
        """
        self.task_count = task_count
        self._done = 0
        self._lock = threading.Lock()
        self._cancelled = threading.Event()
        self._why: str | None = None

    def advance_to(self, done: int) -> None:
        """Say how many of the chunk's tasks are done: never fewer than said before, nor more than it has.

        Args:
            done: The tasks done so far.
        """
        with self._lock:
            self._done = max(self._done, min(done, self.task_count))

    @property
    def done(self) -> int:
        """The tasks done so far, as last said."""
        with self._lock:
            return self._done

    @property
    def cancelled(self) -> bool:
        """Whether the chunk was told to stop since it started."""
        return self._cancelled.is_set()

    @property
    def why(self) -> str | None:
        """Why the chunk was told to stop, the first time it was; None while it was not."""
        return self._why

    def cancel(self, why: str = JOB_CANCELLED) -> None:
        """Tell the chunk to stop: for the worker, on its job's cancellation or once it stops waiting for it.

        Args:
            why: Why: `JOB_CANCELLED`, `NOT_AWAITED` or `TAKEN_OVER`. The first reason given stays.
        """
        with self._lock:
            if self._why is None:
                self._why = why
        self._cancelled.set()

    def stop_if_cancelled(self) -> None:
        """Stop the chunk when it was told to: for a kind, between two steps of its work.

        Raises:
            ChunkCancelled: The chunk was told to stop.
        """
        if self.cancelled:
            raise ChunkCancelled(f"the chunk stopped while it ran: {self.why}")
