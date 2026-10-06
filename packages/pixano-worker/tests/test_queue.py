# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Queue behaviours the schema must make possible.

Lot 1 ships no runner, but it ships the tables and indexes the runner will rely on. These
tests exercise the queries of the following lots against the schema to check that it really
carries them — an index the planner does not pick, or a constraint that blocks the normal
path, would show up here and not in review.
"""

import threading

import psycopg
import pytest
from pixano_worker.schema import SCHEMA_NAME


CLAIM = f"""
UPDATE {SCHEMA_NAME}.job_chunks AS c
SET state = 'running', attempts = c.attempts + 1, claimed_by = %s,
    lease_until = now() + interval '2 minutes'
FROM (
    SELECT id FROM {SCHEMA_NAME}.job_chunks
    WHERE state = 'pending' ORDER BY id
    FOR UPDATE SKIP LOCKED LIMIT %s
) AS picked
WHERE c.id = picked.id
RETURNING c.id
"""


def _job_with_chunks(db: psycopg.Connection, count: int) -> str:
    row = db.execute(
        f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, total_tasks) " "VALUES ('dummy', 'ds', %s) RETURNING id",
        (count * 10,),
    ).fetchone()
    assert row is not None
    job = str(row[0])
    db.execute(
        f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count) "
        "SELECT %s, g, 10 FROM generate_series(0, %s) g",
        (job, count - 1),
    )
    return job


class TestClaim:
    """The queue's central property: no duplicate, no loss."""

    def test_two_workers_share_a_queue_without_overlap(self, db: psycopg.Connection, postgres_url: str) -> None:
        # One thousand, as lot 2's definition of done asked for.
        _job_with_chunks(db, 1000)
        claimed: dict[str, list[int]] = {"a": [], "b": []}
        failures: list[str] = []

        def drain(name: str) -> None:
            try:
                with psycopg.connect(postgres_url, autocommit=True) as conn:
                    while True:
                        rows = conn.execute(CLAIM, (name, 16)).fetchall()
                        if not rows:
                            return
                        ids = [row[0] for row in rows]
                        claimed[name].extend(ids)
                        conn.execute(
                            f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'done', "
                            "lease_until = NULL, produced = task_count, skipped = 0 WHERE id = ANY(%s)",
                            (ids,),
                        )
            except Exception as exc:  # pragma: no cover - surfaced by the assertion
                failures.append(f"{name}: {exc!r}")

        threads = [threading.Thread(target=drain, args=(name,)) for name in claimed]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert failures == []
        assert set(claimed["a"]) & set(claimed["b"]) == set()
        assert len(set(claimed["a"]) | set(claimed["b"])) == 1000
        left = db.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state <> 'done'").fetchone()
        assert left is not None and left[0] == 0

    def test_the_partial_index_carries_the_claim(self, db: psycopg.Connection) -> None:
        """Without this index, claiming would sweep the whole table on every round.

        At the scale of a 50,000-image job — the one the plan targets — the table keeps all
        the executed work while the claimable set shrinks. The test is run at this size
        deliberately: on a few hundred rows the planner picks a full scan, and the test would
        prove nothing.
        """
        _job_with_chunks(db, 50_000)
        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'done', produced = 10, skipped = 0 WHERE seq < 49_000"
        )
        db.execute(f"ANALYZE {SCHEMA_NAME}.job_chunks")

        plan = db.execute(
            f"EXPLAIN (COSTS OFF) SELECT id FROM {SCHEMA_NAME}.job_chunks "
            "WHERE state = 'pending' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 16"
        ).fetchall()

        assert "job_chunks_pending_idx" in "\n".join(row[0] for row in plan)


class TestCancellation:
    """Cancelling must drain the queue without the claim having to know about jobs."""

    def test_cancelling_empties_the_claimable_pool(self, db: psycopg.Connection) -> None:
        job = _job_with_chunks(db, 10)
        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'running', "
            "lease_until = now() + interval '2 minutes' WHERE seq = 0"
        )

        db.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))
        db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'cancelled' WHERE state = 'pending'")

        claimed = db.execute(CLAIM, ("worker", 16)).fetchall()
        assert claimed == []

    def test_a_running_chunk_is_left_to_its_worker(self, db: psycopg.Connection) -> None:
        """A running chunk is not torn away: its worker will return it between two batches."""
        _job_with_chunks(db, 10)
        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'running', "
            "lease_until = now() + interval '2 minutes' WHERE seq = 0"
        )

        db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'cancelled' WHERE state = 'pending'")

        running = db.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'running'").fetchone()
        assert running is not None and running[0] == 1


class TestLease:
    """The lease replaces the PID: it is what decides that a chunk can be taken over."""

    def test_an_expired_lease_returns_the_chunk_to_the_pool(self, db: psycopg.Connection) -> None:
        _job_with_chunks(db, 5)
        db.execute(CLAIM, ("worker-a", 1))
        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() - interval '1 minute' " "WHERE state = 'running'"
        )

        reclaimed = db.execute(
            f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks " "WHERE state = 'running' AND lease_until < now()"
        ).fetchone()

        assert reclaimed is not None and reclaimed[0] == 1

    def test_a_stale_worker_cannot_overwrite_its_successor(self, db: psycopg.Connection) -> None:
        """The attempts counter serves as a fencing token.

        A worker whose lease expired while it was working must find that its work has been
        taken away from it, and not overwrite the result of the one that took it over.
        """
        _job_with_chunks(db, 1)
        row = db.execute(CLAIM, ("worker-a", 1)).fetchone()
        assert row is not None
        chunk = row[0]
        stale_attempts = 1

        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() - interval '1 minute' " "WHERE id = %s",
            (chunk,),
        )
        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET attempts = attempts + 1, claimed_by = 'worker-b', "
            "lease_until = now() + interval '2 minutes' WHERE id = %s",
            (chunk,),
        )

        overwritten = db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'done', lease_until = NULL, produced = 10, skipped = 0 "
            "WHERE id = %s AND state = 'running' AND attempts = %s RETURNING id",
            (chunk, stale_attempts),
        ).fetchall()

        assert overwritten == []
        owner = db.execute(
            f"SELECT claimed_by, state FROM {SCHEMA_NAME}.job_chunks WHERE id = %s", (chunk,)
        ).fetchone()
        assert owner == ("worker-b", "running")

    def test_finishing_a_chunk_must_release_its_lease(self, db: psycopg.Connection) -> None:
        """The constraint also holds on UPDATE, which is the runner's real path."""
        _job_with_chunks(db, 1)
        row = db.execute(CLAIM, ("worker-a", 1)).fetchone()
        assert row is not None

        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute(
                f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'done', produced = 10, skipped = 0 WHERE id = %s",
                (row[0],),
            )
