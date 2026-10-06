# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Le registre des types de jobs, et sa déclaration en base.

Le registre est local au worker ; l'application n'a aucun moyen de l'importer. C'est pourquoi
chaque worker publie ce qu'il sait faire dans `job_kinds` au démarrage : cette table est le
seul pont entre les deux, et elle porte la seule vérité qui vaille — ce que du code
réellement déployé sait exécuter.
"""

import psycopg
from psycopg.types.json import Jsonb

from ..schema import SCHEMA_NAME
from .base import JobKind


DECLARE = f"""
INSERT INTO {SCHEMA_NAME}.job_kinds (name, params_schema, declared_by, declared_at)
VALUES (%s, %s, %s, now())
ON CONFLICT (name) DO UPDATE
SET params_schema = EXCLUDED.params_schema,
    declared_by = EXCLUDED.declared_by,
    declared_at = EXCLUDED.declared_at
"""


class Registry:
    """Les types de jobs que ce worker sait exécuter."""

    def __init__(self) -> None:
        """Créer un registre vide."""
        self._kinds: dict[str, JobKind] = {}

    def register(self, kind: JobKind) -> None:
        """Ajouter un type au registre.

        Raises:
            ValueError: Un type porte déjà ce nom.
        """
        if kind.name in self._kinds:
            raise ValueError(f"le type de job '{kind.name}' est déjà enregistré")
        self._kinds[kind.name] = kind

    def get(self, name: str) -> JobKind | None:
        """Le type portant ce nom, ou None."""
        return self._kinds.get(name)

    def names(self) -> list[str]:
        """Les noms enregistrés, triés."""
        return sorted(self._kinds)

    def declare(self, conn: psycopg.Connection, worker_id: str) -> int:
        """Publier ce registre en base, pour que l'application puisse valider.

        La déclaration écrase la précédente : un worker redéployé avec des paramètres
        modifiés met le schéma à jour sans intervention.

        Returns:
            Le nombre de types déclarés.
        """
        with conn.transaction():
            for kind in self._kinds.values():
                conn.execute(DECLARE, (kind.name, Jsonb(kind.params_schema()), worker_id))
        return len(self._kinds)
