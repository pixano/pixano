# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""La boucle d'exécution du worker.

Deux travaux, dans cet ordre à chaque tour : découper les jobs qui attendent de l'être, puis
consommer des chunks. La planification passe d'abord parce qu'un job non découpé n'a aucun
chunk à réclamer — sans quoi un worker isolé pourrait dormir devant du travail en attente.

L'annulation se regarde **avant chaque chunk**, jamais au milieu : un chunk est l'unité
atomique, l'interrompre laisserait un travail à moitié fait dont on ne saurait rien.

La boucle est asynchrone, le code des types de jobs ne l'est pas. `plan`, `process` et `write`
sont des fonctions ordinaires — c'est le contrat publié, et la lecture comme l'écriture
LanceDB sont bloquantes de toute façon. Elles partent donc dans un thread ; la boucle garde
pour elle ce qui gagne à être asynchrone : la base, les délais et le bail.
"""

import asyncio
import logging
import threading
import traceback
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from psycopg_pool import AsyncConnectionPool

from pixano.datasets import Dataset

from . import queue
from .kinds import Outcome, Registry, TransientError
from .media import MediaResolver
from .reader import JobReader
from .schema import NOTIFY_CHANNEL, SCHEMA_NAME
from .writer import JobWriter


log = logging.getLogger("pixano-worker")

# Ce qu'une base injoignable lève : connexion coupée, serveur redémarré, pool sans connexion
# disponible. Rien de ce que fait un type de job — seulement l'accès à la file.
DATABASE_UNAVAILABLE = (psycopg.OperationalError, psycopg.InterfaceError)

# Espacement des tentatives quand la base ne répond plus. Plafonné bas, comme l'écoute côté
# application : un redémarrage de PostgreSQL dure quelques secondes, et un worker qui revient
# vite reprend le travail là où il l'avait laissé.
OUTAGE_BACKOFF_S = (1.0, 2.0, 5.0, 10.0)

# Au-delà de ce délai, la file est réexaminée même sans rien de nouveau à y faire : c'est ce
# qui rend les baux expirés d'un worker mort à un worker occupé, pas seulement à un oisif.
RECLAIM_INTERVAL_S = 30.0

# Les écritures d'un même dataset passent une à une. Plusieurs chunks d'un dataset tournent
# en même temps, et LanceDB n'est pas fait pour des écritures concurrentes sur une même
# table. Le verrou est un verrou de thread : c'est dans un thread que `write` s'exécute.
_write_locks: defaultdict[str, threading.Lock] = defaultdict(threading.Lock)
_write_locks_guard = threading.Lock()


def _write_lock(dataset_id: str) -> threading.Lock:
    with _write_locks_guard:
        return _write_locks[dataset_id]


CLAIM_PLANNING = f"""
UPDATE {SCHEMA_NAME}.jobs SET state = 'running', updated_at = now()
WHERE id = (
    SELECT id FROM {SCHEMA_NAME}.jobs
    WHERE state = 'planning' AND cancel_requested_at IS NULL
    ORDER BY created_at
    FOR UPDATE SKIP LOCKED
    LIMIT 1
)
RETURNING id, kind, dataset, params
"""

INSERT_CHUNKS = f"""
INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, payload, task_count)
SELECT %s, chunk.seq, chunk.payload, chunk.task_count
FROM unnest(%s::int[], %s::jsonb[], %s::int[]) AS chunk(seq, payload, task_count)
"""

FINISH_PLANNING = f"""
UPDATE {SCHEMA_NAME}.jobs
SET state = 'pending', total_tasks = %s, updated_at = now()
WHERE id = %s
"""

FAIL_JOB = f"""
UPDATE {SCHEMA_NAME}.jobs SET state = 'error', error = %s, updated_at = now() WHERE id = %s
"""

# L'insertion et la sonnette dans la même instruction, donc la même transaction : PostgreSQL
# ne délivre un NOTIFY qu'au commit, ce qui donne gratuitement la garantie « pas d'événement
# annoncé avant d'être lisible ». La charge ne porte que des identifiants — elle est plafonnée
# à 8 ko, et un lecteur doit de toute façon relire la ligne pour rattraper ce qu'il a manqué.
RECORD_EVENT = f"""
WITH inserted AS (
    INSERT INTO {SCHEMA_NAME}.job_events (job_id, type, payload)
    VALUES (%s, %s, %s)
    RETURNING id, job_id, type
)
SELECT pg_notify(%s, json_build_object(
    'job_id', job_id, 'event_id', id, 'type', type
)::text) FROM inserted
"""

# Un job dont plus aucun chunk n'attend ni ne tourne est terminé. L'annulation l'emporte sur
# l'erreur : un job qu'on a arrêté n'est pas un job qui a échoué.
SETTLE = f"""
UPDATE {SCHEMA_NAME}.jobs AS j
SET state = CASE
        WHEN j.cancel_requested_at IS NOT NULL THEN 'cancelled'
        WHEN EXISTS (
            SELECT 1 FROM {SCHEMA_NAME}.job_chunks c
            WHERE c.job_id = j.id AND c.state = 'error'
        ) THEN 'error'
        ELSE 'done' END,
    updated_at = now()
WHERE j.id = %s
  AND j.state IN ('planning', 'pending', 'running')
  AND NOT EXISTS (
      SELECT 1 FROM {SCHEMA_NAME}.job_chunks c
      WHERE c.job_id = j.id AND c.state IN ('pending', 'running')
  )
RETURNING j.state
"""


OUTCOME = f"""
SELECT coalesce(sum(produced), 0)::int, coalesce(sum(skipped), 0)::int,
       (SELECT count(*) FROM {SCHEMA_NAME}.job_items WHERE job_id = %s)::int
FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s AND state = 'done'
"""


async def record_event(conn: psycopg.AsyncConnection, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
    """Consigner un événement de progression.

    Les compteurs y sont **absolus**, jamais des incréments : les identifiants de séquence
    sont attribués avant le commit, donc deux transactions concurrentes peuvent rendre leurs
    événements visibles dans le désordre. Un lecteur qui en saute un doit pouvoir s'en
    remettre au suivant.
    """
    await conn.execute(RECORD_EVENT, (job_id, event_type, Jsonb(payload), NOTIFY_CHANNEL))


async def plan_one(
    conn: psycopg.AsyncConnection,
    registry: Registry,
    library: Path | None = None,
    media: MediaResolver | None = None,
) -> str | None:
    """Découper un job en attente de planification.

    Returns:
        L'identifiant du job découpé, ou None s'il n'y en avait aucun.
    """
    row = await (await conn.execute(CLAIM_PLANNING)).fetchone()
    if row is None:
        return None
    job_id, kind_name, dataset_id, raw_params = str(row[0]), row[1], row[2], row[3]

    kind = registry.get(kind_name)
    if kind is None:
        # Aucun worker vivant ne déclare ce type. Le job ne sera jamais exécutable : le dire
        # tout de suite vaut mieux que de le laisser en attente sans explication.
        await _fail_job(conn, job_id, {"reason": "type de job inconnu", "kind": kind_name})
        log.warning("job %s : type '%s' inconnu de ce worker", job_id, kind_name)
        return job_id

    try:
        params = kind.validate_params(raw_params)
        reader = _reader_for(library, dataset_id, media)
        chunks = await asyncio.to_thread(lambda: list(kind.plan(reader, params)))
    except Exception as error:
        await _fail_job(conn, job_id, {"reason": "la planification a échoué", "detail": str(error)})
        log.exception("job %s : planification impossible", job_id)
        return job_id

    if not chunks:
        await _fail_job(conn, job_id, {"reason": "la planification n'a produit aucun travail"})
        return job_id

    total = sum(chunk.task_count for chunk in chunks)
    async with conn.transaction():
        await conn.execute(
            INSERT_CHUNKS,
            (
                job_id,
                list(range(len(chunks))),
                [Jsonb(chunk.payload) for chunk in chunks],
                [chunk.task_count for chunk in chunks],
            ),
        )
        await conn.execute(FINISH_PLANNING, (total, job_id))
        await record_event(conn, job_id, "state", {"state": "pending", "total_tasks": total, "chunks": len(chunks)})
    log.info("job %s découpé en %d chunks (%d tâches)", job_id, len(chunks), total)
    return job_id


async def _fail_job(conn: psycopg.AsyncConnection, job_id: str, error: dict[str, Any]) -> None:
    async with conn.transaction():
        await conn.execute(FAIL_JOB, (Jsonb(error), job_id))
        await record_event(conn, job_id, "state", {"state": "error", **error})


@lru_cache(maxsize=8)
def _open_dataset(library: Path, dataset_id: str) -> Dataset:
    """Ouvrir un dataset, une fois. Le worker en traite peu à la fois."""
    return Dataset.find(dataset_id, library)


def _reader_for(library: Path | None, dataset_id: str, media: MediaResolver | None) -> JobReader:
    """Lier un lecteur au dataset d'un job, ouvert seulement si le type s'en sert."""

    def open_dataset() -> Dataset:
        if library is None:
            raise RuntimeError("aucune bibliothèque de datasets configurée : PIXANO_LIBRARY_DIR est vide")
        return _open_dataset(library, dataset_id)

    return JobReader(open_dataset, media or MediaResolver("/medias", "/medias"))


def _writer_for(library: Path | None, dataset_id: str, kind: str, job_id: str, source_type: str) -> JobWriter:
    """Lier un écrivain au dataset d'un job.

    L'ouverture est différée au premier usage : un type qui n'écrit rien ne doit pas échouer
    faute de dataset, et l'absence de bibliothèque ne se manifeste que si quelqu'un écrit.
    """

    def open_dataset() -> Dataset:
        if library is None:
            raise RuntimeError("aucune bibliothèque de datasets configurée : PIXANO_LIBRARY_DIR est vide")
        return _open_dataset(library, dataset_id)

    return JobWriter(open_dataset, kind, job_id, source_type)


async def work(
    pool: AsyncConnectionPool,
    registry: Registry,
    worker_id: str,
    concurrency: int,
    library: Path | None = None,
    media: MediaResolver | None = None,
    idle_poll_s: float = 5.0,
    chunk_timeout_s: float | None = None,
) -> None:
    """Tenir jusqu'à `concurrency` chunks en vol, indéfiniment.

    La réclamation ne prend jamais plus que les places libres : un chunk réclamé porte un bail
    qui court, et le réclamer pour le laisser attendre une place l'exposerait à expirer avant
    d'avoir commencé.
    """
    in_flight: set[asyncio.Task[None]] = set()
    loop = asyncio.get_running_loop()
    last_reclaim = loop.time()
    outages = 0

    while True:
        # Une base qui redémarre ne doit pas tuer le worker : il attend qu'elle revienne, comme
        # au démarrage. Les chunks en vol ne sont pas touchés — chacun gère sa propre connexion,
        # et un chunk interrompu garde son bail jusqu'à ce que la reprise le rende.
        try:
            async with pool.connection() as conn:
                planned = await plan_one(conn, registry, library, media)

            claimed: list[queue.Chunk] = []
            free = concurrency - len(in_flight)
            if free > 0:
                async with pool.connection() as conn:
                    claimed = await queue.claim(conn, worker_id, free)
            # Lancés sitôt réclamés, avant tout autre accès à la base : un chunk réclamé porte un
            # bail qui court, et une coupure juste après le laisserait sans personne pour le faire.
            for chunk in claimed:
                task = asyncio.create_task(_run_pooled(pool, registry, chunk, library, media, chunk_timeout_s))
                in_flight.add(task)
                task.add_done_callback(in_flight.discard)

            if loop.time() - last_reclaim >= RECLAIM_INTERVAL_S:
                last_reclaim = loop.time()
                async with pool.connection() as conn:
                    reclaimed, abandoned = await queue.reclaim_expired(conn)
                if reclaimed or abandoned:
                    log.info("baux expirés : %d chunk(s) remis en file, %d écarté(s)", reclaimed, abandoned)
        except DATABASE_UNAVAILABLE as error:
            delay = OUTAGE_BACKOFF_S[min(outages, len(OUTAGE_BACKOFF_S) - 1)]
            outages += 1
            log.warning("base injoignable (%s) — nouvel essai dans %ss", error, delay)
            await asyncio.sleep(delay)
            continue
        if outages:
            log.info("base de nouveau joignable après %d tentative(s)", outages)
            outages = 0

        if len(in_flight) >= concurrency:
            await asyncio.wait(in_flight, return_when=asyncio.FIRST_COMPLETED)
        elif planned is None and not claimed:
            # Rien de nouveau : attendre qu'une place se libère ou que du travail arrive.
            if in_flight:
                await asyncio.wait(in_flight, timeout=idle_poll_s, return_when=asyncio.FIRST_COMPLETED)
            else:
                await asyncio.sleep(idle_poll_s)


async def _run_pooled(
    pool: AsyncConnectionPool,
    registry: Registry,
    chunk: queue.Chunk,
    library: Path | None,
    media: MediaResolver | None,
    chunk_timeout_s: float | None,
) -> None:
    """Exécuter un chunk sur sa propre connexion, sans jamais faire tomber la boucle.

    Une panne de base au milieu d'un chunk le laisse en cours avec son bail : l'expiration le
    rendra. Laisser l'exception remonter ne le rendrait pas plus vite, et tuerait en silence
    une tâche que personne n'attend.
    """
    try:
        async with pool.connection() as conn:
            await run_chunk(conn, registry, chunk, library, media, chunk_timeout_s)
    except Exception:
        log.exception("chunk %s du job %s : panne hors du type de job", chunk.seq, chunk.job_id)


async def run_batch(
    conn: psycopg.AsyncConnection,
    registry: Registry,
    worker_id: str,
    batch_size: int,
    library: Path | None = None,
    media: MediaResolver | None = None,
) -> int:
    """Réclamer un lot de chunks et les exécuter l'un après l'autre sur une connexion.

    La forme séquentielle de `work`, sans pool ni tâches : c'est elle que les tests pilotent,
    parce qu'elle rend l'ordre des événements déterministe.

    Returns:
        Le nombre de chunks traités — zéro quand la file est vide.
    """
    chunks = await queue.claim(conn, worker_id, batch_size)
    for chunk in chunks:
        await run_chunk(conn, registry, chunk, library, media)
    return len(chunks)


async def run_chunk(
    conn: psycopg.AsyncConnection,
    registry: Registry,
    chunk: queue.Chunk,
    library: Path | None = None,
    media: MediaResolver | None = None,
    timeout_s: float | None = None,
) -> None:
    """Exécuter un chunk réclamé, consigner ce qui en résulte, et conclure son job s'il y a lieu.

    Args:
        conn: La connexion propre à ce chunk.
        registry: Les types de jobs connus.
        chunk: Le chunk réclamé.
        library: La bibliothèque de datasets.
        media: Le résolveur de médias.
        timeout_s: Durée maximale du chunk. Au-delà, il est rendu à la file comme après une
            panne passagère. None : pas de limite.
    """
    await _execute(conn, registry, chunk, library, media, timeout_s)
    await _settle(conn, chunk.job_id)


async def _execute(
    conn: psycopg.AsyncConnection,
    registry: Registry,
    chunk: queue.Chunk,
    library: Path | None,
    media: MediaResolver | None,
    timeout_s: float | None,
) -> None:
    if await queue.is_cancelled(conn, chunk.job_id):
        await queue.cancel_chunk(conn, chunk)
        return

    row = await (
        await conn.execute(f"SELECT kind, params, dataset FROM {SCHEMA_NAME}.jobs WHERE id = %s", (chunk.job_id,))
    ).fetchone()
    kind = registry.get(row[0]) if row is not None else None
    if row is None or kind is None:
        await queue.fail(conn, chunk, {"reason": "type de job inconnu"})
        return
    kind_name, raw_params, dataset_id = row

    def work() -> Outcome:
        params = kind.validate_params(raw_params)
        result = kind.process(_reader_for(library, dataset_id, media), chunk.payload, params)
        outcome = kind.outcome(result, chunk.payload, chunk.task_count)
        if outcome.total != chunk.task_count:
            # Un bilan faux fausserait tout ce qu'on affiche du job ; mieux vaut un chunk en échec
            # qui désigne le défaut du type qu'un compte qui ment sans bruit.
            raise ValueError(
                f"le bilan du type « {kind_name} » couvre {outcome.total} tâche(s), "
                f"le chunk en compte {chunk.task_count}"
            )
        with _write_lock(dataset_id):
            kind.write(
                _writer_for(library, dataset_id, kind_name, chunk.job_id, kind.source_type),
                result,
                chunk.payload,
                params,
            )
        return outcome

    try:
        async with _lease_kept(conn, chunk):
            outcome = await asyncio.wait_for(asyncio.to_thread(work), timeout_s)
    except TimeoutError:
        # Le thread ne s'arrête pas : un appel bloqué ne s'interrompt pas de l'extérieur. Le
        # chunk est rendu, et si le thread finit par aboutir, son résultat sera refusé par le
        # jeton de garde — et son écriture, idempotente, n'aura rien doublé.
        await _retry_later(conn, chunk, {"reason": "durée maximale dépassée", "timeout_s": timeout_s})
        return
    except TransientError as error:
        await _retry_later(conn, chunk, {"reason": "panne passagère", "detail": str(error)})
        return
    except Exception as error:
        await queue.fail(conn, chunk, {"reason": str(error), "trace": traceback.format_exc(limit=3)})
        log.warning("chunk %s du job %s en échec : %s", chunk.seq, chunk.job_id, error)
        return

    finished = await queue.finish(
        conn, chunk, produced=outcome.produced, skipped=outcome.skipped, quarantined=outcome.quarantined
    )
    if finished is None:
        # Le bail avait expiré et un autre worker a repris le chunk : son résultat fait foi.
        log.info("chunk %s du job %s repris ailleurs, résultat abandonné", chunk.seq, chunk.job_id)
        return
    if finished.started_job:
        await record_event(conn, chunk.job_id, "state", {"state": "running"})
    if outcome.quarantined:
        log.info("chunk %s du job %s : %d item(s) en quarantaine", chunk.seq, chunk.job_id, len(outcome.quarantined))

    progress = await (
        await conn.execute(f"SELECT done_tasks, total_tasks FROM {SCHEMA_NAME}.jobs WHERE id = %s", (chunk.job_id,))
    ).fetchone()
    if progress is not None:
        await record_event(conn, chunk.job_id, "progress", {"done_tasks": progress[0], "total_tasks": progress[1]})


async def _retry_later(conn: psycopg.AsyncConnection, chunk: queue.Chunk, error: dict[str, Any]) -> None:
    state = await queue.retry_later(conn, chunk, error)
    if state == "pending":
        log.info(
            "chunk %s du job %s rendu à la file (%s), tentative %d",
            chunk.seq,
            chunk.job_id,
            error["reason"],
            chunk.attempts,
        )
    elif state == "error":
        log.warning(
            "chunk %s du job %s écarté après %d tentatives : %s",
            chunk.seq,
            chunk.job_id,
            chunk.attempts,
            error["reason"],
        )


@asynccontextmanager
async def _lease_kept(conn: psycopg.AsyncConnection, chunk: queue.Chunk) -> AsyncIterator[None]:
    """Prolonger le bail du chunk tant que le bloc s'exécute.

    Le rafraîchissement s'arrête par un signal, pas par une annulation : annuler une tâche au
    milieu d'une requête peut laisser la connexion dans un état inutilisable, et c'est la
    connexion que le chunk réutilise juste après.
    """
    stop = asyncio.Event()

    async def keep() -> None:
        interval = queue.LEASE_REFRESH_INTERVAL.total_seconds()
        while not stop.is_set():
            try:
                await asyncio.wait_for(stop.wait(), interval)
            except TimeoutError:
                if not await queue.refresh_lease(conn, chunk):
                    log.warning("chunk %s du job %s : bail perdu en cours d'exécution", chunk.seq, chunk.job_id)
                    return

    keeper = asyncio.create_task(keep())
    try:
        yield
    finally:
        stop.set()
        await keeper


async def _settle(conn: psycopg.AsyncConnection, job_id: str) -> None:
    """Conclure un job dont plus rien n'attend ni ne tourne, en disant ce qu'il a produit."""
    row = await (await conn.execute(SETTLE, (job_id,))).fetchone()
    if row is None:
        return
    outcome = await job_outcome(conn, job_id)
    await record_event(conn, job_id, "state", {"state": row[0], **outcome})
    log.info(
        "job %s terminé : %s — %d produite(s), %d écartée(s), %d en quarantaine",
        job_id,
        row[0],
        outcome["produced"],
        outcome["skipped"],
        outcome["quarantined"],
    )


async def job_outcome(conn: psycopg.AsyncConnection, job_id: str) -> dict[str, int]:
    """Le bilan d'un job, agrégé depuis ses chunks et sa quarantaine.

    Agrégé à la lecture plutôt que tenu en compteurs sur le job : c'est un compte de plus qui
    ne pourrait pas dériver de ce qu'il résume.
    """
    row = await (await conn.execute(OUTCOME, (job_id, job_id))).fetchone()
    assert row is not None
    return {"produced": row[0], "skipped": row[1], "quarantined": row[2]}
