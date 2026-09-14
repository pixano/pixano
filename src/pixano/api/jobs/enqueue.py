# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Planning a job and putting it on the queue.

The application plans and inserts; the worker consumes. Planning belongs here because the
user needs an answer straight away — "accepted, 12 340 images" — which means counting now,
and because this process already has the dataset open. `Dataset.count_rows_where` uses
LanceDB's native count, so planning costs no table materialization.

The worker owns the schema: this module never creates anything. On a database where the
worker has never run, the tables are simply absent and callers get `QueueUnavailableError`.
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterator, Sequence

import psycopg
from psycopg.types.json import Jsonb

from pixano.datasets import Dataset
from pixano.schemas.schema_group import SchemaGroup

from . import queries


# Un chunk porte assez de tâches pour amortir un aller-retour en base, sans être si gros
# qu'une reprise après coupure refasse un travail considérable.
DEFAULT_CHUNK_SIZE = 64

MAX_LISTED_JOBS = 50


class QueueUnavailableError(RuntimeError):
    """La file n'existe pas : le worker, qui possède le schéma, n'a jamais démarré."""


class JobNotFoundError(LookupError):
    """Aucun job ne porte cet identifiant."""


@dataclass(frozen=True)
class JobRecord:
    """Un job tel que l'interface le voit."""

    id: str
    kind: str
    dataset: str
    state: str
    total_tasks: int
    done_tasks: int
    created_at: datetime

    @classmethod
    def from_row(cls, row: Sequence[Any]) -> "JobRecord":
        """Construire depuis une ligne de la projection commune des requêtes."""
        return cls(
            id=str(row[0]),
            kind=row[1],
            dataset=row[2],
            state=row[3],
            total_tasks=row[4],
            done_tasks=row[5],
            created_at=row[6],
        )


def connect(database_url: str | None) -> psycopg.Connection:
    """Ouvrir une connexion sur la file, ou refuser clairement.

    Raises:
        QueueUnavailableError: Aucune URL n'est configurée, ou la base est injoignable.
    """
    if not database_url:
        raise QueueUnavailableError(
            "aucune file de jobs configurée — définissez PIXANO_DATABASE_URL et démarrez pixano-worker"
        )
    try:
        return psycopg.connect(database_url)
    except psycopg.Error as error:
        raise QueueUnavailableError(f"file de jobs injoignable : {error}") from error


def _require_queue(conn: psycopg.Connection) -> None:
    """Vérifier que le worker a déjà installé le schéma."""
    row = conn.execute(queries.QUEUE_EXISTS).fetchone()
    if row is None or row[0] is None:
        raise QueueUnavailableError(
            "la file de jobs n'existe pas encore — démarrez pixano-worker, qui installe le schéma"
        )


def plan_chunks(
    item_ids: Sequence[str], chunk_size: int = DEFAULT_CHUNK_SIZE
) -> Iterator[tuple[int, dict[str, Any], int]]:
    """Découper une sélection d'items en chunks numérotés.

    Le payload reste opaque pour le moteur : il porte les identifiants d'items, que le type
    de job saura lire. Un découpage par plages serait plus compact, mais l'ordre des lignes
    LanceDB n'est pas un contrat — une plage calculée à la soumission ne désignerait pas
    forcément les mêmes lignes à l'exécution.

    Args:
        item_ids: Les items à traiter, dans l'ordre voulu.
        chunk_size: Nombre de tâches par chunk.

    Yields:
        Le rang du chunk, son payload, et son nombre de tâches.
    """
    if chunk_size < 1:
        raise ValueError("chunk_size doit valoir au moins 1")
    for seq, start in enumerate(range(0, len(item_ids), chunk_size)):
        batch = list(item_ids[start : start + chunk_size])
        yield seq, {"item_ids": batch}, len(batch)


def select_record_ids(dataset: Dataset, where: str | None = None) -> list[str]:
    """Lister les enregistrements d'un dataset, éventuellement filtrés.

    Le comptage passe par le `count_rows` natif de LanceDB, qui ne matérialise pas la table ;
    c'est ce qui rend la planification assez peu coûteuse pour tenir dans une requête HTTP.
    """
    table = SchemaGroup.RECORD.value
    total = dataset.count_rows_where(table, where)
    records = dataset.get_data(table_name=table, limit=total, where=where)
    return [record.id for record in records]


def enqueue(
    conn: psycopg.Connection,
    *,
    kind: str,
    dataset_id: str,
    item_ids: Sequence[str],
    params: dict[str, Any] | None = None,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> JobRecord:
    """Créer un job et mettre tous ses chunks en file, dans une seule transaction.

    L'atomicité n'est pas un détail : un worker ne doit jamais pouvoir observer un job sans
    son travail, sinon il le conclurait terminé avant qu'il ait commencé.

    Raises:
        QueueUnavailableError: Le schéma n'est pas installé.
        ValueError: La sélection est vide.
    """
    if not item_ids:
        raise ValueError("un job sans aucun item n'a rien à exécuter")

    chunks = list(plan_chunks(item_ids, chunk_size))

    with conn.transaction():
        _require_queue(conn)
        row = conn.execute(queries.INSERT_JOB, (kind, dataset_id, Jsonb(params or {}), len(item_ids))).fetchone()
        if row is None:  # pragma: no cover - RETURNING garantit une ligne
            raise RuntimeError("l'insertion du job n'a rien renvoyé")
        job = JobRecord.from_row(row)

        conn.execute(
            queries.INSERT_CHUNKS,
            (
                job.id,
                [seq for seq, _, _ in chunks],
                [Jsonb(payload) for _, payload, _ in chunks],
                [count for _, _, count in chunks],
            ),
        )
    return job


def get(conn: psycopg.Connection, job_id: str) -> JobRecord:
    """Lire un job.

    Raises:
        JobNotFoundError: Aucun job ne porte cet identifiant.
    """
    _require_queue(conn)
    row = conn.execute(queries.SELECT_JOB, (job_id,)).fetchone()
    if row is None:
        raise JobNotFoundError(job_id)
    return JobRecord.from_row(row)


def list_jobs(conn: psycopg.Connection, limit: int = MAX_LISTED_JOBS) -> list[JobRecord]:
    """Lister les jobs, du plus récent au plus ancien."""
    _require_queue(conn)
    return [JobRecord.from_row(row) for row in conn.execute(queries.LIST_JOBS, (limit,)).fetchall()]


def cancel(conn: psycopg.Connection, job_id: str) -> JobRecord:
    """Demander l'annulation d'un job.

    Les chunks en attente sortent de la file immédiatement ; ceux qui tournent sont laissés
    à leur worker, qui les rendra entre deux lots. Un job dont plus rien ne tourne devient
    terminal tout de suite.

    Raises:
        JobNotFoundError: Aucun job ne porte cet identifiant.
    """
    with conn.transaction():
        job = get(conn, job_id)
        conn.execute(queries.REQUEST_CANCEL, (job.id,))
        conn.execute(queries.CANCEL_PENDING_CHUNKS, (job.id,))
        conn.execute(queries.SETTLE_IF_IDLE, (job.id, job.id))
    return get(conn, job_id)
