# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Comportements de file que le schéma doit rendre possibles.

Le lot 1 ne livre pas de runner, mais il livre les tables et les index sur lesquels le
runner s'appuiera. Ces tests exercent les requêtes des lots suivants contre le schéma pour
vérifier qu'il les porte réellement — un index qui n'est pas choisi par le planificateur, ou
une contrainte qui bloque le chemin normal, se verrait ici et pas en review.
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
        f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, total_tasks) " "VALUES ('factice', 'ds', %s) RETURNING id",
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
    """La propriété centrale de la file : ni doublon, ni perte."""

    def test_two_workers_share_a_queue_without_overlap(self, db: psycopg.Connection, postgres_url: str) -> None:
        _job_with_chunks(db, 200)
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
                            "lease_until = NULL WHERE id = ANY(%s)",
                            (ids,),
                        )
            except Exception as exc:  # pragma: no cover - remonté par l'assertion
                failures.append(f"{name}: {exc!r}")

        threads = [threading.Thread(target=drain, args=(name,)) for name in claimed]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert failures == []
        assert set(claimed["a"]) & set(claimed["b"]) == set()
        assert len(set(claimed["a"]) | set(claimed["b"])) == 200
        left = db.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state <> 'done'").fetchone()
        assert left is not None and left[0] == 0

    def test_the_partial_index_carries_the_claim(self, db: psycopg.Connection) -> None:
        """Sans cet index, la réclamation balaierait toute la table à chaque tour.

        À l'échelle d'un job de 50 000 images — celle que vise le plan — la table conserve
        tout le travail exécuté tandis que l'ensemble réclamable fond. Le test se fait à
        cette taille délibérément : sur quelques centaines de lignes le planificateur
        choisit un balayage complet, et le test ne prouverait rien.
        """
        _job_with_chunks(db, 50_000)
        db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'done' WHERE seq < 49_000")
        db.execute(f"ANALYZE {SCHEMA_NAME}.job_chunks")

        plan = db.execute(
            f"EXPLAIN (COSTS OFF) SELECT id FROM {SCHEMA_NAME}.job_chunks "
            "WHERE state = 'pending' ORDER BY id FOR UPDATE SKIP LOCKED LIMIT 16"
        ).fetchall()

        assert "job_chunks_pending_idx" in "\n".join(row[0] for row in plan)


class TestCancellation:
    """Annuler doit vider la file sans que la réclamation ait à connaître les jobs."""

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
        """On n'arrache pas un chunk en cours : son worker le rendra entre deux lots."""
        _job_with_chunks(db, 10)
        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'running', "
            "lease_until = now() + interval '2 minutes' WHERE seq = 0"
        )

        db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'cancelled' WHERE state = 'pending'")

        running = db.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'running'").fetchone()
        assert running is not None and running[0] == 1


class TestLease:
    """Le bail remplace le PID : c'est lui qui décide qu'un chunk est reprenable."""

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
        """Le compteur de tentatives sert de jeton de garde.

        Un worker dont le bail a expiré pendant qu'il travaillait doit constater que son
        travail lui a été retiré, et non écraser le résultat de celui qui l'a repris.
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
            f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'done', lease_until = NULL "
            "WHERE id = %s AND state = 'running' AND attempts = %s RETURNING id",
            (chunk, stale_attempts),
        ).fetchall()

        assert overwritten == []
        owner = db.execute(
            f"SELECT claimed_by, state FROM {SCHEMA_NAME}.job_chunks WHERE id = %s", (chunk,)
        ).fetchone()
        assert owner == ("worker-b", "running")

    def test_finishing_a_chunk_must_release_its_lease(self, db: psycopg.Connection) -> None:
        """La contrainte tient aussi sur UPDATE, qui est le chemin réel du runner."""
        _job_with_chunks(db, 1)
        row = db.execute(CLAIM, ("worker-a", 1)).fetchone()
        assert row is not None

        with pytest.raises(psycopg.errors.CheckViolation):
            db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'done' WHERE id = %s", (row[0],))
