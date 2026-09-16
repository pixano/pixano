# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests des primitives de réclamation du worker."""

import asyncio

import psycopg
from pixano_worker import queue
from pixano_worker.schema import SCHEMA_NAME


def _enqueue(db: psycopg.Connection, chunks: int, tasks_per_chunk: int = 10) -> str:
    row = db.execute(
        f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, total_tasks, state) "
        "VALUES ('factice', 'ds', %s, 'pending') RETURNING id",
        (chunks * tasks_per_chunk,),
    ).fetchone()
    assert row is not None
    job = str(row[0])
    db.execute(
        f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, payload, task_count) "
        "SELECT %s, g, jsonb_build_object('item_ids', jsonb_build_array(g)), %s "
        "FROM generate_series(0, %s) g",
        (job, tasks_per_chunk, chunks - 1),
    )
    return job


class TestClaim:
    async def test_claims_up_to_the_batch_size(self, db: psycopg.Connection, adb: psycopg.AsyncConnection) -> None:
        _enqueue(db, 10)

        claimed = await queue.claim(adb, "worker-a", 4)

        assert len(claimed) == 4
        assert all(chunk.attempts == 1 for chunk in claimed)
        assert claimed[0].payload == {"item_ids": [0]}

    async def test_claims_in_order(self, db: psycopg.Connection, adb: psycopg.AsyncConnection) -> None:
        """L'ordre FIFO : un job soumis avant est servi avant."""
        _enqueue(db, 10)

        claimed = await queue.claim(adb, "worker-a", 3)

        assert [chunk.seq for chunk in claimed] == [0, 1, 2]

    async def test_an_empty_queue_returns_nothing(self, db: psycopg.Connection, adb: psycopg.AsyncConnection) -> None:
        assert await queue.claim(adb, "worker-a", 8) == []

    async def test_a_claimed_chunk_is_no_longer_claimable(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        _enqueue(db, 4)
        await queue.claim(adb, "worker-a", 4)

        assert await queue.claim(adb, "worker-b", 4) == []

    async def test_two_workers_never_take_the_same_chunk(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection, postgres_url: str
    ) -> None:
        """La propriété centrale de la file, à travers le vrai code cette fois."""
        _enqueue(db, 300)
        taken: dict[str, list[int]] = {"a": [], "b": []}
        failures: list[str] = []

        async def drain(name: str) -> None:
            try:
                async with await psycopg.AsyncConnection.connect(postgres_url, autocommit=True) as conn:
                    while True:
                        chunks = await queue.claim(conn, name, 16)
                        if not chunks:
                            return
                        taken[name].extend(chunk.id for chunk in chunks)
                        for chunk in chunks:
                            await queue.finish(conn, chunk)
            except Exception as exc:  # pragma: no cover - remonté par l'assertion
                failures.append(f"{name}: {exc!r}")

        await asyncio.gather(*(drain(name) for name in taken))

        assert failures == []
        assert set(taken["a"]) & set(taken["b"]) == set()
        assert len(set(taken["a"]) | set(taken["b"])) == 300
        left = db.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state <> 'done'").fetchone()
        assert left is not None and left[0] == 0


class TestFinish:
    async def test_advances_the_job_progress(self, db: psycopg.Connection, adb: psycopg.AsyncConnection) -> None:
        job = _enqueue(db, 5, tasks_per_chunk=10)
        chunks = await queue.claim(adb, "worker-a", 2)

        for chunk in chunks:
            assert await queue.finish(adb, chunk)

        row = db.execute(f"SELECT state, done_tasks FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job,)).fetchone()
        assert row == ("running", 20)

    async def test_a_stale_worker_cannot_finish_a_stolen_chunk(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Sans ce garde, un worker lent écraserait le résultat de son successeur."""
        job = _enqueue(db, 1)
        chunk = (await queue.claim(adb, "worker-a", 1))[0]
        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() - interval '1 minute' WHERE state = 'running'"
        )
        await queue.reclaim_expired(adb)
        await queue.claim(adb, "worker-b", 1)

        assert await queue.finish(adb, chunk) is False

        row = db.execute(f"SELECT done_tasks FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job,)).fetchone()
        assert row is not None and row[0] == 0


class TestRecovery:
    async def test_an_expired_lease_returns_the_chunk(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        _enqueue(db, 3)
        await queue.claim(adb, "worker-a", 3)
        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() - interval '1 minute' WHERE state = 'running'"
        )

        reclaimed, abandoned = await queue.reclaim_expired(adb)

        assert (reclaimed, abandoned) == (3, 0)
        assert len(await queue.claim(adb, "worker-b", 3)) == 3

    async def test_a_chunk_that_keeps_killing_workers_is_set_aside(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Sans plafond, un chunk qui fait tomber son worker ferait boucler la file.

        Le bail n'est antidaté que sur les chunks qui tournent : un chunk écarté n'en a plus,
        et la contrainte du schéma refuserait d'ailleurs de lui en rendre un.
        """
        _enqueue(db, 1)
        outcomes = []
        for _ in range(queue.MAX_ATTEMPTS):
            await queue.claim(adb, "worker-a", 1)
            db.execute(
                f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() - interval '1 minute' "
                "WHERE state = 'running'"
            )
            outcomes.append(await queue.reclaim_expired(adb))

        assert outcomes[-1] == (0, 1), f"attendu un abandon au dernier tour, obtenu {outcomes}"
        row = db.execute(f"SELECT state, error FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row is not None and row[0] == "error"
        assert row[1]["reason"] == "abandonné"
        assert await queue.claim(adb, "worker-b", 1) == []

    async def test_a_restarted_worker_returns_its_own_chunks_at_once(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Le bail finirait par les rendre ; les rendre au démarrage évite deux minutes d'attente."""
        _enqueue(db, 5)
        await queue.claim(adb, "worker-a", 3)

        released = await queue.release_own(adb, "worker-a")

        assert released == 3
        assert len(await queue.claim(adb, "worker-a", 5)) == 5

    async def test_another_workers_chunks_are_left_alone(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        _enqueue(db, 4)
        await queue.claim(adb, "worker-a", 2)

        assert await queue.release_own(adb, "worker-b") == 0


class TestCancellation:
    async def test_reports_whether_a_job_was_cancelled(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        running = _enqueue(db, 2)
        cancelled = _enqueue(db, 2)
        db.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (cancelled,))

        assert await queue.is_cancelled(adb, running) is False
        assert await queue.is_cancelled(adb, cancelled) is True

    async def test_a_released_chunk_goes_back_to_the_queue(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Ce que fait un worker qui voit l'annulation entre deux lots."""
        _enqueue(db, 2)
        chunk = (await queue.claim(adb, "worker-a", 1))[0]

        assert await queue.release(adb, chunk)

        row = db.execute(
            f"SELECT state, claimed_by, lease_until FROM {SCHEMA_NAME}.job_chunks WHERE id = %s",
            (chunk.id,),
        ).fetchone()
        assert row == ("pending", None, None)


class TestLeaseDuration:
    def test_the_lease_outlives_the_liveness_window(self) -> None:
        """Un chunk ne doit pas être volé avant qu'on ait constaté que son porteur est mort."""
        assert queue.LEASE_TTL.total_seconds() > queue.MAX_HEARTBEAT_AGE_S
