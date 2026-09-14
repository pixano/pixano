# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Accès à un PostgreSQL vivant pour les tests qui en ont besoin."""

import os
from collections.abc import Iterator

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


@pytest.fixture
def blank_db(postgres_url: str) -> Iterator[psycopg.Connection]:
    """Connexion sur une base sans schéma de jobs, effacé avant et après le test."""
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")
        yield conn
        conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")


@pytest.fixture
def db(blank_db: psycopg.Connection) -> psycopg.Connection:
    """Connexion sur une base dont le schéma est installé."""
    ensure_schema(blank_db)
    return blank_db
