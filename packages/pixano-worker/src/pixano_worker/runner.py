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
from typing import Any

import psycopg
from psycopg.types.json import Jsonb

from . import queue
from .kinds import Registry
from .schema import SCHEMA_NAME


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

RECORD_EVENT = f"""
INSERT INTO {SCHEMA_NAME}.job_events (job_id, type, payload) VALUES (%s, %s, %s)
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
    conn.execute(RECORD_EVENT, (job_id, event_type, Jsonb(payload)))


def plan_one(conn: psycopg.Connection, registry: Registry) -> str | None:
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
        chunks = list(kind.plan(dataset_id, params))
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


def run_batch(conn: psycopg.Connection, registry: Registry, worker_id: str, batch_size: int) -> int:
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
        _run_chunk(conn, registry, chunk)

    for job_id in jobs_touched:
        _settle(conn, job_id)
    return len(chunks)


def _run_chunk(conn: psycopg.Connection, registry: Registry, chunk: queue.Chunk) -> None:
    """Exécuter un chunk, et consigner ce qui en résulte."""
    row = conn.execute(f"SELECT kind, params FROM {SCHEMA_NAME}.jobs WHERE id = %s", (chunk.job_id,)).fetchone()
    kind = registry.get(row[0]) if row is not None else None
    if row is None or kind is None:
        queue.fail(conn, chunk, {"reason": "type de job inconnu"})
        return

    try:
        params = kind.validate_params(row[1])
        result = kind.process(chunk.payload, params)
        kind.write(result, chunk.payload, params, chunk.job_id, chunk.seq)
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
