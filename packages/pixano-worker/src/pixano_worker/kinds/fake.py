# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Un type de job qui ne fait rien, lentement.

Il existe pour éprouver le moteur sans dépendre d'un modèle : la réclamation, le bail, la
reprise, l'annulation et la progression se démontrent entièrement avec lui. C'est aussi la
première implémentation des trois contrats, donc celle qui les met à l'épreuve avant que le
lot des contrats gelés ne les fige.
"""

import time
from typing import Any, Iterable

from pydantic import Field

from pixano.schemas.annotations.classification import Classification

from ..reader import JobReader
from ..writer import JobWriter
from .base import Chunk, JobKind, JobParams


class FakeParams(JobParams):
    """Paramètres du job factice.

    Attributes:
        task_count: Nombre de tâches à simuler.
        chunk_size: Tâches par chunk.
        seconds_per_task: Temps passé par tâche, pour observer une progression réaliste.
        fail_at_chunk: Rang d'un chunk qui doit échouer, pour éprouver la remontée d'erreur.
        write_to: Table de jouet où écrire des lignes sans signification, pour éprouver
            l'idempotence des écritures. Vide, le type n'écrit rien.
    """

    task_count: int = Field(default=200, ge=1, le=1_000_000)
    chunk_size: int = Field(default=20, ge=1, le=10_000)
    seconds_per_task: float = Field(default=0.01, ge=0.0, le=60.0)
    fail_at_chunk: int | None = Field(default=None, ge=0)
    write_to: str | None = Field(
        default=None,
        description="Toy table to write meaningless rows into. Leave empty to write nothing.",
    )


class FakeKind(JobKind[FakeParams]):
    """Le type de job factice."""

    name = "fake"
    params_model = FakeParams
    # Aucun modèle ne tourne ici : ce que ce type écrit n'est pas une prédiction.
    source_type = "other"

    def plan(self, reader: JobReader, params: FakeParams) -> Iterable[Chunk]:
        """Découper en chunks de taille fixe. Rien à lire : le compte est dans les paramètres."""
        remaining = params.task_count
        first = 0
        while remaining > 0:
            size = min(params.chunk_size, remaining)
            yield Chunk(payload={"first_task": first, "task_count": size}, task_count=size)
            first += size
            remaining -= size

    def process(self, payload: dict[str, Any], params: FakeParams) -> dict[str, Any]:
        """Dormir le temps annoncé, puis rendre un résultat symbolique.

        Raises:
            RuntimeError: Le rang de ce chunk est celui qu'on a demandé de faire échouer.
        """
        if params.fail_at_chunk is not None and payload.get("first_task") == params.fail_at_chunk * params.chunk_size:
            raise RuntimeError(f"échec demandé au chunk {params.fail_at_chunk}")
        time.sleep(params.seconds_per_task * payload["task_count"])
        return {"processed": payload["task_count"]}

    def write(self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: FakeParams) -> None:
        """Écrire une classification sans signification dans une table de jouet.

        Le nom de la table dit ce qu'elle est. Ce type existe pour éprouver le moteur, et ce
        qu'il produit n'a aucun sens : rien ne doit pouvoir passer pour une annotation réelle,
        ni traîner dans un dataset sans qu'on sache d'où ça vient.
        """
        if not params.write_to:
            return
        first = payload["first_task"]
        rows = [
            Classification(
                id="",
                record_id=f"task-{first + offset}",
                labels=["factice"],
                confidences=[1.0],
                **writer.provenance(),
            )
            for offset in range(payload["task_count"])
        ]
        writer.replace(params.write_to, key=f"chunk-{first}", rows=rows)
