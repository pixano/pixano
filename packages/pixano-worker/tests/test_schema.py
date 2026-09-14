# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests de l'installation du schéma de la file de jobs."""

import re

import psycopg
import pytest
from pixano_worker.schema import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SchemaVersionError,
    ensure_schema,
    read_schema_sql,
)


TABLES = ("schema_version", "jobs", "job_chunks", "job_events")
INDEXES = (
    "job_chunks_pending_idx",
    "job_chunks_expired_lease_idx",
    "jobs_created_at_idx",
    "job_events_job_idx",
)


class TestSchemaFile:
    """Le fichier SQL doit être livré avec le paquet et rester rejouable."""

    def test_is_shipped_with_the_package(self) -> None:
        """Le garde-fou d'empaquetage : l'image installe le paquet, pas l'arbre source."""
        assert read_schema_sql().strip()

    def test_every_create_is_conditional(self) -> None:
        """Un CREATE sec glissé dans le fichier ferait échouer le second démarrage."""
        unconditional = re.findall(
            r"^CREATE\s+(?!SCHEMA IF NOT EXISTS|TABLE IF NOT EXISTS|INDEX IF NOT EXISTS)\S+.*$",
            read_schema_sql(),
            flags=re.MULTILINE,
        )

        assert unconditional == []

    def test_carries_no_query_parameter(self) -> None:
        """psycopg n'accepte plusieurs instructions que sans paramètre.

        Un `%s` dans ce fichier basculerait l'exécution sur le protocole étendu, qui refuse
        le multi-instructions — et la panne serait au démarrage, pas ici.
        """
        assert "%s" not in read_schema_sql()


class TestEnsureSchema:
    """Installation, rejeu, et refus sur version incompatible."""

    def test_creates_tables_and_indexes(self, blank_db: psycopg.Connection) -> None:
        ensure_schema(blank_db)

        tables = blank_db.execute("SELECT tablename FROM pg_tables WHERE schemaname = %s", (SCHEMA_NAME,)).fetchall()
        indexes = blank_db.execute("SELECT indexname FROM pg_indexes WHERE schemaname = %s", (SCHEMA_NAME,)).fetchall()

        assert {row[0] for row in tables} == set(TABLES)
        assert set(INDEXES) <= {row[0] for row in indexes}

    def test_records_the_version(self, db: psycopg.Connection) -> None:
        row = db.execute(f"SELECT version FROM {SCHEMA_NAME}.schema_version").fetchone()

        assert row is not None
        assert row[0] == SCHEMA_VERSION

    def test_applying_twice_changes_nothing(self, db: psycopg.Connection) -> None:
        """« Rejouable sans effet » : c'est la moitié de la DoD du lot."""
        before = db.execute(f"SELECT * FROM {SCHEMA_NAME}.schema_version").fetchall()

        ensure_schema(db)

        after = db.execute(f"SELECT * FROM {SCHEMA_NAME}.schema_version").fetchall()
        assert after == before
        assert len(after) == 1

    def test_refuses_an_unknown_version(self, db: psycopg.Connection) -> None:
        db.execute(f"UPDATE {SCHEMA_NAME}.schema_version SET version = %s", (SCHEMA_VERSION + 1,))

        with pytest.raises(SchemaVersionError) as raised:
            ensure_schema(db)

        message = str(raised.value)
        assert str(SCHEMA_VERSION) in message
        assert str(SCHEMA_VERSION + 1) in message
        assert "docker compose down -v" in message

    def test_a_refusal_writes_nothing(self, db: psycopg.Connection) -> None:
        """Le refus doit être inoffensif : on ne touche pas à une base qu'on ne comprend pas."""
        db.execute(f"UPDATE {SCHEMA_NAME}.schema_version SET version = 99")

        with pytest.raises(SchemaVersionError):
            ensure_schema(db)

        row = db.execute(f"SELECT version FROM {SCHEMA_NAME}.schema_version").fetchone()
        assert row is not None and row[0] == 99

    def test_recovers_from_a_crash_before_the_version_was_written(self, db: psycopg.Connection) -> None:
        """Une coupure entre la DDL et le marqueur laisse une table vide : on la complète."""
        db.execute(f"DELETE FROM {SCHEMA_NAME}.schema_version")

        ensure_schema(db)

        row = db.execute(f"SELECT version FROM {SCHEMA_NAME}.schema_version").fetchone()
        assert row is not None and row[0] == SCHEMA_VERSION

    def test_the_version_table_cannot_hold_two_rows(self, db: psycopg.Connection) -> None:
        """La lecture de la version ne doit jamais être ambiguë."""
        with pytest.raises(psycopg.errors.UniqueViolation):
            db.execute(f"INSERT INTO {SCHEMA_NAME}.schema_version (version) VALUES (2)")
