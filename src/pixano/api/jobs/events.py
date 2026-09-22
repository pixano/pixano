# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Listening to job events and fanning them out to open streams.

One connection listens, every stream shares it. The obvious alternative — a PostgreSQL
connection per open browser tab — does not hold: ten researchers with three tabs each would
spend thirty connections watching a progress bar.

`NOTIFY` only rings the bell: its payload is capped at 8 kB and reaches only the clients
connected at commit time. So the bell carries identifiers, the stream reads the row, and a
client that was away catches up from the table by identifier. That is what `job_events.id`
and the absolute counters in each payload were put there for.
"""

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable

import psycopg

from pixano.datasets import Dataset

from .queries import NOTIFY_CHANNEL, SCHEMA_NAME


logger = logging.getLogger(__name__)

# Backoff while the database is unreachable. The cap is low: an interrupted listener loses
# nothing — catching up by identifier repairs the gap — but it leaves the interfaces without
# news, so it comes back quickly.
_RETRY_BACKOFF_S = (1, 2, 5, 10)

# Beyond this, a subscriber that does not read fast enough is dropped rather than left to grow
# its queue without end. It reconnects and catches up by identifier.
_SUBSCRIBER_BACKLOG = 1000

SELECT_SINCE = f"""
SELECT id, job_id, type, payload, created_at
FROM {SCHEMA_NAME}.job_events
WHERE job_id = %s AND id > %s
ORDER BY id
"""

SELECT_ONE = f"""
SELECT id, job_id, type, payload, created_at
FROM {SCHEMA_NAME}.job_events WHERE id = %s
"""

# The dataset a job worked on, read when the job reaches a terminal state: what the worker
# wrote — an embeddings table this process has never seen — must reach the API's own caches.
SELECT_DATASET_OF_JOB = f"SELECT dataset FROM {SCHEMA_NAME}.jobs WHERE id = %s"

# The states after which a job writes nothing more.
TERMINAL_STATES = frozenset({"done", "error", "cancelled"})


@dataclass(frozen=True)
class JobEvent:
    """One progress or state event, as a stream delivers it."""

    id: int
    job_id: str
    type: str
    payload: dict[str, Any]

    def to_sse(self) -> str:
        """Render as a Server-Sent Event.

        The identifier goes out as `id:` so that a browser resends it as `Last-Event-ID` on
        reconnection, and the stream resumes exactly where it stopped.
        """
        body = json.dumps({"job_id": self.job_id, **self.payload}, default=str)
        return f"id: {self.id}\nevent: {self.type}\ndata: {body}\n\n"


class _Subscriber:
    """One open stream, and what it wants to hear about."""

    def __init__(self, job_id: str | None, types: frozenset[str] | None) -> None:
        self.job_id = job_id
        self.types = types
        self.queue: asyncio.Queue[JobEvent] = asyncio.Queue(maxsize=_SUBSCRIBER_BACKLOG)
        self.dropped = False

    def wants(self, event: JobEvent) -> bool:
        """Whether this event belongs in this stream."""
        if self.job_id is not None and event.job_id != self.job_id:
            return False
        return self.types is None or event.type in self.types

    def offer(self, event: JobEvent) -> None:
        """Hand over an event, without ever blocking the listener."""
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            # A slow subscriber must not delay the others. It is let go: its stream closes once
            # it has drained its queue, and its reconnection catches up on what it missed.
            self.dropped = True


class EventBroker:
    """Holds the single listening connection and feeds every open stream."""

    def __init__(
        self, database_url: str | None, on_job_ended: Callable[[str], None] = Dataset.invalidate_caches
    ) -> None:
        """Create a broker. A missing URL makes it inert rather than broken.

        Args:
            database_url: Where the queue lives.
            on_job_ended: Called with the dataset identifier of every job that reaches a
                terminal state. The default drops this process's cached view of the dataset:
                the worker writes tables — an embeddings table above all — that a `Dataset`
                opened before the job would never see, since it reads its sidecar once.
        """
        self._database_url = database_url
        self._on_job_ended = on_job_ended
        self._subscribers: set[_Subscriber] = set()
        self._task: asyncio.Task | None = None
        self._listening = asyncio.Event()

    @property
    def enabled(self) -> bool:
        """Whether a queue is configured at all."""
        return bool(self._database_url)

    def start(self) -> None:
        """Begin listening in the background."""
        if self.enabled and self._task is None:
            self._task = asyncio.create_task(self._listen_forever(), name="pixano-jobs-listener")

    async def stop(self) -> None:
        """Stop listening and let every stream end."""
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

    async def _listen_forever(self) -> None:
        """Listen, and come back after a dropped connection.

        Losing the connection loses no event: every stream catches up by identifier when it
        reconnects. What it loses is liveness, so the retry stays short.
        """
        attempt = 0
        while True:
            try:
                # Two connections, and not a luxury: querying the listening connection while
                # iterating its notifications blocks it forever. The bell carries identifiers
                # only, so the row has to be read elsewhere.
                listen = await psycopg.AsyncConnection.connect(self._database_url or "", autocommit=True)
                read = await psycopg.AsyncConnection.connect(self._database_url or "", autocommit=True)
                try:
                    await listen.execute(f"LISTEN {NOTIFY_CHANNEL}")
                    logger.info("listening for job events on %s", NOTIFY_CHANNEL)
                    attempt = 0
                    self._listening.set()
                    async for notification in listen.notifies():
                        await self._dispatch(read, notification.payload)
                finally:
                    await listen.close()
                    await read.close()
            except asyncio.CancelledError:
                raise
            except Exception:
                self._listening.clear()
                delay = _RETRY_BACKOFF_S[min(attempt, len(_RETRY_BACKOFF_S) - 1)]
                logger.warning("job event listener lost, retrying in %ss", delay, exc_info=True)
                attempt += 1
                await asyncio.sleep(delay)

    async def _dispatch(self, conn: psycopg.AsyncConnection, raw: str) -> None:
        """Read the announced row and hand it to whoever wants it."""
        try:
            announced = json.loads(raw)
            event_id = int(announced["event_id"])
        except (ValueError, KeyError, TypeError):
            logger.warning("unreadable job event notification: %r", raw)
            return

        wanted = [sub for sub in self._subscribers if sub.job_id in (None, announced.get("job_id"))]
        # A state event is read whether or not anyone is listening: the end of a job is what
        # this process needs to hear for itself, not only what it relays.
        if not wanted and announced.get("type") != "state":
            return

        row = await (await conn.execute(SELECT_ONE, (event_id,))).fetchone()
        if row is None:
            return
        event = JobEvent(id=row[0], job_id=str(row[1]), type=row[2], payload=row[3])
        if event.type == "state" and event.payload.get("state") in TERMINAL_STATES:
            await self._job_ended(conn, event.job_id)
        for subscriber in wanted:
            if subscriber.wants(event):
                subscriber.offer(event)

    async def _job_ended(self, conn: psycopg.AsyncConnection, job_id: str) -> None:
        row = await (await conn.execute(SELECT_DATASET_OF_JOB, (job_id,))).fetchone()
        if row is None:
            return
        try:
            self._on_job_ended(str(row[0]))
        except Exception:
            logger.exception("job %s: the end-of-job hook failed", job_id)

    @asynccontextmanager
    async def subscribe(
        self, job_id: str | None = None, types: frozenset[str] | None = None
    ) -> AsyncIterator[_Subscriber]:
        """Register a stream for the duration of a request."""
        subscriber = _Subscriber(job_id, types)
        self._subscribers.add(subscriber)
        try:
            yield subscriber
        finally:
            self._subscribers.discard(subscriber)


# Event identifiers are handed out before commit, so an event committed late can carry an
# identifier below the last one a client saw. Catching up from that identifier alone would skip
# it for good. Reading back a little further costs a few duplicates, which absolute counters
# and identifier-ordered states make harmless.
CATCH_UP_SLACK = 100


class SentWindow:
    """The identifiers a stream has sent, kept only as far back as an event can arrive late.

    A plain set would grow for the life of the connection — a panel left open for days on a
    team running large jobs is tens of megabytes per tab. An event can only arrive late by
    about `CATCH_UP_SLACK` identifiers, so anything below the highest identifier seen minus
    that margin is treated as already sent, and forgotten.
    """

    def __init__(self, slack: int = CATCH_UP_SLACK) -> None:
        """Create an empty window."""
        self._slack = slack
        self._sent: set[int] = set()
        self._highest = 0

    def already_sent(self, event_id: int) -> bool:
        """Whether this identifier was sent, or is too old to be a late arrival."""
        return event_id in self._sent or event_id <= self._highest - self._slack

    def mark(self, event_id: int) -> None:
        """Record an identifier as sent, and forget the ones now out of the window."""
        self._sent.add(event_id)
        if event_id > self._highest:
            self._highest = event_id
            floor = self._highest - self._slack
            if len(self._sent) > 2 * self._slack:
                self._sent = {sent for sent in self._sent if sent > floor}

    def __len__(self) -> int:
        """How many identifiers the window holds."""
        return len(self._sent)


async def read_since(database_url: str, job_id: str, after_id: int, slack: int = CATCH_UP_SLACK) -> list[JobEvent]:
    """Read the events a reconnecting client missed, and a few it may have seen."""
    async with await psycopg.AsyncConnection.connect(database_url) as conn:
        rows = await (await conn.execute(SELECT_SINCE, (job_id, max(0, after_id - slack)))).fetchall()
    return [JobEvent(id=row[0], job_id=str(row[1]), type=row[2], payload=row[3]) for row in rows]
