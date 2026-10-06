# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Accès à un PostgreSQL vivant pour les tests qui en ont besoin."""

import os
from collections.abc import AsyncIterator, Iterator

import psycopg
import pytest
from pixano_worker.schema import SCHEMA_NAME, ensure_schema


# Variable dédiée, et c'est délibéré : un développeur qui fait tourner le worker a
# PIXANO_DATABASE_URL dans son environnement. Si les tests s'y branchaient, lancer pytest
# tronquerait sa base de travail. On ne doit pas pouvoir viser un déploiement par accident.
TEST_DATABASE_URL = "PIXANO_TEST_DATABASE_URL"


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """URL de la base jetable réservée aux tests."""
    url = os.environ.get(TEST_DATABASE_URL, "")
    if not url:
        pytest.skip(f"{TEST_DATABASE_URL} non défini")
    return url


def _refuse_a_populated_database(conn: psycopg.Connection) -> None:
    """Interdire d'effacer un schéma qui contient des jobs.

    La variable dédiée ne protège que de l'oubli ; elle ne protège pas de la main qui la
    pose sur une vraie base. Ce garde-fou attrape le cas restant — au prix d'une requête
    par test, ce qui est dérisoire face à une file effacée par erreur.
    """
    exists = conn.execute(f"SELECT to_regclass('{SCHEMA_NAME}.jobs')").fetchone()
    if exists is None or exists[0] is None:
        return
    row = conn.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.jobs").fetchone()
    if row is not None and row[0]:
        raise RuntimeError(
            f"{TEST_DATABASE_URL} désigne une base qui contient {row[0]} job(s). "
            "Les tests effacent le schéma : pointez-les sur une base jetable."
        )


@pytest.fixture
def blank_db(postgres_url: str) -> Iterator[psycopg.Connection]:
    """Connexion sur une base sans schéma de jobs, effacé avant et après le test."""
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        _refuse_a_populated_database(conn)
        conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")
        yield conn
        conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")


@pytest.fixture
def db(blank_db: psycopg.Connection) -> psycopg.Connection:
    """Connexion sur une base dont le schéma est installé."""
    ensure_schema(blank_db)
    return blank_db


@pytest.fixture
async def adb(db: psycopg.Connection, postgres_url: str) -> AsyncIterator[psycopg.AsyncConnection]:
    """Connexion asynchrone sur la même base, pour la file et le runner.

    Les deux connexions sont en autocommit : ce que le test prépare par `db` est visible
    tout de suite par `adb`, et inversement.
    """
    async with await psycopg.AsyncConnection.connect(postgres_url, autocommit=True) as conn:
        yield conn
