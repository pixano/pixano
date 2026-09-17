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
from typing import Any, Protocol, Sequence

import psycopg
from psycopg.types.json import Jsonb

from .config import MAX_HEARTBEAT_AGE_S
from .schema import SCHEMA_NAME


# Le bail doit dépasser la fenêtre au bout de laquelle docker déclare le worker mort, sinon
# un chunk serait volé avant même qu'on ait constaté que son porteur ne répond plus.
LEASE_TTL = timedelta(seconds=max(120, MAX_HEARTBEAT_AGE_S * 4))

# Un chunk qui tourne prolonge son bail bien avant qu'il expire : trois occasions par bail,
# pour qu'une requête lente ou une connexion qui hoquette ne suffise pas à le perdre.
LEASE_REFRESH_INTERVAL = LEASE_TTL / 3

# Au-delà, un chunk est mis de côté plutôt que de faire boucler la file indéfiniment — qu'il
# fasse tomber son worker à chaque tentative ou qu'il bute sur une panne qui ne passe pas.
# Cinq, parce qu'avec le délai ci-dessous cela laisse près de quatre minutes à une inférence
# pour revenir : le temps d'un redémarrage avec rechargement du modèle.
MAX_ATTEMPTS = 5

# Délai avant de rejouer un chunk après une panne passagère, doublé à chaque tentative. Le
# plafond évite qu'un chunk disparaisse une heure pour une panne déjà réparée.
RETRY_BASE_DELAY = timedelta(seconds=15)
RETRY_MAX_DELAY = timedelta(minutes=5)

CLAIM = f"""
UPDATE {SCHEMA_NAME}.job_chunks AS c
SET state = 'running',
    attempts = c.attempts + 1,
    claimed_by = %s,
    lease_until = now() + %s,
    updated_at = now()
FROM (
    SELECT id FROM {SCHEMA_NAME}.job_chunks
    WHERE state = 'pending' AND available_at <= now()
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
SET state = 'done', lease_until = NULL, error = NULL, produced = %s, skipped = %s, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
RETURNING job_id, task_count
"""

# Un item rejoué avec son chunk remplace sa ligne : la quarantaine reflète la dernière
# tentative, pas l'historique de toutes.
QUARANTINE = f"""
INSERT INTO {SCHEMA_NAME}.job_items (job_id, chunk_id, item_id, reason, detail)
VALUES (%s, %s, %s, %s, %s)
ON CONFLICT (job_id, item_id) DO UPDATE
SET chunk_id = EXCLUDED.chunk_id, reason = EXCLUDED.reason, detail = EXCLUDED.detail, created_at = now()
"""

# Une panne passagère rend le chunk à la file après un délai — ou l'écarte, s'il a épuisé ses
# tentatives. Même jeton de garde que FINISH.
RETRY = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = CASE WHEN attempts < %(max_attempts)s THEN 'pending' ELSE 'error' END,
    lease_until = NULL,
    claimed_by = CASE WHEN attempts < %(max_attempts)s THEN NULL ELSE claimed_by END,
    available_at = now() + least(%(base)s * power(2, attempts - 1), %(cap)s),
    error = %(error)s,
    updated_at = now()
WHERE id = %(id)s AND state = 'running' AND attempts = %(attempts)s
RETURNING state
"""

# Le bail d'un chunk qui tourne encore. Même jeton de garde : un worker qui a perdu son chunk
# ne peut pas prolonger le bail de son successeur.
REFRESH_LEASE = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET lease_until = now() + %s, updated_at = now()
WHERE id = %s AND state = 'running' AND attempts = %s
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
# suite, au lieu d'attendre l'expiration de leur bail. Avec le même plafond que la reprise des
# baux : un chunk qui fait tomber son worker à chaque tentative ferait sinon boucler un worker
# redémarré automatiquement, puisque ce chemin ne regardait jamais les tentatives.
RELEASE_OWN = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'pending', lease_until = NULL, claimed_by = NULL, updated_at = now()
WHERE state = 'running' AND claimed_by = %s AND attempts < %s
RETURNING id
"""

ABANDON_OWN = f"""
UPDATE {SCHEMA_NAME}.job_chunks
SET state = 'error', lease_until = NULL, updated_at = now(),
    error = jsonb_build_object('reason', 'abandonné', 'attempts', attempts)
WHERE state = 'running' AND claimed_by = %s AND attempts >= %s
RETURNING job_id
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
RETURNING job_id
"""

# Le premier chunk terminé fait passer le job en cours. L'ancien état est lu sous le verrou de
# la ligne, pour que l'appelant sache si c'est lui qui a fait la transition — et l'annonce une
# seule fois, même quand plusieurs chunks du job finissent ensemble.
ADVANCE_JOB = f"""
WITH previous AS (
    SELECT state FROM {SCHEMA_NAME}.jobs WHERE id = %(job)s FOR UPDATE
)
UPDATE {SCHEMA_NAME}.jobs AS j
SET done_tasks = j.done_tasks + %(tasks)s,
    state = CASE WHEN j.state = 'pending' THEN 'running' ELSE j.state END,
    updated_at = now()
FROM previous
WHERE j.id = %(job)s
RETURNING previous.state = 'pending'
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


@dataclass(frozen=True)
class Recovery:
    """Ce qu'une reprise de chunks orphelins a fait.

    Attributes:
        requeued: Chunks remis en file.
        abandoned_jobs: Jobs dont au moins un chunk vient d'être écarté après ses tentatives.
            Ce chunk était peut-être le dernier de son job : l'appelant doit conclure ces jobs,
            sans quoi un job dont plus rien ne tourne resterait « en cours » pour toujours.
    """

    requeued: int
    abandoned_jobs: frozenset[str]


@dataclass(frozen=True)
class Finished:
    """Ce qu'a produit la fin d'un chunk, au-delà du chunk lui-même.

    Attributes:
        started_job: Ce chunk est le premier terminé de son job, qui vient de passer en cours.
            C'est le moment d'annoncer la transition : sans événement, une interface
            continuerait d'afficher « en attente » sous une barre qui avance.
    """

    started_job: bool


class QuarantinedItem(Protocol):
    """Ce que la file lit d'un item en quarantaine.

    Un protocole plutôt que le modèle du contrat des types de jobs : la file est la couche du
    bas, elle ne doit rien importer de ce qui s'appuie sur elle.
    """

    @property
    def item_id(self) -> str: ...  # noqa: D102

    @property
    def reason(self) -> str: ...  # noqa: D102

    @property
    def detail(self) -> dict[str, Any] | None: ...  # noqa: D102


async def finish(
    conn: psycopg.AsyncConnection,
    chunk: Chunk,
    produced: int | None = None,
    skipped: int = 0,
    quarantined: Sequence[QuarantinedItem] = (),
) -> Finished | None:
    """Marquer un chunk terminé, consigner son bilan, et avancer la progression de son job.

    Le bilan, la quarantaine et la progression s'écrivent dans une seule transaction : un
    chunk ne peut pas être compté fait sans que ses items écartés soient consignés.

    Args:
        conn: La connexion du chunk.
        chunk: Le chunk réclamé.
        produced: Tâches produites. Par défaut, toutes celles qui ne sont ni écartées ni en
            quarantaine.
        skipped: Tâches sans objet.
        quarantined: Items en échec.

    Returns:
        None si le chunk avait été repris par un autre worker entre-temps ; l'appelant doit
        alors jeter son résultat plutôt que d'écraser celui de son successeur.
    """
    if produced is None:
        produced = chunk.task_count - skipped - len(quarantined)
    async with conn.transaction():
        row = await (await conn.execute(FINISH, (produced, skipped, chunk.id, chunk.attempts))).fetchone()
        if row is None:
            return None
        for item in quarantined:
            await conn.execute(
                QUARANTINE,
                (chunk.job_id, chunk.id, item.item_id, item.reason, Jsonb(item.detail) if item.detail else None),
            )
        advanced = await (await conn.execute(ADVANCE_JOB, {"job": row[0], "tasks": row[1]})).fetchone()
    return Finished(started_job=bool(advanced and advanced[0]))


async def retry_later(
    conn: psycopg.AsyncConnection, chunk: Chunk, error: dict[str, Any], max_attempts: int = MAX_ATTEMPTS
) -> str | None:
    """Rendre à la file, après un délai, un chunk qui a buté sur une panne passagère.

    Returns:
        `pending` s'il sera rejoué, `error` s'il a épuisé ses tentatives, None si le chunk
        ne lui appartenait plus.
    """
    row = await (
        await conn.execute(
            RETRY,
            {
                "max_attempts": max_attempts,
                "base": RETRY_BASE_DELAY,
                "cap": RETRY_MAX_DELAY,
                "error": Jsonb(error),
                "id": chunk.id,
                "attempts": chunk.attempts,
            },
        )
    ).fetchone()
    return row[0] if row is not None else None


async def refresh_lease(conn: psycopg.AsyncConnection, chunk: Chunk) -> bool:
    """Prolonger le bail d'un chunk en cours.

    Returns:
        False si le chunk ne lui appartient plus : son bail a expiré et un autre l'a repris.
    """
    return (await conn.execute(REFRESH_LEASE, (LEASE_TTL, chunk.id, chunk.attempts))).rowcount > 0


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


async def release_own(conn: psycopg.AsyncConnection, worker_id: str, max_attempts: int = MAX_ATTEMPTS) -> Recovery:
    """Rendre les chunks laissés par une exécution précédente de ce même worker.

    Le bail finirait par les libérer de toute façon ; les rendre au démarrage transforme une
    reprise de deux minutes en reprise immédiate. Ceux qui ont épuisé leurs tentatives sont
    écartés, comme par la reprise des baux.
    """
    async with conn.transaction():
        requeued = len(await (await conn.execute(RELEASE_OWN, (worker_id, max_attempts))).fetchall())
        abandoned = await (await conn.execute(ABANDON_OWN, (worker_id, max_attempts))).fetchall()
    return Recovery(requeued=requeued, abandoned_jobs=frozenset(str(row[0]) for row in abandoned))


async def reclaim_expired(conn: psycopg.AsyncConnection, max_attempts: int = MAX_ATTEMPTS) -> Recovery:
    """Remettre en file les chunks dont le bail a expiré, écarter ceux qui s'acharnent."""
    async with conn.transaction():
        requeued = len(await (await conn.execute(RECLAIM_EXPIRED, (max_attempts,))).fetchall())
        abandoned = await (await conn.execute(ABANDON_EXHAUSTED, (max_attempts,))).fetchall()
    return Recovery(requeued=requeued, abandoned_jobs=frozenset(str(row[0]) for row in abandoned))


async def is_cancelled(conn: psycopg.AsyncConnection, job_id: str) -> bool:
    """Une annulation a-t-elle été demandée pour ce job ?"""
    row = await (await conn.execute(IS_CANCELLED, (job_id,))).fetchone()
    return row is not None and bool(row[0])
