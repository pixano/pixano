# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests de la boucle d'exécution : planification, exécution, annulation, reprise."""

import asyncio
import contextlib
import json

import psycopg
import pytest
from pixano_worker import queue, runner
from pixano_worker.kinds import Registry, default_registry
from pixano_worker.schema import NOTIFY_CHANNEL, SCHEMA_NAME
from psycopg_pool import AsyncConnectionPool


FAST = {"task_count": 200, "chunk_size": 20, "seconds_per_task": 0.0}


@pytest.fixture
def registry() -> Registry:
    """Le registre livré avec le worker."""
    return default_registry()


@pytest.fixture
def declared(db: psycopg.Connection, registry: Registry) -> psycopg.Connection:
    """Une base où ce worker a déclaré ce qu'il sait faire."""
    registry.declare(db, "worker-test")
    return db


def _submit(db: psycopg.Connection, params: dict | None = None, kind: str = "fake") -> str:
    from psycopg.types.json import Jsonb

    row = db.execute(
        f"INSERT INTO {SCHEMA_NAME}.jobs (kind, dataset, params) VALUES (%s, 'ds', %s) RETURNING id",
        (kind, Jsonb(params if params is not None else FAST)),
    ).fetchone()
    assert row is not None
    return str(row[0])


def _state(db: psycopg.Connection, job_id: str) -> tuple:
    row = db.execute(
        f"SELECT state, done_tasks, total_tasks FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job_id,)
    ).fetchone()
    assert row is not None
    return row


class TestDeclaration:
    def test_publishes_every_kind_with_its_parameter_schema(self, db: psycopg.Connection, registry: Registry) -> None:
        """C'est le seul pont entre l'application et le worker : ils ne partagent aucun code."""
        registry.declare(db, "worker-test")

        rows = db.execute(f"SELECT name, params_schema FROM {SCHEMA_NAME}.job_kinds ORDER BY name").fetchall()

        assert [row[0] for row in rows] == registry.names()
        published = dict(rows)
        assert published["fake"]["properties"]["task_count"]["type"] == "integer"

    def test_the_published_schema_refuses_an_unknown_parameter(self, registry: Registry) -> None:
        """C'est cette propriété qui permet à l'application d'attraper une faute de frappe.

        Sans `additionalProperties: false` dans le schéma publié, un paramètre mal
        orthographié passe la validation et se fait ignorer en silence à l'exécution.
        """
        kind = registry.get("fake")
        assert kind is not None

        assert kind.params_schema()["additionalProperties"] is False

    def test_an_unknown_parameter_is_refused_at_execution_too(self, registry: Registry) -> None:
        import pydantic

        kind = registry.get("fake")
        assert kind is not None

        with pytest.raises(pydantic.ValidationError):
            kind.validate_params({"task_count": 10, "tsak_size": 4})

    def test_declaring_again_refreshes_rather_than_duplicates(
        self, db: psycopg.Connection, registry: Registry
    ) -> None:
        """Un worker redéployé met son schéma à jour sans intervention."""
        registry.declare(db, "worker-a")
        registry.declare(db, "worker-b")

        row = db.execute(
            f"SELECT count(*), count(DISTINCT declared_by), max(declared_by) FROM {SCHEMA_NAME}.job_kinds"
        ).fetchone()
        assert row == (len(registry.names()), 1, "worker-b")


class TestPlanning:
    async def test_splits_a_job_into_chunks(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared)

        await runner.plan_one(adb, registry)

        assert _state(declared, job) == ("pending", 0, 200)
        row = declared.execute(
            f"SELECT count(*), sum(task_count) FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s", (job,)
        ).fetchone()
        assert row == (10, 200)

    async def test_nothing_to_plan_returns_nothing(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        assert await runner.plan_one(adb, registry) is None

    async def test_an_unknown_kind_fails_the_job_instead_of_stranding_it(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Sans ça, un job dont aucun worker ne connaît le type attendrait sans explication."""
        job = _submit(declared, kind="fantome")

        await runner.plan_one(adb, registry)

        state, _, _ = _state(declared, job)
        assert state == "error"
        row = declared.execute(f"SELECT error FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job,)).fetchone()
        assert row is not None and row[0]["kind"] == "fantome"

    async def test_invalid_parameters_fail_the_job(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={"task_count": -5})

        await runner.plan_one(adb, registry)

        assert _state(declared, job)[0] == "error"

    async def test_a_cancelled_job_is_never_planned(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Découper le travail d'un job qu'on vient d'arrêter n'a aucun sens."""
        job = _submit(declared)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))

        assert await runner.plan_one(adb, registry) is None
        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row is not None and row[0] == 0


class TestExecution:
    async def test_runs_a_job_to_completion(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """La première moitié de la DoD du lot : un job factice de 200 tâches va au bout."""
        job = _submit(declared)
        await runner.plan_one(adb, registry)

        while await runner.run_batch(adb, registry, "worker-test", 8):
            pass

        assert _state(declared, job) == ("done", 200, 200)

    async def test_reports_progress_as_it_goes(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared)
        await runner.plan_one(adb, registry)

        await runner.run_batch(adb, registry, "worker-test", 3)

        assert _state(declared, job)[1] == 60
        events = declared.execute(
            f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'progress' ORDER BY id",
            (job,),
        ).fetchall()
        assert [event[0]["done_tasks"] for event in events] == [20, 40, 60]

    async def test_progress_events_carry_absolute_counters(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Les identifiants de séquence sont attribués avant le commit : un lecteur peut en
        sauter un, et doit pouvoir s'en remettre au suivant. Des incréments l'interdiraient."""
        _submit(declared)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-test", 2)

        events = declared.execute(
            f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE type = 'progress' ORDER BY id"
        ).fetchall()
        assert all("total_tasks" in event[0] for event in events)
        assert [event[0]["done_tasks"] for event in events] == [20, 40]

    async def test_a_failing_chunk_fails_the_job(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={**FAST, "fail_at_chunk": 3})
        await runner.plan_one(adb, registry)

        while await runner.run_batch(adb, registry, "worker-test", 4):
            pass

        assert _state(declared, job)[0] == "error"

    async def test_the_other_chunks_still_run(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Un job ne s'arrête pas au premier item corrompu : il finit et rapporte."""
        _submit(declared, params={**FAST, "fail_at_chunk": 3})
        await runner.plan_one(adb, registry)

        while await runner.run_batch(adb, registry, "worker-test", 4):
            pass

        row = declared.execute(
            f"SELECT count(*) FILTER (WHERE state = 'done'), count(*) FILTER (WHERE state = 'error') "
            f"FROM {SCHEMA_NAME}.job_chunks"
        ).fetchone()
        assert row == (9, 1)


class TestCancellation:
    async def test_stops_between_batches(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """La deuxième partie de la DoD : une annulation en cours de route s'arrête proprement.

        Le worker voit l'annulation avant le chunk suivant : il le sort de la file plutôt que
        de l'exécuter, puis conclut le job.
        """
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-test", 3)

        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))
        while await runner.run_batch(adb, registry, "worker-test", 3):
            pass

        state, done, total = _state(declared, job)
        assert state == "cancelled"
        assert done == 60, "le travail déjà fait reste compté"
        assert total == 200

    async def test_a_cancelled_chunk_never_comes_back(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Le rendre « en attente » le ferait reréclamer sans fin, et le job ne conclurait jamais."""
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))

        tours = 0
        while await runner.run_batch(adb, registry, "worker-test", 4) and tours < 20:
            tours += 1

        assert tours < 20, "la boucle ne se termine pas"
        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'pending'").fetchone()
        assert row is not None and row[0] == 0

    async def test_work_already_done_is_not_undone(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-test", 2)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'cancelled' WHERE state = 'pending'")

        while await runner.run_batch(adb, registry, "worker-test", 3):
            pass

        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'done'").fetchone()
        assert row is not None and row[0] == 2


class TestRecovery:
    async def test_an_interrupted_job_resumes_where_it_stopped(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """La troisième partie de la DoD, simulée : un worker meurt, un autre reprend.

        Ce qu'un `kill -9` laisse derrière lui, ce sont des chunks en cours avec un bail. Le
        worker qui redémarre rend les siens ; ceux d'un worker qui ne revient pas expirent.
        """
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-mort", 2)
        await queue.claim(adb, "worker-mort", 3)

        released = await queue.release_own(adb, "worker-mort")
        assert released == 3
        while await runner.run_batch(adb, registry, "worker-vivant", 8):
            pass

        assert _state(declared, job) == ("done", 200, 200)

    async def test_no_task_is_counted_twice_after_a_resume(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Reprendre ne doit pas gonfler la progression au-delà du total."""
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        await runner.run_batch(adb, registry, "worker-mort", 4)
        await queue.claim(adb, "worker-mort", 2)
        await queue.release_own(adb, "worker-mort")

        while await runner.run_batch(adb, registry, "worker-vivant", 8):
            pass

        state, done, total = _state(declared, job)
        assert (state, done) == ("done", total)


class TestNotification:
    """La sonnette qui réveille l'interface."""

    async def test_an_event_rings_only_once_committed(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, postgres_url: str
    ) -> None:
        """PostgreSQL ne délivre un NOTIFY qu'au commit.

        C'est ce qui garantit qu'un lecteur réveillé trouve toujours la ligne en base — sans
        cette propriété il faudrait un accusé de réception applicatif.
        """
        job = _submit(declared)

        with psycopg.connect(postgres_url, autocommit=True) as listener:
            listener.execute(f"LISTEN {NOTIFY_CHANNEL}")

            async with await psycopg.AsyncConnection.connect(postgres_url) as writer:
                await runner.record_event(writer, job, "state", {"state": "planning"})
                assert list(listener.notifies(timeout=0.3)) == [], "rien ne doit sonner avant le commit"
                await writer.commit()

            received = list(listener.notifies(timeout=3, stop_after=1))

        assert len(received) == 1
        payload = json.loads(received[0].payload)
        assert payload["job_id"] == job
        assert payload["type"] == "state"
        assert isinstance(payload["event_id"], int)

    async def test_the_payload_carries_identifiers_only(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, postgres_url: str
    ) -> None:
        """La charge d'un NOTIFY est plafonnée à 8 ko : y mettre le contenu serait un piège
        qui se déclencherait le jour d'un message d'erreur un peu long."""
        job = _submit(declared)

        with psycopg.connect(postgres_url, autocommit=True) as listener:
            listener.execute(f"LISTEN {NOTIFY_CHANNEL}")
            async with await psycopg.AsyncConnection.connect(postgres_url, autocommit=True) as writer:
                await runner.record_event(writer, job, "progress", {"done_tasks": 40, "total_tasks": 200})
            received = list(listener.notifies(timeout=3, stop_after=1))

        assert set(json.loads(received[0].payload)) == {"job_id", "event_id", "type"}


class TestConcurrency:
    """Plusieurs chunks en vol, sans jamais en tenir plus que permis."""

    @staticmethod
    async def _run_until_settled(pool, registry: Registry, declared: psycopg.Connection, job: str, concurrency: int):
        """Faire tourner la boucle réelle jusqu'à ce que le job conclue, en relevant l'occupation."""
        worker = asyncio.create_task(runner.work(pool, registry, "worker-test", concurrency, idle_poll_s=0.05))
        peak = 0
        try:
            for _ in range(400):
                running = declared.execute(
                    f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'running'"
                ).fetchone()
                peak = max(peak, running[0] if running else 0)
                if _state(declared, job)[0] in ("done", "error", "cancelled"):
                    break
                await asyncio.sleep(0.02)
        finally:
            worker.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await worker
        return peak

    async def test_runs_several_chunks_at_once(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        """Le plafond est atteint, et jamais dépassé.

        Chaque chunk dort un dixième de seconde : assez pour que la sonde voie les chunks se
        chevaucher, si la boucle les chevauche vraiment.
        """
        job = _submit(declared, params={"task_count": 200, "chunk_size": 20, "seconds_per_task": 0.005})

        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=5, kwargs={"autocommit": True}) as pool:
            peak = await self._run_until_settled(pool, registry, declared, job, concurrency=4)

        assert _state(declared, job) == ("done", 200, 200)
        assert 2 <= peak <= 4, f"occupation maximale observée : {peak}"

    async def test_a_single_slot_runs_one_chunk_at_a_time(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        job = _submit(declared, params={"task_count": 100, "chunk_size": 20, "seconds_per_task": 0.005})

        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=2, kwargs={"autocommit": True}) as pool:
            peak = await self._run_until_settled(pool, registry, declared, job, concurrency=1)

        assert _state(declared, job) == ("done", 100, 100)
        assert peak == 1

    async def test_no_task_is_counted_twice_under_concurrency(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        """Les progressions de chunks concurrents s'additionnent sans se marcher dessus."""
        job = _submit(declared, params={"task_count": 500, "chunk_size": 10, "seconds_per_task": 0.0})

        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=9, kwargs={"autocommit": True}) as pool:
            await self._run_until_settled(pool, registry, declared, job, concurrency=8)

        assert _state(declared, job) == ("done", 500, 500)
        events = declared.execute(
            f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'progress'", (job,)
        ).fetchall()
        assert len(events) == 50
        assert max(event[0]["done_tasks"] for event in events) == 500
