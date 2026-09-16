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
from typing import Any, Callable, Iterable, Protocol, Sequence


logger = logging.getLogger("pixano-worker")

# Longueur des identifiants dérivés. Assez pour qu'une collision soit hors de portée, assez
# court pour rester lisible dans une table.
_ID_LENGTH = 22

# Nombre de rangs sondés au-delà de la sortie courante quand on nettoie. Une sortie qui
# rétrécit le fait de quelques lignes, pas de cent ; au-delà, des restes subsistent, ce qui
# vaut mieux que balayer la table à chaque écriture.
_LEFTOVER_PROBE = 32


class DatasetReadSource(Protocol):
    """Les seules opérations dont la planification d'un job a besoin.

    Un type de job doit pouvoir énumérer ce qu'il va traiter sans ouvrir un dataset lui-même :
    c'est la même raison que pour l'écriture — un point unique, pour que sérialiser ou mettre
    en cache les accès reste un jour une modification d'un seul fichier.
    """

    def count_rows_where(self, table_name: str, where: str | None = None) -> int:
        """Compter les lignes d'une table, sans la matérialiser."""
        ...

    # Les paramètres reprennent ceux de `Dataset` un à un, noms compris. Un `**kwargs` ici
    # exigerait d'un dataset qu'il accepte n'importe quel argument nommé, ce que le vrai ne fait
    # pas : le protocole ne décrivait plus la classe qu'il abstrait, et seul mypy lancé sur tout
    # le dépôt s'en apercevait.
    def get_data(
        self,
        table_name: str,
        ids: list[str] | None = None,
        limit: int | None = None,
        skip: int = 0,
        where: str | None = None,
        record_ids: list[str] | None = None,
    ) -> list[Any]:
        """Lire des lignes d'une table."""
        ...

    def get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str] | None:
        """Les octets d'une vue embarquée, et leur type."""
        ...


class DatasetWriteTarget(Protocol):
    """Les seules opérations dont l'écriture d'un job a besoin.

    Dépendre de ce contrat plutôt que de `Dataset` suit la règle du projet — les frontières
    dépendent d'interfaces — et permet à un test de fournir une doublure qui se comporte comme
    LanceDB sans avoir à feindre d'être un dataset complet.
    """

    def update_data(self, table_name: str, data: list[Any]) -> Any:
        """Écrire des lignes, en remplaçant celles qui portent déjà leur identifiant."""
        ...

    def delete_data(self, table_name: str, ids: list[str]) -> Any:
        """Supprimer des lignes par identifiant."""
        ...

    def get_data(self, table_name: str, ids: list[str]) -> list[Any]:
        """Lire les lignes portant ces identifiants."""
        ...

    def has_record_embeddings(self) -> bool:
        """Si une table d'embeddings de records existe déjà."""
        ...

    def create_record_embedding_table(self, dim: int, model_id: str) -> None:
        """Créer la table d'embeddings pour une largeur de vecteur donnée."""
        ...

    @property
    def info(self) -> Any:
        """Les métadonnées du dataset, dont les schémas de tables."""
        ...


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

    def __init__(
        self, open_dataset: Callable[[], DatasetWriteTarget], kind: str, job_id: str, source_type: str = "model"
    ) -> None:
        """Lier un écrivain à un job et à son dataset.

        Le dataset est ouvert au premier usage, pas à la construction : un type de job qui
        n'écrit rien ne doit pas exiger qu'un dataset existe, et le runner construit un
        écrivain pour chaque chunk sans savoir si celui-ci s'en servira.
        """
        self._open_dataset = open_dataset
        self._dataset: DatasetWriteTarget | None = None
        self.kind = kind
        self.job_id = job_id
        self.source_type = source_type

    @property
    def dataset(self) -> DatasetWriteTarget:
        """Le dataset visé, ouvert à la demande."""
        if self._dataset is None:
            self._dataset = self._open_dataset()
        return self._dataset

    def provenance(self) -> dict[str, str]:
        """De quoi tracer une sortie jusqu'au traitement qui l'a produite.

        Les schémas d'annotation portent `source_type`, `source_name` et `source_metadata` ;
        les remplir ici plutôt que dans chaque type de job garantit qu'aucune sortie de job
        n'atterrit dans un dataset sans qu'on sache d'où elle vient. Le vocabulaire de
        `source_type` est celui des schémas — `model`, `human`, `ground_truth`, `other` —
        et c'est le type de job qui déclare lequel le décrit.
        """
        return {
            "source_type": self.source_type,
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

    # Le nom canonique de la table d'embeddings de records dans Pixano.
    EMBEDDING_TABLE = "embeddings"

    def write_record_embeddings(self, record_ids: Sequence[str], vectors: Sequence[Any], model: str) -> None:
        """Écrire un vecteur par enregistrement, en remplaçant le précédent.

        La table n'est pas ordinaire : sa largeur dépend du modèle, donc elle ne peut être
        créée qu'une fois un premier vecteur connu. Créer au premier passage évite d'imposer
        au type de job de connaître la dimension de son modèle.

        Raises:
            ValueError: Les vecteurs ne correspondent pas aux enregistrements.
        """
        if len(record_ids) != len(vectors):
            raise ValueError(f"{len(record_ids)} enregistrements pour {len(vectors)} vecteurs")
        if not vectors:
            return

        dataset = self.dataset
        if not dataset.has_record_embeddings():
            dataset.create_record_embedding_table(dim=len(vectors[0]), model_id=model)

        schema = dataset.info.tables[self.EMBEDDING_TABLE]
        rows = [
            schema(id=derive_id(self.kind, record_id, 0), record_id=record_id, vector=list(vector))
            for record_id, vector in zip(record_ids, vectors)
        ]
        dataset.update_data(self.EMBEDDING_TABLE, rows)
