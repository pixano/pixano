# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests de l'installation du schéma de la file de jobs."""

import re
import threading

import psycopg
import pytest
from pixano_worker.schema import (
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SchemaVersionError,
    ensure_schema,
    read_schema_sql,
)
from psycopg.types.json import Jsonb


TABLES = ("schema_version", "job_kinds", "jobs", "job_chunks", "job_items", "job_events")
INDEXES = (
    "job_chunks_pending_idx",
    "job_chunks_expired_lease_idx",
    "jobs_created_at_idx",
    "jobs_to_plan_idx",
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
        assert "DROP SCHEMA pixano_jobs CASCADE" in message

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

    def test_the_whole_schema_is_all_or_nothing(self, blank_db: psycopg.Connection, postgres_url: str) -> None:
        """La DDL de PostgreSQL est transactionnelle, et toute la stratégie repose dessus.

        C'est ce qui permet de se passer d'un moteur de migrations : il n'existe pas d'état
        à moitié appliqué sur lequel il faudrait raisonner.
        """
        with psycopg.connect(postgres_url) as conn:
            conn.execute(read_schema_sql())
            conn.rollback()

        row = blank_db.execute(f"SELECT to_regclass('{SCHEMA_NAME}.jobs')").fetchone()
        assert row is not None and row[0] is None

    def test_reapplying_restores_an_index_dropped_by_hand(self, db: psycopg.Connection) -> None:
        """Rejouer le fichier répare un objet manquant — mais jamais une colonne modifiée,
        et c'est exactement le trou que couvre le numéro de version."""
        db.execute(f"DROP INDEX {SCHEMA_NAME}.job_chunks_pending_idx")

        ensure_schema(db)

        row = db.execute(
            "SELECT count(*) FROM pg_indexes WHERE schemaname = %s AND indexname = %s",
            (SCHEMA_NAME, "job_chunks_pending_idx"),
        ).fetchone()
        assert row is not None and row[0] == 1

    def test_a_payload_round_trips_without_manual_encoding(self, db: psycopg.Connection) -> None:
        """`jsonb` et psycopg s'occupent de la conversion : un modèle pydantic fait l'aller
        et le retour sans json.dumps, contrairement au magasin SQLite qui décode cinq
        colonnes à la main."""
        params = {"model": "clip", "batch": 16, "classes": ["chat", "chien"]}
        row = db.execute(
            f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, params, total_tasks) "
            "VALUES ('k', 'd', %s, 1) RETURNING id",
            (Jsonb(params),),
        ).fetchone()
        assert row is not None

        stored = db.execute(f"SELECT params FROM {SCHEMA_NAME}.jobs WHERE id = %s", (row[0],)).fetchone()
        assert stored is not None and stored[0] == params

    def test_timestamps_come_from_the_database_clock(self, db: psycopg.Connection) -> None:
        """Un worker à l'horloge décalée ne doit pas pouvoir prolonger ni voler un bail."""
        row = db.execute(
            f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, total_tasks) "
            "VALUES ('k', 'd', 1) RETURNING abs(extract(epoch from (created_at - now())))"
        ).fetchone()

        assert row is not None and float(row[0]) < 1

    def test_two_workers_can_install_at_the_same_instant(
        self, blank_db: psycopg.Connection, postgres_url: str
    ) -> None:
        """`IF NOT EXISTS` n'est pas atomique face à un créateur concurrent.

        Sans reprise, le worker perdant sortait en erreur et ne revenait jamais : le compose
        ne lui donne aucune politique de redémarrage. Il aurait fallu attendre l'étape 4 et
        ses workers multiples pour s'en apercevoir.
        """
        outcomes: list[str] = []

        def install() -> None:
            try:
                with psycopg.connect(postgres_url) as conn:
                    ensure_schema(conn)
                outcomes.append("ok")
            except Exception as exc:  # pragma: no cover - remonté par l'assertion
                outcomes.append(repr(exc))

        threads = [threading.Thread(target=install) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert outcomes == ["ok", "ok"]
        rows = blank_db.execute(f"SELECT version FROM {SCHEMA_NAME}.schema_version").fetchall()
        assert rows == [(SCHEMA_VERSION,)]
