# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Recording a job request on the queue.

The application records the request; the worker plans and executes it. Splitting work is
kind-specific logic — by video, by image, by selection — and kind code only ever runs in the
worker, so a job is written here without chunks, in state `planning`, and the worker expands
it. What the application does own is refusing a request that cannot succeed: an unknown kind,
or parameters that do not fit the kind's declared schema.

The worker owns the schema: this module never creates anything. On a database where the
worker has never run, the tables are simply absent and callers get `QueueUnavailableError`.
"""

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Sequence

import jsonschema
import psycopg
from psycopg.types.json import Jsonb

from . import queries


DEFAULT_LISTED_JOBS = 50


class QueueUnavailableError(RuntimeError):
    """La file n'existe pas : le worker, qui possède le schéma, n'a jamais démarré."""


class JobNotFoundError(LookupError):
    """Aucun job ne porte cet identifiant."""


class UnknownKindError(ValueError):
    """Aucun worker n'a déclaré savoir exécuter ce type de job."""


class InvalidParamsError(ValueError):
    """Les paramètres ne respectent pas le schéma déclaré par le type."""


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
    produced: int = 0
    skipped: int = 0
    quarantined: int = 0
    cancel_requested: bool = False
    error: dict[str, Any] | None = None

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
            produced=row[7],
            skipped=row[8],
            quarantined=row[9],
            cancel_requested=row[10],
            error=row[11],
        )


@dataclass(frozen=True)
class QuarantinedItem:
    """Un item qu'un job n'a pas su traiter, et pourquoi."""

    item_id: str
    reason: str
    detail: dict[str, Any] | None
    created_at: datetime


def connect(database_url: str | None) -> psycopg.Connection:
    """Ouvrir une connexion sur la file, ou refuser clairement.

    Raises:
        QueueUnavailableError: Aucune URL n'est configurée, ou la base est injoignable.
    """
    if not database_url:
        raise QueueUnavailableError("no job queue is configured — set PIXANO_DATABASE_URL and start pixano-worker")
    try:
        return psycopg.connect(database_url)
    except psycopg.Error as error:
        raise QueueUnavailableError(f"the job queue is unreachable: {error}") from error


def _require_queue(conn: psycopg.Connection) -> None:
    """Vérifier que le worker a déjà installé le schéma."""
    row = conn.execute(queries.QUEUE_EXISTS).fetchone()
    if row is None or row[0] is None:
        raise QueueUnavailableError("the job queue does not exist yet — start pixano-worker, which installs it")


def available_kinds(conn: psycopg.Connection) -> dict[str, dict[str, Any]]:
    """Les types de jobs qu'un worker a déclaré savoir exécuter, et leurs schémas."""
    _require_queue(conn)
    return {row[0]: row[1] for row in conn.execute(queries.LIST_KINDS).fetchall()}


def check_params(conn: psycopg.Connection, kind: str, params: dict[str, Any]) -> None:
    """Refuser une demande qu'aucun worker ne saurait exécuter.

    Valider ici épargne à l'utilisateur un job qui part en file pour échouer ensuite, et
    épargne au worker de découvrir une erreur de saisie au moment de planifier.

    Raises:
        UnknownKindError: Aucun worker ne déclare ce type.
        InvalidParamsError: Les paramètres ne respectent pas le schéma déclaré.
    """
    _require_queue(conn)
    row = conn.execute(queries.SELECT_KIND, (kind,)).fetchone()
    if row is None:
        declared = sorted(available_kinds(conn))
        known = ", ".join(declared) if declared else "none"
        raise UnknownKindError(f"no worker has declared the job kind '{kind}' — declared kinds: {known}")

    try:
        jsonschema.validate(params, row[0])
    except jsonschema.ValidationError as error:
        raise InvalidParamsError(f"invalid parameters for '{kind}': {error.message}") from error


def submit(
    conn: psycopg.Connection,
    *,
    kind: str,
    dataset_id: str,
    params: dict[str, Any] | None = None,
) -> JobRecord:
    """Enregistrer une demande de job, à charge du worker de la découper.

    Raises:
        QueueUnavailableError: Le schéma n'est pas installé.
        UnknownKindError: Aucun worker ne déclare ce type.
        InvalidParamsError: Les paramètres ne respectent pas le schéma déclaré.
    """
    params = params or {}
    check_params(conn, kind, params)
    with conn.transaction():
        row = conn.execute(queries.INSERT_JOB, (kind, dataset_id, Jsonb(params))).fetchone()
        if row is None:  # pragma: no cover - RETURNING garantit une ligne
            raise RuntimeError("l'insertion du job n'a rien renvoyé")
    return JobRecord.from_row(row)


def get(conn: psycopg.Connection, job_id: str) -> JobRecord:
    """Lire un job.

    Raises:
        JobNotFoundError: Aucun job ne porte cet identifiant.
    """
    _require_queue(conn)
    try:
        uuid.UUID(job_id)
    except ValueError as error:
        # Le schéma type l'identifiant en uuid : une chaîne d'une autre forme faisait échouer
        # la requête, donc répondre 500 pour ce qui est un job inconnu.
        raise JobNotFoundError(job_id) from error
    row = conn.execute(queries.SELECT_JOB, (job_id,)).fetchone()
    if row is None:
        raise JobNotFoundError(job_id)
    return JobRecord.from_row(row)


def list_jobs(conn: psycopg.Connection, limit: int = DEFAULT_LISTED_JOBS) -> list[JobRecord]:
    """Lister les jobs, du plus récent au plus ancien."""
    _require_queue(conn)
    return [JobRecord.from_row(row) for row in conn.execute(queries.LIST_JOBS, (limit,)).fetchall()]


def quarantine(conn: psycopg.Connection, job_id: str, limit: int) -> list[QuarantinedItem]:
    """Les items qu'un job a mis en quarantaine.

    Raises:
        JobNotFoundError: Aucun job ne porte cet identifiant.
    """
    job = get(conn, job_id)
    rows = conn.execute(queries.LIST_QUARANTINE, (job.id, limit)).fetchall()
    return [QuarantinedItem(item_id=r[0], reason=r[1], detail=r[2], created_at=r[3]) for r in rows]


def cancel(conn: psycopg.Connection, job_id: str) -> JobRecord:
    """Demander l'annulation d'un job.

    Les chunks en attente sortent de la file immédiatement ; ceux qui tournent sont laissés
    à leur worker, qui s'arrêtera avant le chunk suivant. Un job dont plus rien ne tourne devient
    terminal tout de suite.

    L'annulation est annoncée sur le flux d'événements, dans la même transaction : c'est le
    seul changement d'état que l'application fait elle-même, et sans événement les autres
    clients gardaient un job « en cours » jusqu'à un rechargement. L'événement porte l'état
    du job après l'annulation — conclu, ou encore en cours le temps que ses chunks finissent —
    et le drapeau de demande.

    Raises:
        JobNotFoundError: Aucun job ne porte cet identifiant.
    """
    with conn.transaction():
        job = get(conn, job_id)
        requested = conn.execute(queries.REQUEST_CANCEL, (job.id,)).rowcount
        conn.execute(queries.CANCEL_PENDING_CHUNKS, (job.id,))
        settled = conn.execute(queries.SETTLE_IF_IDLE, (job.id, job.id)).fetchone()
        if requested:
            # Conclu sur-le-champ, ou encore dans l'état d'avant : l'annulation ne le change pas.
            payload = {"state": settled[0] if settled else job.state, "cancel_requested": True}
            conn.execute(queries.RECORD_EVENT, (job.id, "state", Jsonb(payload), queries.NOTIFY_CHANNEL))
    return get(conn, job_id)
