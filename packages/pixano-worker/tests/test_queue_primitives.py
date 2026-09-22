# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests des primitives de réclamation du worker."""

import asyncio
from dataclasses import dataclass

import psycopg
import pytest
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

    async def test_a_claimed_job_is_running_before_any_of_its_chunks_finishes(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Revue d'architecture, point 17 : un premier chunk long laissait le job « pending »."""
        job = _enqueue(db, 4)
        claimed = await queue.claim(adb, "worker-a", 2)

        started = await queue.start_jobs(adb, (chunk.job_id for chunk in claimed))

        assert started == [job]
        row = db.execute(f"SELECT state FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job,)).fetchone()
        assert row == ("running",)
        events = db.execute(
            f"SELECT type, payload FROM {SCHEMA_NAME}.job_events WHERE job_id = %s ORDER BY id", (job,)
        ).fetchall()
        assert events == [("state", {"state": "running"})]

    async def test_starting_a_job_twice_announces_it_once(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Deux workers réclament des chunks du même job : un seul fait la transition."""
        job = _enqueue(db, 4)
        first = await queue.claim(adb, "worker-a", 1)
        second = await queue.claim(adb, "worker-b", 1)

        assert await queue.start_jobs(adb, [first[0].job_id]) == [job]
        assert await queue.start_jobs(adb, [second[0].job_id]) == []

        count = db.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_events WHERE job_id = %s", (job,)).fetchone()
        assert count == (1,)

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
    async def test_announces_the_job_running_then_its_progress_in_the_same_transaction(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Revue indépendante, D2/D6 : émis après coup, `running` pouvait suivre `done`.

        C'est le filet du cas où la marque posée à la réclamation a manqué : ici elle n'est
        pas posée du tout, et c'est le premier chunk terminé qui doit l'annoncer.
        """
        job = _enqueue(db, 2, tasks_per_chunk=10)
        chunks = await queue.claim(adb, "worker-a", 2)

        for chunk in chunks:
            await queue.finish(adb, chunk)

        events = db.execute(
            f"SELECT type, payload FROM {SCHEMA_NAME}.job_events WHERE job_id = %s ORDER BY id", (job,)
        ).fetchall()
        assert events == [
            ("state", {"state": "running"}),
            ("progress", {"done_tasks": 10, "total_tasks": 20}),
            ("progress", {"done_tasks": 20, "total_tasks": 20}),
        ]

    async def test_advances_the_job_progress(self, db: psycopg.Connection, adb: psycopg.AsyncConnection) -> None:
        job = _enqueue(db, 5, tasks_per_chunk=10)
        chunks = await queue.claim(adb, "worker-a", 2)

        outcomes = [await queue.finish(adb, chunk) for chunk in chunks]

        assert [finished.started_job for finished in outcomes if finished] == [True, False]

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

        assert await queue.finish(adb, chunk) is None

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

        recovery = await queue.reclaim_expired(adb)

        assert (recovery.requeued, recovery.abandoned_jobs) == (3, frozenset())
        assert len(await queue.claim(adb, "worker-b", 3)) == 3

    async def test_a_chunk_that_keeps_killing_workers_is_set_aside(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Sans plafond, un chunk qui fait tomber son worker ferait boucler la file.

        Le bail n'est antidaté que sur les chunks qui tournent : un chunk écarté n'en a plus,
        et la contrainte du schéma refuserait d'ailleurs de lui en rendre un.
        """
        job = _enqueue(db, 1)
        outcomes = []
        for _ in range(queue.MAX_ATTEMPTS):
            await queue.claim(adb, "worker-a", 1)
            db.execute(
                f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() - interval '1 minute' "
                "WHERE state = 'running'"
            )
            outcomes.append(await queue.reclaim_expired(adb))

        assert outcomes[-1] == queue.Recovery(0, frozenset({job})), f"attendu un abandon au dernier tour : {outcomes}"
        row = db.execute(f"SELECT state, error FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row is not None and row[0] == "error"
        assert row[1]["reason"] == "abandoned after its attempts"
        assert await queue.claim(adb, "worker-b", 1) == []

    async def test_a_restarted_worker_returns_its_own_chunks_at_once(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Le bail finirait par les rendre ; les rendre au démarrage évite deux minutes d'attente."""
        _enqueue(db, 5)
        await queue.claim(adb, "worker-a", 3)

        recovery = await queue.release_own(adb, "worker-a")

        assert recovery == queue.Recovery(3, frozenset())
        assert len(await queue.claim(adb, "worker-a", 5)) == 5

    async def test_another_workers_chunks_are_left_alone(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        _enqueue(db, 4)
        await queue.claim(adb, "worker-a", 2)

        assert await queue.release_own(adb, "worker-b") == queue.Recovery(0, frozenset())

    async def test_a_chunk_that_kills_its_worker_at_every_restart_is_set_aside(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Revue de l'étape 1 : ce chemin ne regardait pas les tentatives.

        Avec un redémarrage automatique, un chunk qui fait planter son worker — une image qui
        fait exploser la mémoire — le relançait sans fin : réclamé, crash, rendu, réclamé.
        """
        job = _enqueue(db, 1)
        recoveries = []
        for _ in range(queue.MAX_ATTEMPTS):
            await queue.claim(adb, "worker-a", 1)
            recoveries.append(await queue.release_own(adb, "worker-a"))

        assert recoveries[-1] == queue.Recovery(0, frozenset({job}))
        assert await queue.claim(adb, "worker-a", 1) == []


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


class TestRetryLater:
    """Une panne passagère rend le chunk à la file, mais pas tout de suite."""

    async def test_the_chunk_goes_back_but_is_not_claimable_yet(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Rejoué dans la seconde contre une inférence qui redémarre, il épuiserait ses tentatives."""
        _enqueue(db, 1)
        chunk = (await queue.claim(adb, "worker-a", 1))[0]

        state = await queue.retry_later(adb, chunk, {"reason": "panne passagère"})

        assert state == "pending"
        assert await queue.claim(adb, "worker-a", 1) == []
        row = db.execute(
            f"SELECT extract(epoch FROM available_at - now()), error->>'reason' FROM {SCHEMA_NAME}.job_chunks"
        ).fetchone()
        assert row is not None
        assert float(row[0]) == pytest.approx(queue.RETRY_BASE_DELAY.total_seconds(), abs=2)
        assert row[1] == "panne passagère"

    async def test_the_delay_doubles_with_each_attempt(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        _enqueue(db, 1)
        delays = []
        for _ in range(3):
            chunk = (await queue.claim(adb, "worker-a", 1))[0]
            await queue.retry_later(adb, chunk, {"reason": "panne passagère"})
            row = db.execute(
                f"SELECT extract(epoch FROM available_at - now()) FROM {SCHEMA_NAME}.job_chunks"
            ).fetchone()
            assert row is not None
            delays.append(float(row[0]))
            db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET available_at = now()")

        base = queue.RETRY_BASE_DELAY.total_seconds()
        assert delays == pytest.approx([base, base * 2, base * 4], abs=2)

    async def test_a_failure_that_never_passes_is_set_aside(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        _enqueue(db, 1)
        states = []
        for _ in range(queue.MAX_ATTEMPTS):
            chunk = (await queue.claim(adb, "worker-a", 1))[0]
            states.append(await queue.retry_later(adb, chunk, {"reason": "panne passagère"}))
            db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET available_at = now()")

        assert states == ["pending"] * (queue.MAX_ATTEMPTS - 1) + ["error"]
        assert await queue.claim(adb, "worker-a", 1) == []

    async def test_a_stale_worker_cannot_send_back_a_stolen_chunk(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        _enqueue(db, 1)
        chunk = (await queue.claim(adb, "worker-a", 1))[0]
        await queue.release(adb, chunk)
        await queue.claim(adb, "worker-b", 1)

        assert await queue.retry_later(adb, chunk, {"reason": "panne passagère"}) is None


class TestRetriedJob:
    """Un job relancé par l'API rouvre ses chunks avec un compte de tentatives neuf.

    `attempts` ne recule jamais — c'est le jeton de garde — donc le compte repart d'un plancher.
    """

    @staticmethod
    def _reopen_like_the_api(db: psycopg.Connection, chunk_id: int) -> None:
        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'pending', attempts_floor = attempts, claimed_by = NULL, "
            "error = NULL, available_at = now() WHERE id = %s",
            (chunk_id,),
        )

    async def test_a_reopened_chunk_has_its_attempts_again(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        _enqueue(db, 1)
        chunk = (await queue.claim(adb, "worker-a", 1))[0]
        db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET attempts = %s WHERE id = %s", (queue.MAX_ATTEMPTS, chunk.id))
        exhausted = queue.Chunk(**{**chunk.__dict__, "attempts": queue.MAX_ATTEMPTS})
        assert await queue.retry_later(adb, exhausted, {"reason": "x"}) == "error"

        self._reopen_like_the_api(db, chunk.id)
        again = (await queue.claim(adb, "worker-a", 1))[0]

        # Première tentative du nouveau compte : rendu à la file, pas écarté, et sans délai
        # hérité de l'ancien compte.
        assert again.attempts == queue.MAX_ATTEMPTS + 1
        assert await queue.retry_later(adb, again, {"reason": "x"}) == "pending"
        delay = db.execute(
            f"SELECT available_at - now() FROM {SCHEMA_NAME}.job_chunks WHERE id = %s", (chunk.id,)
        ).fetchone()
        assert delay is not None and delay[0] <= queue.RETRY_BASE_DELAY

    async def test_the_fencing_token_still_holds_across_a_retry(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Un worker de l'exécution précédente, revenu tard, ne peut pas écrire sur la nouvelle."""
        _enqueue(db, 1)
        stale = (await queue.claim(adb, "worker-a", 1))[0]
        db.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'error', lease_until = NULL WHERE id = %s", (stale.id,)
        )
        self._reopen_like_the_api(db, stale.id)
        await queue.claim(adb, "worker-b", 1)

        assert await queue.finish(adb, stale) is None


class TestLeaseRefresh:
    async def test_extends_the_lease_of_a_running_chunk(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        _enqueue(db, 1)
        chunk = (await queue.claim(adb, "worker-a", 1))[0]
        db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() + interval '5 seconds'")

        assert await queue.refresh_lease(adb, chunk)

        row = db.execute(f"SELECT extract(epoch FROM lease_until - now()) FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row is not None and float(row[0]) == pytest.approx(queue.LEASE_TTL.total_seconds(), abs=2)

    async def test_a_worker_cannot_extend_the_lease_of_its_successor(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Sinon un worker qui a perdu son chunk le garderait indéfiniment hors de portée."""
        _enqueue(db, 1)
        chunk = (await queue.claim(adb, "worker-a", 1))[0]
        await queue.release(adb, chunk)
        await queue.claim(adb, "worker-b", 1)

        assert await queue.refresh_lease(adb, chunk) is False


class TestOutcome:
    @dataclass(frozen=True)
    class Item:
        item_id: str
        reason: str
        detail: dict | None = None

    async def test_records_counts_and_quarantine(self, db: psycopg.Connection, adb: psycopg.AsyncConnection) -> None:
        _enqueue(db, 1, tasks_per_chunk=10)
        chunk = (await queue.claim(adb, "worker-a", 1))[0]

        await queue.finish(
            adb,
            chunk,
            produced=7,
            skipped=1,
            quarantined=[self.Item("a", "illisible"), self.Item("b", "illisible", {"code": 500})],
        )

        assert db.execute(f"SELECT produced, skipped FROM {SCHEMA_NAME}.job_chunks").fetchone() == (7, 1)
        items = db.execute(f"SELECT item_id, reason, detail FROM {SCHEMA_NAME}.job_items ORDER BY item_id").fetchall()
        assert items == [("a", "illisible", None), ("b", "illisible", {"code": 500})]

    async def test_produced_defaults_to_what_is_left(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        _enqueue(db, 1, tasks_per_chunk=10)
        chunk = (await queue.claim(adb, "worker-a", 1))[0]

        await queue.finish(adb, chunk, skipped=2, quarantined=[self.Item("a", "illisible")])

        assert db.execute(f"SELECT produced, skipped FROM {SCHEMA_NAME}.job_chunks").fetchone() == (7, 2)

    async def test_a_replayed_chunk_replaces_its_quarantine(
        self, db: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Le cas du `kill -9` entre l'écriture LanceDB et le commit : le chunk est refait."""
        job = _enqueue(db, 1, tasks_per_chunk=10)
        chunk = (await queue.claim(adb, "worker-a", 1))[0]
        await queue.finish(adb, chunk, quarantined=[self.Item("a", "première fois")])
        db.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'pending', produced = NULL, skipped = NULL")
        chunk = (await queue.claim(adb, "worker-b", 1))[0]

        await queue.finish(adb, chunk, quarantined=[self.Item("a", "seconde fois")])

        items = db.execute(f"SELECT item_id, reason FROM {SCHEMA_NAME}.job_items WHERE job_id = %s", (job,)).fetchall()
        assert items == [("a", "seconde fois")]
