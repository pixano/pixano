# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Le point d'écriture unique des résultats de jobs.

Toute écriture d'un type de job passe par ici, pour deux raisons.

**L'idempotence.** Les résultats vont dans LanceDB tandis que l'avancement va dans PostgreSQL
— deux magasins, donc deux écritures qui ne peuvent pas partager une transaction. Un worker
qui meurt entre les deux refera le chunk, et un chunk dont le bail a expiré peut être repris
par un autre worker. Rejouer doit donc produire exactement le même contenu, jamais des
doublons. Les identifiants sont pour cela dérivés **du travail**, pas de son exécution : deux
exécutions du même traitement sur le même item écrivent sur les mêmes lignes.

**L'écrivain unique, plus tard.** LanceDB n'a pas la gestion de concurrence de PostgreSQL, et
coordonner plusieurs workers écrivant le même dataset est un sujet ouvert. Que toutes les
écritures passent par un seul endroit est ce qui rendra cette coordination possible sans
toucher au moindre type de job.
"""

import hashlib
import json
import logging
from typing import Any, Callable, Iterable, Sequence

from pixano.datasets import Dataset


logger = logging.getLogger("pixano-worker")

# Longueur des identifiants dérivés. Assez pour qu'une collision soit hors de portée, assez
# court pour rester lisible dans une table.
_ID_LENGTH = 22

# Nombre de rangs sondés au-delà de la sortie courante quand on nettoie. Une sortie qui
# rétrécit le fait de quelques lignes, pas de cent ; au-delà, des restes subsistent, ce qui
# vaut mieux que balayer la table à chaque écriture.
_LEFTOVER_PROBE = 32


def derive_id(kind: str, key: str, index: int = 0) -> str:
    """Construire un identifiant stable pour une sortie.

    L'identité vient du **travail** — quel traitement, sur quoi, quelle sortie — et non de
    l'exécution qui l'a produit. C'est ce qui fait qu'un job relancé remplace ses résultats au
    lieu de les dupliquer : un identifiant qui porterait le job produirait des lignes neuves
    à chaque soumission.

    Args:
        kind: Le type de job, pour que deux traitements ne se marchent pas dessus.
        key: Ce sur quoi porte la sortie — l'identifiant d'un item, en général.
        index: Le rang de la sortie quand il y en a plusieurs pour une même clé.

    Returns:
        Un identifiant déterministe.
    """
    digest = hashlib.blake2b(f"{kind}\x00{key}\x00{index}".encode(), digest_size=16).hexdigest()
    return digest[:_ID_LENGTH]


class JobWriter:
    """Écrit les sorties d'un job dans un dataset, de façon rejouable.

    Attributes:
        dataset: Le dataset visé.
        kind: Le type de job qui écrit, pour dériver les identifiants.
        job_id: Le job, conservé comme provenance.
    """

    def __init__(self, open_dataset: Callable[[], Dataset], kind: str, job_id: str) -> None:
        """Lier un écrivain à un job et à son dataset.

        Le dataset est ouvert au premier usage, pas à la construction : un type de job qui
        n'écrit rien ne doit pas exiger qu'un dataset existe, et le runner construit un
        écrivain pour chaque chunk sans savoir si celui-ci s'en servira.
        """
        self._open_dataset = open_dataset
        self._dataset: Dataset | None = None
        self.kind = kind
        self.job_id = job_id

    @property
    def dataset(self) -> Dataset:
        """Le dataset visé, ouvert à la demande."""
        if self._dataset is None:
            self._dataset = self._open_dataset()
        return self._dataset

    def provenance(self) -> dict[str, str]:
        """De quoi tracer une sortie jusqu'au traitement qui l'a produite.

        Les schémas d'annotation portent `source_type`, `source_name` et `source_metadata` ;
        les remplir ici plutôt que dans chaque type de job garantit qu'aucune sortie de job
        n'atterrit dans un dataset sans qu'on sache d'où elle vient.
        """
        return {
            "source_type": "job",
            "source_name": self.kind,
            "source_metadata": json.dumps({"job_id": self.job_id}),
        }

    def ids_for(self, key: str, count: int) -> list[str]:
        """Les identifiants qu'une clé occupera pour `count` sorties."""
        return [derive_id(self.kind, key, index) for index in range(count)]

    def replace(self, table_name: str, key: str, rows: Sequence[Any]) -> list[str]:
        """Écrire les sorties d'une clé, en remplaçant intégralement les précédentes.

        Deux opérations, et les deux sont nécessaires : les lignes sont écrites en upsert sur
        leur identifiant dérivé, puis **les lignes surnuméraires d'une exécution précédente
        sont supprimées**. Sans cette seconde étape, un rejeu qui produirait moins de sorties
        qu'avant — un modèle qui détecte deux objets là où il en voyait cinq — laisserait
        trois lignes orphelines que rien ne viendrait jamais nettoyer.

        Args:
            table_name: La table visée.
            key: Ce sur quoi portent ces sorties, typiquement un identifiant d'item.
            rows: Les lignes à écrire. Leur champ `id` est réécrit.

        Returns:
            Les identifiants écrits.
        """
        written = self.ids_for(key, len(rows))
        for row, row_id in zip(rows, written):
            row.id = row_id

        if rows:
            self.dataset.update_data(table_name, list(rows))

        self._drop_leftovers(table_name, key, kept=len(rows))
        return written

    def _drop_leftovers(self, table_name: str, key: str, kept: int) -> None:
        """Effacer ce qu'une exécution précédente avait écrit au-delà de `kept`.

        Les identifiants étant dérivés d'une suite d'index, les survivants d'un rejeu plus
        court sont exactement les rangs suivants. On en sonde un nombre borné : au-delà, une
        sortie qui aurait rétréci de plus de `_LEFTOVER_PROBE` lignes laisserait des restes,
        ce qui est préférable à balayer la table à chaque écriture.
        """
        candidates = [derive_id(self.kind, key, index) for index in range(kept, kept + _LEFTOVER_PROBE)]
        existing = self._existing(table_name, candidates)
        if existing:
            self.dataset.delete_data(table_name, existing)
            logger.debug("job %s : %d ligne(s) obsolète(s) retirée(s) pour %s", self.job_id, len(existing), key)

    def _existing(self, table_name: str, ids: Iterable[str]) -> list[str]:
        """Parmi ces identifiants, ceux qui sont réellement dans la table."""
        wanted = list(ids)
        if not wanted:
            return []
        found = self.dataset.get_data(table_name, ids=wanted)
        return [row.id for row in found]
