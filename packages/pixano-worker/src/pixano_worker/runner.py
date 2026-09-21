# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""La boucle d'exécution du worker.

Deux travaux, dans cet ordre à chaque tour : découper les jobs qui attendent de l'être, puis
consommer des chunks. La planification passe d'abord parce qu'un job non découpé n'a aucun
chunk à réclamer — sans quoi un worker isolé pourrait dormir devant du travail en attente.

L'annulation se regarde **entre les lots**, jamais au milieu d'un chunk : un chunk est
l'unité atomique, l'interrompre laisserait un travail à moitié fait dont on ne saurait rien.
"""

import logging
import traceback
from functools import lru_cache
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from pixano.datasets import Dataset

from . import queue
from .kinds import Registry
from .media import MediaResolver
from .reader import JobReader
from .schema import NOTIFY_CHANNEL, SCHEMA_NAME
from .writer import JobWriter


log = logging.getLogger("pixano-worker")

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


def record_event(conn: psycopg.Connection, job_id: str, event_type: str, payload: dict[str, Any]) -> None:
    """Consigner un événement de progression.

    Les compteurs y sont **absolus**, jamais des incréments : les identifiants de séquence
    sont attribués avant le commit, donc deux transactions concurrentes peuvent rendre leurs
    événements visibles dans le désordre. Un lecteur qui en saute un doit pouvoir s'en
    remettre au suivant.
    """
    conn.execute(RECORD_EVENT, (job_id, event_type, Jsonb(payload), NOTIFY_CHANNEL))


def plan_one(
    conn: psycopg.Connection,
    registry: Registry,
    library: Path | None = None,
    media: MediaResolver | None = None,
) -> str | None:
    """Découper un job en attente de planification.

    Returns:
        L'identifiant du job découpé, ou None s'il n'y en avait aucun.
    """
    row = conn.execute(CLAIM_PLANNING).fetchone()
    if row is None:
        return None
    job_id, kind_name, dataset_id, raw_params = str(row[0]), row[1], row[2], row[3]

    kind = registry.get(kind_name)
    if kind is None:
        # Aucun worker vivant ne déclare ce type. Le job ne sera jamais exécutable : le dire
        # tout de suite vaut mieux que de le laisser en attente sans explication.
        _fail_job(conn, job_id, {"reason": "type de job inconnu", "kind": kind_name})
        log.warning("job %s : type '%s' inconnu de ce worker", job_id, kind_name)
        return job_id

    try:
        params = kind.validate_params(raw_params)
        chunks = list(kind.plan(_reader_for(library, dataset_id, media), params))
    except Exception as error:
        _fail_job(conn, job_id, {"reason": "la planification a échoué", "detail": str(error)})
        log.exception("job %s : planification impossible", job_id)
        return job_id

    if not chunks:
        _fail_job(conn, job_id, {"reason": "la planification n'a produit aucun travail"})
        return job_id

    total = sum(chunk.task_count for chunk in chunks)
    with conn.transaction():
        conn.execute(
            INSERT_CHUNKS,
            (
                job_id,
                list(range(len(chunks))),
                [Jsonb(chunk.payload) for chunk in chunks],
                [chunk.task_count for chunk in chunks],
            ),
        )
        conn.execute(FINISH_PLANNING, (total, job_id))
        record_event(conn, job_id, "state", {"state": "pending", "total_tasks": total, "chunks": len(chunks)})
    log.info("job %s découpé en %d chunks (%d tâches)", job_id, len(chunks), total)
    return job_id


def _fail_job(conn: psycopg.Connection, job_id: str, error: dict[str, Any]) -> None:
    with conn.transaction():
        conn.execute(FAIL_JOB, (Jsonb(error), job_id))
        record_event(conn, job_id, "state", {"state": "error", **error})


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


def run_batch(
    conn: psycopg.Connection,
    registry: Registry,
    worker_id: str,
    batch_size: int,
    library: Path | None = None,
    media: MediaResolver | None = None,
) -> int:
    """Réclamer un lot de chunks et l'exécuter.

    Returns:
        Le nombre de chunks traités — zéro quand la file est vide.
    """
    chunks = queue.claim(conn, worker_id, batch_size)
    if not chunks:
        return 0

    cancelled = queue.cancelled_jobs(conn, [chunk.job_id for chunk in chunks])
    jobs_touched = set()

    for chunk in chunks:
        jobs_touched.add(chunk.job_id)
        if chunk.job_id in cancelled:
            queue.cancel_chunk(conn, chunk)
            continue
        _run_chunk(conn, registry, chunk, library, media)

    for job_id in jobs_touched:
        _settle(conn, job_id)
    return len(chunks)


def _run_chunk(
    conn: psycopg.Connection,
    registry: Registry,
    chunk: queue.Chunk,
    library: Path | None,
    media: MediaResolver | None,
) -> None:
    """Exécuter un chunk, et consigner ce qui en résulte."""
    row = conn.execute(
        f"SELECT kind, params, dataset FROM {SCHEMA_NAME}.jobs WHERE id = %s", (chunk.job_id,)
    ).fetchone()
    kind = registry.get(row[0]) if row is not None else None
    if row is None or kind is None:
        queue.fail(conn, chunk, {"reason": "type de job inconnu"})
        return

    try:
        params = kind.validate_params(row[1])
        reader = _reader_for(library, row[2], media)
        result = kind.process(reader, chunk.payload, params)
        writer = _writer_for(library, row[2], row[0], chunk.job_id, kind.source_type)
        kind.write(writer, result, chunk.payload, params)
    except Exception as error:
        queue.fail(conn, chunk, {"reason": str(error), "trace": traceback.format_exc(limit=3)})
        log.warning("chunk %s du job %s en échec : %s", chunk.seq, chunk.job_id, error)
        return

    if not queue.finish(conn, chunk):
        # Le bail avait expiré et un autre worker a repris le chunk : son résultat fait foi.
        log.info("chunk %s du job %s repris ailleurs, résultat abandonné", chunk.seq, chunk.job_id)
        return

    row = conn.execute(
        f"SELECT done_tasks, total_tasks FROM {SCHEMA_NAME}.jobs WHERE id = %s", (chunk.job_id,)
    ).fetchone()
    if row is not None:
        record_event(conn, chunk.job_id, "progress", {"done_tasks": row[0], "total_tasks": row[1]})


def _settle(conn: psycopg.Connection, job_id: str) -> None:
    """Conclure un job dont plus rien n'attend ni ne tourne."""
    row = conn.execute(SETTLE, (job_id,)).fetchone()
    if row is not None:
        record_event(conn, job_id, "state", {"state": row[0]})
        log.info("job %s terminé : %s", job_id, row[0])
