# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Installation du schéma de la file de jobs.

Il n'y a délibérément pas de moteur de migrations. Jusqu'à ce que cette base porte des
données irremplaçables — les comptes utilisateurs, à l'étape 6 — « effacer et recréer » est
la stratégie de migration retenue : les jobs sont jetables, leurs résultats vivent dans
LanceDB. Ce module se contente donc d'appliquer un fichier idempotent et d'inscrire un
numéro de version.

Ce numéro n'est pas une décoration : `CREATE TABLE IF NOT EXISTS` crée une table absente
mais ne modifie jamais une table existante. Sans lui, un worker tournerait joyeusement sur
un schéma qui n'est plus le sien et échouerait plus tard, loin de la cause. Avec lui, il
refuse de démarrer et dit quoi faire.

**Toute modification de `sql/schema.sql` impose d'incrémenter `SCHEMA_VERSION`.**
"""

import logging
from importlib.resources import files

import psycopg


logger = logging.getLogger("pixano-worker")

# Incrémenter à chaque modification de sql/schema.sql.
SCHEMA_VERSION = 1

SCHEMA_NAME = "pixano_jobs"

# Les canaux NOTIFY sont globaux à la base, pas au schéma : le préfixe évite une collision
# avec ce que l'étape 6 ajoutera.
NOTIFY_CHANNEL = "pixano_jobs_events"


class SchemaVersionError(RuntimeError):
    """La base porte une version de schéma que ce worker ne sait pas utiliser."""


def read_schema_sql() -> str:
    """Lire le fichier de schéma livré dans le paquet.

    Passe par `importlib.resources` et non par un chemin relatif à `__file__` : l'image
    installe le paquet dans le venv, où le fichier n'est pas à côté d'un arbre source.
    """
    return files("pixano_worker").joinpath("sql/schema.sql").read_text(encoding="utf-8")


def _installed_version(cursor: psycopg.Cursor) -> int | None:
    """Lire la version en base, ou None si le schéma n'a jamais été installé."""
    cursor.execute(f"SELECT to_regclass('{SCHEMA_NAME}.schema_version')")
    row = cursor.fetchone()
    if row is None or row[0] is None:
        return None
    cursor.execute(f"SELECT version FROM {SCHEMA_NAME}.schema_version")
    row = cursor.fetchone()
    return None if row is None else int(row[0])


# `IF NOT EXISTS` n'est pas atomique face à un créateur concurrent : deux workers qui
# démarrent ensemble sur une base vierge voient tous deux « la table n'existe pas », et le
# second échoue à la création. PostgreSQL annule alors sa transaction — rien n'est appliqué
# à moitié — et il suffit de recommencer pour prendre la branche « déjà installé ».
_CONCURRENT_CREATION = (
    psycopg.errors.UniqueViolation,
    psycopg.errors.DuplicateSchema,
    psycopg.errors.DuplicateTable,
    psycopg.errors.DuplicateObject,
)


def ensure_schema(conn: psycopg.Connection) -> None:
    """Installer le schéma si besoin, et vérifier qu'il est celui qu'attend ce worker.

    Args:
        conn: Connexion PostgreSQL ouverte.

    Raises:
        SchemaVersionError: La base porte une autre version que `SCHEMA_VERSION`. Rien
            n'est écrit dans ce cas : la transaction est annulée.
    """
    try:
        installed = _install(conn)
    except _CONCURRENT_CREATION:
        logger.info("schéma installé au même instant par un autre worker — nouvel essai")
        installed = _install(conn)

    if installed is None:
        logger.info("schéma %s créé (version %s)", SCHEMA_NAME, SCHEMA_VERSION)
    else:
        logger.info("schéma %s déjà à la version %s", SCHEMA_NAME, SCHEMA_VERSION)


def _install(conn: psycopg.Connection) -> int | None:
    """Appliquer le fichier en une transaction, et renvoyer la version trouvée avant."""
    with conn.transaction(), conn.cursor() as cursor:
        installed = _installed_version(cursor)

        if installed is not None and installed != SCHEMA_VERSION:
            raise SchemaVersionError(
                f"schéma de base incompatible : la base porte la version {installed}, "
                f"ce worker attend la version {SCHEMA_VERSION}.\n"
                "Aucune migration n'est fournie à ce stade — rien de ce que contient cette "
                "base ne peut être perdu, tout est recréé au prochain démarrage :\n"
                "  docker compose down -v && docker compose up"
            )

        # Rejouer le fichier même quand la version correspond : c'est une poignée
        # d'instructions `IF NOT EXISTS`, et ça répare une base dont un index aurait été
        # supprimé à la main. Ça ne répare en revanche aucune colonne modifiée — c'est
        # exactement le trou que le numéro de version couvre.
        cursor.execute(read_schema_sql())  # type: ignore[arg-type]
        cursor.execute(
            f"INSERT INTO {SCHEMA_NAME}.schema_version (version) VALUES (%s) " "ON CONFLICT (singleton) DO NOTHING",
            (SCHEMA_VERSION,),
        )

    return installed
