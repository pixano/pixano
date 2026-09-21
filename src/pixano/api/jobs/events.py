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
from typing import Any, AsyncIterator

import psycopg

from .queries import SCHEMA_NAME


logger = logging.getLogger(__name__)

NOTIFY_CHANNEL = "pixano_jobs_events"

# Espacement des tentatives quand la base est injoignable. Le plafond est bas : une écoute
# interrompue ne perd rien — le rattrapage par identifiant répare le trou — mais elle laisse
# les interfaces sans nouvelles, donc on revient vite.
_RETRY_BACKOFF_S = (1, 2, 5, 10)

# Au-delà, un abonné qui ne lit pas assez vite est déconnecté plutôt que de faire grossir sa
# file sans fin. Il se reconnectera et rattrapera par identifiant.
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
            # Un abonné lent ne doit pas retarder les autres. On le lâche ; sa reconnexion
            # rattrapera ce qu'il a manqué par identifiant.
            self.dropped = True


class EventBroker:
    """Holds the single listening connection and feeds every open stream."""

    def __init__(self, database_url: str | None) -> None:
        """Create a broker. A missing URL makes it inert rather than broken."""
        self._database_url = database_url
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
                # Deux connexions, et ce n'est pas du luxe : interroger la connexion qui écoute
                # pendant qu'on itère ses notifications la bloque indéfiniment. La sonnette ne
                # portant que des identifiants, la ligne doit être lue ailleurs.
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
        if not wanted:
            return

        row = await (await conn.execute(SELECT_ONE, (event_id,))).fetchone()
        if row is None:
            return
        event = JobEvent(id=row[0], job_id=str(row[1]), type=row[2], payload=row[3])
        for subscriber in wanted:
            if subscriber.wants(event):
                subscriber.offer(event)

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


async def read_since(database_url: str, job_id: str, after_id: int) -> list[JobEvent]:
    """Read the events a reconnecting client missed."""
    async with await psycopg.AsyncConnection.connect(database_url) as conn:
        rows = await (await conn.execute(SELECT_SINCE, (job_id, after_id))).fetchall()
    return [JobEvent(id=row[0], job_id=str(row[1]), type=row[2], payload=row[3]) for row in rows]
