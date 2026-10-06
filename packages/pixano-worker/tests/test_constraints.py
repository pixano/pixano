# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The schema constraints encode design decisions.

Each test here names the flaw a constraint makes impossible. These are not tests of
PostgreSQL: they are the guardrails that keep the following lots from reintroducing a problem
we deliberately designed out of reach.
"""

from datetime import datetime, timezone

import psycopg
import pytest
from pixano_worker.schema import SCHEMA_NAME


def _new_job(db: psycopg.Connection, **fields: object) -> str:
    columns = {"kind": "dummy", "dataset": "ds", "total_tasks": 1, **fields}
    names = ", ".join(columns)
    placeholders = ", ".join(["%s"] * len(columns))
    row = db.execute(
        f"INSERT INTO {SCHEMA_NAME}.jobs ({names}) VALUES ({placeholders}) RETURNING id",
        tuple(columns.values()),
    ).fetchone()
    assert row is not None
    return str(row[0])


class TestJobConstraints:
    def test_the_database_generates_the_identifier(self, db: psycopg.Connection) -> None:
        """Neither the application nor the worker needs an identifier library."""
        assert _new_job(db)

    def test_an_unknown_state_is_refused(self, db: psycopg.Connection) -> None:
        with pytest.raises(psycopg.errors.CheckViolation):
            _new_job(db, state="oops")

    def test_an_error_payload_requires_a_failed_job(self, db: psycopg.Connection) -> None:
        """The SQLite store's flaw: the cancellation stashed in the error payload.

        See src/pixano/datasets/io/jobs.py:189-207 — `request_cancel` writes
        `{"cancel_requested": True}` into `error_json` there, which overwrites the previous
        error and gets overwritten in return. Here it is structurally impossible.
        """
        with pytest.raises(psycopg.errors.CheckViolation):
            _new_job(db, state="done", error="{}")

    def test_a_cancelled_job_keeps_no_error(self, db: psycopg.Connection) -> None:
        with pytest.raises(psycopg.errors.CheckViolation):
            _new_job(db, state="cancelled", error='{"cancel_requested": true}')

    def test_params_must_be_an_object(self, db: psycopg.Connection) -> None:
        """A pydantic model always gets in; a bare array, never."""
        with pytest.raises(psycopg.errors.CheckViolation):
            _new_job(db, params="[1, 2]")


class TestChunkConstraints:
    def test_a_lease_exists_exactly_while_running(self, db: psycopg.Connection) -> None:
        """A finished chunk that kept its lease, or an active chunk without a lease — hence
        never recoverable — are refused at write time."""
        job = _new_job(db)

        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute(
                f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count, state) "
                "VALUES (%s, 0, 1, 'running')",
                (job,),
            )

    def test_a_finished_chunk_cannot_keep_its_lease(self, db: psycopg.Connection) -> None:
        job = _new_job(db)

        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute(
                f"INSERT INTO {SCHEMA_NAME}.job_chunks "
                "(job_id, seq, task_count, state, lease_until) "
                "VALUES (%s, 0, 1, 'done', now())",
                (job,),
            )

    def test_the_same_rank_cannot_be_inserted_twice(self, db: psycopg.Connection) -> None:
        """Makes inserting the chunks idempotent: a replayed POST does not double the work."""
        job = _new_job(db)
        db.execute(
            f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count) VALUES (%s, 0, 1)",
            (job,),
        )

        with pytest.raises(psycopg.errors.UniqueViolation):
            db.execute(
                f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count) VALUES (%s, 0, 1)",
                (job,),
            )

    def test_deleting_a_job_takes_its_chunks_and_events(self, db: psycopg.Connection) -> None:
        job = _new_job(db)
        db.execute(
            f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count) VALUES (%s, 0, 1)",
            (job,),
        )
        db.execute(
            f"INSERT INTO {SCHEMA_NAME}.job_events (job_id, type) VALUES (%s, 'state')",
            (job,),
        )

        db.execute(f"DELETE FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job,))

        for table in ("job_chunks", "job_events"):
            row = db.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.{table}").fetchone()
            assert row is not None and row[0] == 0


class TestPlanningLease:
    def test_a_planning_lease_only_exists_while_planning(self, db: psycopg.Connection) -> None:
        """A split-up job that kept its lease would still look reserved by a worker."""
        with pytest.raises(psycopg.errors.CheckViolation):
            _new_job(db, state="pending", planning_until=datetime.now(timezone.utc))


class TestOutcomeConstraints:
    """An outcome only exists for a finished chunk, and an item is quarantined only once."""

    @staticmethod
    def _chunk(db: psycopg.Connection) -> tuple[str, int]:
        job = _new_job(db)
        row = db.execute(
            f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count) VALUES (%s, 0, 10) RETURNING id",
            (job,),
        ).fetchone()
        assert row is not None
        return job, row[0]

    def test_a_finished_chunk_must_say_what_it_produced(self, db: psycopg.Connection) -> None:
        """Without an outcome, a job could only say what it attempted — lot 10's flaw."""
        _, chunk = self._chunk(db)

        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'done' WHERE id = %s", (chunk,))

    def test_a_chunk_sent_back_cannot_keep_an_earlier_outcome(self, db: psycopg.Connection) -> None:
        _, chunk = self._chunk(db)

        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET produced = 10, skipped = 0 WHERE id = %s", (chunk,))

    def test_an_item_is_quarantined_once_per_job(self, db: psycopg.Connection) -> None:
        """A chunk replayed after its worker's death must not double its quarantine."""
        job, chunk = self._chunk(db)
        insert = (
            f"INSERT INTO {SCHEMA_NAME}.job_items (job_id, chunk_id, item_id, reason) "
            "VALUES (%s, %s, 'img-1', 'unreadable')"
        )
        db.execute(insert, (job, chunk))

        with pytest.raises(psycopg.errors.UniqueViolation):
            db.execute(insert, (job, chunk))
