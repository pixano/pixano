# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests of the job queue schema installation."""

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
    """The SQL file must ship with the package and stay replayable."""

    def test_is_shipped_with_the_package(self) -> None:
        """The packaging guardrail: the image installs the package, not the source tree."""
        assert read_schema_sql().strip()

    def test_every_create_is_conditional(self) -> None:
        """A bare CREATE slipped into the file would make the second startup fail."""
        unconditional = re.findall(
            r"^CREATE\s+(?!SCHEMA IF NOT EXISTS|TABLE IF NOT EXISTS|INDEX IF NOT EXISTS)\S+.*$",
            read_schema_sql(),
            flags=re.MULTILINE,
        )

        assert unconditional == []

    def test_carries_no_query_parameter(self) -> None:
        """psycopg only accepts several statements when there is no parameter.

        A `%s` in this file would switch execution to the extended protocol, which refuses
        multi-statements — and the failure would be at startup, not here.
        """
        assert "%s" not in read_schema_sql()


class TestEnsureSchema:
    """Installation, replay, and refusal on an incompatible version."""

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
        """'Replayable without effect': that is half of the lot's DoD."""
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
        """The refusal must be harmless: we do not touch a database we do not understand."""
        db.execute(f"UPDATE {SCHEMA_NAME}.schema_version SET version = 99")

        with pytest.raises(SchemaVersionError):
            ensure_schema(db)

        row = db.execute(f"SELECT version FROM {SCHEMA_NAME}.schema_version").fetchone()
        assert row is not None and row[0] == 99

    def test_recovers_from_a_crash_before_the_version_was_written(self, db: psycopg.Connection) -> None:
        """A crash between the DDL and the marker leaves an empty table: we fill it in."""
        db.execute(f"DELETE FROM {SCHEMA_NAME}.schema_version")

        ensure_schema(db)

        row = db.execute(f"SELECT version FROM {SCHEMA_NAME}.schema_version").fetchone()
        assert row is not None and row[0] == SCHEMA_VERSION

    def test_the_version_table_cannot_hold_two_rows(self, db: psycopg.Connection) -> None:
        """Reading the version must never be ambiguous."""
        with pytest.raises(psycopg.errors.UniqueViolation):
            db.execute(f"INSERT INTO {SCHEMA_NAME}.schema_version (version) VALUES (2)")

    def test_the_whole_schema_is_all_or_nothing(self, blank_db: psycopg.Connection, postgres_url: str) -> None:
        """PostgreSQL's DDL is transactional, and the whole strategy rests on it.

        This is what makes it possible to do without a migration engine: there is no
        half-applied state to reason about.
        """
        with psycopg.connect(postgres_url) as conn:
            conn.execute(read_schema_sql())
            conn.rollback()

        row = blank_db.execute(f"SELECT to_regclass('{SCHEMA_NAME}.jobs')").fetchone()
        assert row is not None and row[0] is None

    def test_reapplying_restores_an_index_dropped_by_hand(self, db: psycopg.Connection) -> None:
        """Replaying the file repairs a missing object — but never an altered column,
        and that is exactly the gap the version number covers."""
        db.execute(f"DROP INDEX {SCHEMA_NAME}.job_chunks_pending_idx")

        ensure_schema(db)

        row = db.execute(
            "SELECT count(*) FROM pg_indexes WHERE schemaname = %s AND indexname = %s",
            (SCHEMA_NAME, "job_chunks_pending_idx"),
        ).fetchone()
        assert row is not None and row[0] == 1

    def test_a_payload_round_trips_without_manual_encoding(self, db: psycopg.Connection) -> None:
        """`jsonb` and psycopg take care of the conversion: a pydantic model makes the round
        trip without json.dumps, unlike the SQLite store which decodes five columns by
        hand."""
        params = {"model": "clip", "batch": 16, "classes": ["cat", "dog"]}
        row = db.execute(
            f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, params, total_tasks) "
            "VALUES ('k', 'd', %s, 1) RETURNING id",
            (Jsonb(params),),
        ).fetchone()
        assert row is not None

        stored = db.execute(f"SELECT params FROM {SCHEMA_NAME}.jobs WHERE id = %s", (row[0],)).fetchone()
        assert stored is not None and stored[0] == params

    def test_timestamps_come_from_the_database_clock(self, db: psycopg.Connection) -> None:
        """A worker with a skewed clock must be able neither to extend nor to steal a lease."""
        row = db.execute(
            f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, total_tasks) "
            "VALUES ('k', 'd', 1) RETURNING abs(extract(epoch from (created_at - now())))"
        ).fetchone()

        assert row is not None and float(row[0]) < 1

    def test_two_workers_can_install_at_the_same_instant(
        self, blank_db: psycopg.Connection, postgres_url: str
    ) -> None:
        """`IF NOT EXISTS` is not atomic against a concurrent creator.

        Without a retry, the losing worker exited in error and never came back: the compose
        gives it no restart policy. It would have taken step 4 and its multiple workers to
        notice.
        """
        outcomes: list[str] = []

        def install() -> None:
            try:
                with psycopg.connect(postgres_url) as conn:
                    ensure_schema(conn)
                outcomes.append("ok")
            except Exception as exc:  # pragma: no cover - surfaced by the assertion
                outcomes.append(repr(exc))

        threads = [threading.Thread(target=install) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert outcomes == ["ok", "ok"]
        rows = blank_db.execute(f"SELECT version FROM {SCHEMA_NAME}.schema_version").fetchall()
        assert rows == [(SCHEMA_VERSION,)]
