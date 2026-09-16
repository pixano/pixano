# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Réclamation et restitution de chunks.

Les primitives qu'appelle le runner. Elles sont ici, séparées de la boucle, parce qu'elles
portent les seules propriétés qui comptent — aucun doublon, aucune perte, et une reprise qui
ne dépend d'aucun process vivant — et qu'on veut les tester sans runner.

Elles sont asynchrones parce que le runner l'est : il fait tourner plusieurs chunks à la fois,
et chacun attend surtout du réseau.

Rien ici ne joint la table des jobs. La réclamation doit rester une requête sur un seul index
partiel : c'est pourquoi l'annulation d'un job bascule ses chunks en attente plutôt que de
laisser la file interroger l'état du job à chaque tour.
"""

import os
import socket
from dataclasses import dataclass
from datetime import timedelta
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from .config import MAX_HEARTBEAT_AGE_S
from .schema import SCHEMA_NAME


# Le bail doit dépasser la fenêtre au bout de laquelle docker déclare le worker mort, sinon
# un chunk serait volé avant même qu'on ait constaté que son porteur ne répond plus.
LEASE_TTL = timedelta(seconds=max(120, MAX_HEARTBEAT_AGE_S * 4))

# Au-delà, un chunk qui fait tomber son worker à chaque tentative est mis de côté plutôt que
# de faire boucler la file indéfiniment.
MAX_ATTEMPTS = 3

CLAIM = f"""
UPDATE {SCHEMA_NAME}.job_chunks AS c
SET state = 'running',
    attempts = c.attempts + 1,
    claimed_by = %s,
    lease_until = now() + %s,
    updated_at = now()
FROM (
    SELECT id FROM {SCHEMA_NAME}.job_chunks
    WHERE state = 'pending'
    ORDER BY id
    FOR UPDATE SKIP LOCKED
    LIMIT %s
) AS picked
WHERE c.id = picked.id
RETURNING c.id, c.job_id, c.seq, c.payload, c.task_count, c.attempts
"""

# `attempts` sert de jeton de garde : un worker dont le bail a expiré pendant qu'il
# travaillait ne doit pas écraser le résultat de celui qui a repris son chunk.
FINISH = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'done', lease_until = NULL, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
RETURNING job_id, task_count
"""

FAIL = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'error', lease_until = NULL, error = %s, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
RETURNING job_id
"""

# Un chunk dont le job est annulé ne revient pas en file : il en sort. Le rendre « en
# attente » le ferait reréclamer au tour suivant, relâcher, reréclamer — sans fin, et le job
# ne se conclurait jamais faute de voir sa file se vider.
CANCEL_CHUNK = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'cancelled', lease_until = NULL, claimed_by = NULL, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
"""

RELEASE = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'pending', lease_until = NULL, claimed_by = NULL, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
"""

# Ce que le worker fait de ses propres chunks après un arrêt brutal : les rendre tout de
# suite, au lieu d'attendre l'expiration de leur bail.
RELEASE_OWN = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'pending', lease_until = NULL, claimed_by = NULL, updated_at = now()
WHERE state = 'running' AND claimed_by = %s
RETURNING id
"""

RECLAIM_EXPIRED = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'pending', lease_until = NULL, claimed_by = NULL, updated_at = now()
WHERE state = 'running' AND lease_until < now() AND attempts < %s
RETURNING id
"""

ABANDON_EXHAUSTED = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'error', lease_until = NULL, updated_at = now(),
    error = jsonb_build_object('reason', 'abandonné', 'attempts', attempts)
WHERE state = 'running' AND lease_until < now() AND attempts >= %s
RETURNING id
"""

ADVANCE_JOB = f"""
UPDATE {SCHEMA_NAME}.jobs
SET done_tasks = done_tasks + %s,
    state = CASE WHEN state = 'pending' THEN 'running' ELSE state END,
    updated_at = now()
WHERE id = %s
"""

IS_CANCELLED = f"SELECT cancel_requested_at IS NOT NULL FROM {SCHEMA_NAME}.jobs WHERE id = %s"


@dataclass(frozen=True)
class Chunk:
    """Un lot de tâches réclamé, avec le jeton qui autorise à écrire son résultat."""

    id: int
    job_id: str
    seq: int
    payload: dict[str, Any]
    task_count: int
    attempts: int


def worker_identity() -> str:
    """Nommer ce worker, pour le diagnostic et la restitution après un arrêt brutal."""
    return f"{socket.gethostname()}:{os.getpid()}"


async def claim(conn: psycopg.AsyncConnection, worker_id: str, batch_size: int) -> list[Chunk]:
    """Réclamer jusqu'à `batch_size` chunks en attente.

    Deux workers qui réclament en même temps obtiennent des ensembles disjoints : le verrou
    de ligne et `SKIP LOCKED` s'en chargent, sans qu'aucun des deux n'attende l'autre.
    """
    cursor = await conn.execute(CLAIM, (worker_id, LEASE_TTL, batch_size))
    rows = await cursor.fetchall()
    return [
        Chunk(id=row[0], job_id=str(row[1]), seq=row[2], payload=row[3], task_count=row[4], attempts=row[5])
        for row in rows
    ]


async def finish(conn: psycopg.AsyncConnection, chunk: Chunk) -> bool:
    """Marquer un chunk terminé et avancer la progression de son job.

    Returns:
        False si le chunk avait été repris par un autre worker entre-temps ; l'appelant doit
        alors jeter son résultat plutôt que d'écraser celui de son successeur.
    """
    async with conn.transaction():
        row = await (await conn.execute(FINISH, (chunk.id, chunk.attempts))).fetchone()
        if row is None:
            return False
        await conn.execute(ADVANCE_JOB, (row[1], row[0]))
    return True


async def fail(conn: psycopg.AsyncConnection, chunk: Chunk, error: dict[str, Any]) -> bool:
    """Marquer un chunk en échec. Même garde que `finish`."""
    cursor = await conn.execute(FAIL, (Jsonb(error), chunk.id, chunk.attempts))
    return await cursor.fetchone() is not None


async def release(conn: psycopg.AsyncConnection, chunk: Chunk) -> bool:
    """Remettre un chunk en file sans l'exécuter."""
    return (await conn.execute(RELEASE, (chunk.id, chunk.attempts))).rowcount > 0


async def cancel_chunk(conn: psycopg.AsyncConnection, chunk: Chunk) -> bool:
    """Sortir de la file un chunk dont le job a été annulé."""
    return (await conn.execute(CANCEL_CHUNK, (chunk.id, chunk.attempts))).rowcount > 0


async def release_own(conn: psycopg.AsyncConnection, worker_id: str) -> int:
    """Rendre les chunks laissés par une exécution précédente de ce même worker.

    Le bail finirait par les libérer de toute façon ; les rendre au démarrage transforme une
    reprise de deux minutes en reprise immédiate.
    """
    return len(await (await conn.execute(RELEASE_OWN, (worker_id,))).fetchall())


async def reclaim_expired(conn: psycopg.AsyncConnection, max_attempts: int = MAX_ATTEMPTS) -> tuple[int, int]:
    """Remettre en file les chunks dont le bail a expiré, écarter ceux qui s'acharnent.

    Returns:
        Le nombre de chunks remis en file, et le nombre mis en échec.
    """
    async with conn.transaction():
        reclaimed = len(await (await conn.execute(RECLAIM_EXPIRED, (max_attempts,))).fetchall())
        abandoned = len(await (await conn.execute(ABANDON_EXHAUSTED, (max_attempts,))).fetchall())
    return reclaimed, abandoned


async def is_cancelled(conn: psycopg.AsyncConnection, job_id: str) -> bool:
    """Une annulation a-t-elle été demandée pour ce job ?"""
    row = await (await conn.execute(IS_CANCELLED, (job_id,))).fetchone()
    return row is not None and bool(row[0])
