# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Le point de lecture unique d'un dataset, pour la planification d'un job.

Symétrique de l'écrivain, et pour la même raison : un type de job énumère ce qu'il va traiter
sans ouvrir de dataset lui-même. Cela garde une seule porte d'entrée vers LanceDB, ce qui
rendra possible d'y mettre un cache ou une coordination sans toucher au moindre type.

Le dataset est ouvert au premier usage : un type dont le travail tient dans ses paramètres
n'a rien à lire, et ne doit pas exiger qu'un dataset existe.
"""

import logging
from typing import Any, Callable, Iterator, Sequence

from .media import MediaResolver, ResolvedMedia
from .writer import DatasetReadSource


logger = logging.getLogger("pixano-worker")

# Combien de lignes on ramène par requête en énumérant une table. Assez pour amortir l'aller
# et retour, assez peu pour qu'un dataset de plusieurs millions d'items ne tienne pas en
# mémoire d'un coup.
PAGE_SIZE = 2_000


class JobReader:
    """Lit un dataset pour le compte d'un type de job.

    Attributes:
        media: Comment désigner un média pour l'inference.
    """

    def __init__(self, open_dataset: Callable[[], DatasetReadSource], media: MediaResolver) -> None:
        """Lier un lecteur à un dataset et à la façon de résoudre ses médias."""
        self._open_dataset = open_dataset
        self._dataset: DatasetReadSource | None = None
        self.media = media

    @property
    def dataset(self) -> DatasetReadSource:
        """Le dataset visé, ouvert à la demande."""
        if self._dataset is None:
            self._dataset = self._open_dataset()
        return self._dataset

    def count(self, table_name: str, where: str | None = None) -> int:
        """Combien de lignes une table contient, sans la matérialiser."""
        return self.dataset.count_rows_where(table_name, where)

    def ids(self, table_name: str, where: str | None = None) -> Iterator[str]:
        """Énumérer les identifiants d'une table, par pages.

        Par pages, parce qu'un job peut viser des centaines de milliers d'items et que la
        planification doit rester tenable en mémoire.
        """
        total = self.count(table_name, where)
        for offset in range(0, total, PAGE_SIZE):
            rows = self.dataset.get_data(table_name, limit=PAGE_SIZE, skip=offset, where=where)
            for row in rows:
                yield row.id

    def rows(self, table_name: str, ids: Sequence[str]) -> list[Any]:
        """Lire des lignes précises, par identifiant."""
        return self.dataset.get_data(table_name, ids=list(ids))

    def resolve_media(self, table_name: str, view: Any) -> ResolvedMedia | None:
        """Désigner un média pour l'inference — un chemin si possible, les octets sinon."""
        return self.media.resolve(self.dataset, table_name, view)
