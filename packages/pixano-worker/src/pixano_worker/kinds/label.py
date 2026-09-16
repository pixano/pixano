# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Un type de job qui pose la même étiquette sur une sélection d'enregistrements.

Il existe pour une raison précise : prouver qu'ajouter un type de job ne demande aucune
modification du moteur. Sa forme diffère délibérément de celle du type factice — ses
paramètres portent une liste et une valeur obligatoire, son découpage suit une sélection
donnée plutôt qu'un compte, et il écrit une ligne par tâche plutôt qu'un lot par chunk.

Si le moteur avait la moindre connaissance de ce que fait un type, l'un des deux casserait.
"""

from typing import Any, Iterable

from pydantic import Field

from pixano.schemas.annotations.classification import Classification

from ..reader import JobReader
from ..writer import JobWriter
from .base import Chunk, JobKind, JobParams


class LabelParams(JobParams):
    """Paramètres de l'étiquetage.

    Attributes:
        record_ids: Les enregistrements à étiqueter. Une sélection, pas un compte : c'est la
            forme que prend le cas le plus courant, « traite ce que j'ai coché ».
        label: L'étiquette à poser. Obligatoire, pour éprouver le refus d'un paramètre
            manquant à la soumission.
        chunk_size: Enregistrements par chunk.
        write_to: Table où écrire. Vide, le type n'écrit rien.
    """

    record_ids: list[str] = Field(default_factory=list)
    label: str = Field(min_length=1)
    chunk_size: int = Field(default=32, ge=1, le=10_000)
    write_to: str | None = None


class LabelKind(JobKind[LabelParams]):
    """Pose une étiquette sur chaque enregistrement d'une sélection."""

    name = "label"
    params_model = LabelParams
    # Une étiquette posée par une règle n'est pas une prédiction de modèle.
    source_type = "other"

    def plan(self, reader: JobReader, params: LabelParams) -> Iterable[Chunk]:
        """Découper la sélection en chunks. Rien à lire : la sélection est donnée."""
        ids = params.record_ids
        for start in range(0, len(ids), params.chunk_size):
            batch = ids[start : start + params.chunk_size]
            yield Chunk(payload={"record_ids": batch}, task_count=len(batch))

    def process(self, payload: dict[str, Any], params: LabelParams) -> dict[str, Any]:
        """Il n'y a rien à calculer : l'étiquette est dans les paramètres."""
        return {"label": params.label, "record_ids": payload["record_ids"]}

    def write(self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: LabelParams) -> None:
        """Écrire une classification par enregistrement.

        Une clé par enregistrement, contrairement au type factice qui en emploie une par
        chunk : ré-étiqueter un seul enregistrement ne doit pas dépendre du découpage qui
        l'avait traité la première fois.
        """
        if not params.write_to:
            return
        for record_id in result["record_ids"]:
            row = Classification(
                id="",
                record_id=record_id,
                labels=[result["label"]],
                confidences=[1.0],
                **writer.provenance(),
            )
            writer.replace(params.write_to, key=record_id, rows=[row])
