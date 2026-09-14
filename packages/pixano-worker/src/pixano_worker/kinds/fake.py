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

from pydantic import BaseModel, Field

from .base import Chunk, JobKind


class FakeParams(BaseModel):
    """Paramètres du job factice.

    Attributes:
        task_count: Nombre de tâches à simuler.
        chunk_size: Tâches par chunk.
        seconds_per_task: Temps passé par tâche, pour observer une progression réaliste.
        fail_at_chunk: Rang d'un chunk qui doit échouer, pour éprouver la remontée d'erreur.
    """

    task_count: int = Field(default=200, ge=1, le=1_000_000)
    chunk_size: int = Field(default=20, ge=1, le=10_000)
    seconds_per_task: float = Field(default=0.01, ge=0.0, le=60.0)
    fail_at_chunk: int | None = Field(default=None, ge=0)


class FakeKind(JobKind[FakeParams]):
    """Le type de job factice."""

    name = "fake"
    params_model = FakeParams

    def plan(self, dataset_id: str, params: FakeParams) -> Iterable[Chunk]:
        """Découper en chunks de taille fixe."""
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

    def write(
        self, result: dict[str, Any], payload: dict[str, Any], params: FakeParams, job_id: str, seq: int
    ) -> None:
        """N'écrire nulle part — il n'y a rien à produire."""
