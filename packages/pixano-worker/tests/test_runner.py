# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests de la boucle d'exécution : planification, exécution, annulation, reprise."""

import asyncio
import contextlib
import json
import threading
from datetime import timedelta

import psycopg
import pytest
from pixano_worker import queue, runner
from pixano_worker.kinds import Chunk, FakeKind, Outcome, Registry, default_registry
from pixano_worker.schema import NOTIFY_CHANNEL, SCHEMA_NAME
from pixano_worker.threads import WorkerSaturatedError, WorkerThreads
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


class TestInterruptedPlanning:
    """Un worker qui meurt en pleine découpe ne doit pas laisser le job bloqué pour toujours."""

    @staticmethod
    def _claim_planning_and_die(declared: psycopg.Connection) -> None:
        """Ce qu'un worker laisse derrière lui s'il meurt juste après avoir réclamé la découpe."""
        declared.execute(runner.CLAIM_PLANNING, (queue.LEASE_TTL,))

    async def test_the_job_stays_in_planning_while_it_is_split(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Il était passé « en cours » avant même d'avoir un chunk — un état qu'aucune reprise ne voyait."""
        job = _submit(declared)

        self._claim_planning_and_die(declared)

        assert _state(declared, job)[0] == "planning"

    async def test_a_live_planning_lease_is_respected(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        _submit(declared)
        self._claim_planning_and_die(declared)

        assert await runner.plan_one(adb, registry) is None

    async def test_a_job_whose_planner_died_is_planned_again(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared)
        self._claim_planning_and_die(declared)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET planning_until = now() - interval '1 minute'")

        await runner.plan_one(adb, registry)

        assert _state(declared, job) == ("pending", 0, 200)

    async def test_a_second_planner_does_not_double_the_chunks(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Le premier planificateur, trop lent, finit après celui qui a repris son bail."""
        job = _submit(declared)
        await runner.plan_one(adb, registry)
        late_chunks = [Chunk(payload={"first_task": 0, "task_count": 200}, task_count=200)]

        recorded = await runner.record_plan(adb, job, late_chunks)

        assert recorded is False
        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s", (job,)).fetchone()
        assert row == (10,)


class TestCancelledDuringPlanning:
    """Revue de l'étape 1 : une annulation pendant la découpe ressuscitait le job en `pending`."""

    @staticmethod
    def _cancel_as_the_application_does(declared: psycopg.Connection, job: str) -> None:
        declared.execute(
            f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now(), state = 'cancelled', "
            "planning_until = NULL WHERE id = %s",
            (job,),
        )

    async def test_a_plan_finished_after_a_cancel_is_dropped(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        job = _submit(declared)
        declared.execute(runner.CLAIM_PLANNING, (queue.LEASE_TTL,))
        self._cancel_as_the_application_does(declared, job)

        recorded = await runner.record_plan(adb, job, [Chunk(payload={"first_task": 0}, task_count=200)])

        assert recorded is False
        assert _state(declared, job)[0] == "cancelled"
        chunks = declared.execute(
            f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s", (job,)
        ).fetchone()
        assert chunks == (0,)
        states = declared.execute(
            f"SELECT payload->>'state' FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'state'", (job,)
        ).fetchall()
        assert ("pending",) not in states, "aucun événement ne doit annoncer le job de nouveau en attente"

    async def test_a_planning_failure_after_a_cancel_does_not_turn_it_into_an_error(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Un job qu'on a arrêté n'est pas un job qui a échoué."""
        job = _submit(declared)
        declared.execute(runner.CLAIM_PLANNING, (queue.LEASE_TTL,))
        self._cancel_as_the_application_does(declared, job)

        await runner._fail_job(adb, job, {"reason": "la planification a échoué"})

        assert _state(declared, job)[0] == "cancelled"


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

    async def test_the_job_announces_once_that_it_is_running(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Sans cet événement, l'interface affiche « pending » sous une barre qui avance.

        Vu dans le navigateur au lot 11 : le job passait bien en cours en base, sans que rien ne
        le dise au flux.
        """
        job = _submit(declared)
        await runner.plan_one(adb, registry)

        while await runner.run_batch(adb, registry, "worker-test", 8):
            pass

        states = declared.execute(
            f"SELECT payload->>'state' FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'state' ORDER BY id",
            (job,),
        ).fetchall()
        assert [row[0] for row in states] == ["pending", "running", "done"]

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

        recovery = await queue.release_own(adb, "worker-mort")
        assert recovery.requeued == 3
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


class TestAbandonedChunk:
    """Revue de l'étape 1 : un chunk écarté par la reprise ne concluait pas son job."""

    async def test_a_job_whose_last_chunk_is_set_aside_ends_in_error(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.0})
        await runner.plan_one(adb, registry)
        for _ in range(queue.MAX_ATTEMPTS):
            await queue.claim(adb, "worker-qui-meurt", 1)
            declared.execute(
                f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() - interval '1 minute' "
                "WHERE state = 'running'"
            )
            recovery = await queue.reclaim_expired(adb)

        await runner.settle_abandoned(adb, recovery)

        assert _state(declared, job)[0] == "error"


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


async def _drain(adb: psycopg.AsyncConnection, registry: Registry) -> None:
    while await runner.run_batch(adb, registry, "worker-test", 8):
        pass


class TestTransientFailures:
    """Une panne passagère n'est pas un échec du job."""

    async def test_the_chunk_is_retried_later_instead_of_failing_the_job(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={**FAST, "transient_at_chunk": 3})
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        assert _state(declared, job)[0] == "running", "le job attend son chunk rejoué, il n'a pas échoué"
        row = declared.execute(
            f"SELECT state, attempts, error->>'reason' FROM {SCHEMA_NAME}.job_chunks WHERE seq = 3"
        ).fetchone()
        assert row == ("pending", 1, "panne passagère")

    async def test_the_job_completes_once_the_failure_has_passed(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={**FAST, "transient_at_chunk": 3})
        await runner.plan_one(adb, registry)
        await _drain(adb, registry)

        # La panne est passée : le même job, sans la panne, et le délai écoulé.
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET params = params - 'transient_at_chunk' WHERE id = %s", (job,))
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET available_at = now()")
        await _drain(adb, registry)

        assert _state(declared, job) == ("done", 200, 200)

    async def test_a_failure_that_never_passes_ends_in_error(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={**FAST, "transient_at_chunk": 3})
        await runner.plan_one(adb, registry)

        for _ in range(queue.MAX_ATTEMPTS):
            await _drain(adb, registry)
            declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET available_at = now()")

        assert _state(declared, job)[0] == "error"
        row = declared.execute(f"SELECT state, attempts FROM {SCHEMA_NAME}.job_chunks WHERE seq = 3").fetchone()
        assert row == ("error", queue.MAX_ATTEMPTS)


class TestOutcome:
    """Un job dit ce qu'il a produit, pas seulement ce qu'il a tenté."""

    async def test_the_final_event_carries_the_outcome(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        job = _submit(declared, params={**FAST, "skip_per_chunk": 3, "quarantine_per_chunk": 1})
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        assert _state(declared, job) == ("done", 200, 200)
        final = declared.execute(
            f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'state' "
            "ORDER BY id DESC LIMIT 1",
            (job,),
        ).fetchone()
        assert final is not None
        assert final[0] == {"state": "done", "produced": 160, "skipped": 30, "quarantined": 10}

    async def test_quarantined_items_can_be_read_back(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Une quarantaine qu'on ne peut pas relire ne sert à rien."""
        job = _submit(declared, params={**FAST, "quarantine_per_chunk": 1})
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        items = declared.execute(
            f"SELECT item_id, reason FROM {SCHEMA_NAME}.job_items WHERE job_id = %s ORDER BY item_id", (job,)
        ).fetchall()
        assert len(items) == 10
        assert items[0] == ("task-0", "failure requested")

    async def test_an_outcome_that_does_not_add_up_fails_the_chunk(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection
    ) -> None:
        """Un bilan faux fausserait tout ce qu'on affiche du job : c'est un défaut du type."""

        class Miscounting(FakeKind):
            def outcome(self, result, payload, task_count):  # noqa: ANN001, ANN202, D102
                return Outcome(produced=task_count - 1)

        registry = Registry()
        registry.register(Miscounting())
        job = _submit(declared)
        await runner.plan_one(adb, registry)

        await _drain(adb, registry)

        assert _state(declared, job)[0] == "error"
        row = declared.execute(f"SELECT error->>'reason' FROM {SCHEMA_NAME}.job_chunks LIMIT 1").fetchone()
        assert row is not None and "bilan" in row[0]


class TestChunkTimeLimit:
    async def test_a_chunk_over_its_time_limit_is_sent_back(
        self, declared: psycopg.Connection, adb: psycopg.AsyncConnection, registry: Registry
    ) -> None:
        """Le worker est vivant, la sonde de docker ne voit rien : seul ce plafond rend le chunk."""
        job = _submit(declared, params={"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.05})
        await runner.plan_one(adb, registry)
        chunk = (await queue.claim(adb, "worker-test", 1))[0]

        await runner.run_chunk(adb, registry, chunk, timeout_s=0.1)

        row = declared.execute(f"SELECT state, error->>'reason' FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row == ("pending", "durée maximale dépassée")
        assert _state(declared, job)[0] == "pending"


class TestLeaseKeptWhileRunning:
    async def test_a_long_chunk_keeps_its_lease(
        self,
        declared: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Sans rafraîchissement, un chunk plus long que son bail serait repris en plein vol."""
        monkeypatch.setattr(queue, "LEASE_REFRESH_INTERVAL", timedelta(milliseconds=50))
        _submit(declared, params={"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.02})
        await runner.plan_one(adb, registry)
        chunk = (await queue.claim(adb, "worker-test", 1))[0]
        # Un bail presque échu, qui expirerait bien avant la fin du chunk s'il n'était pas prolongé.
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET lease_until = now() + interval '200 milliseconds'")

        running = asyncio.create_task(runner.run_chunk(adb, registry, chunk))
        await asyncio.sleep(0.25)
        lease = declared.execute(
            f"SELECT extract(epoch FROM lease_until - now()) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'running'"
        ).fetchone()
        await running

        assert lease is not None and float(lease[0]) > 60, "le bail a été prolongé pendant l'exécution"
        row = declared.execute(f"SELECT state FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row == ("done",)


class TestLeaseRefreshOutage:
    """Seconde revue : un rafraîchissement de bail raté classait un chunk réussi comme fatal."""

    async def test_a_chunk_whose_work_succeeded_is_done_despite_a_failed_refresh(
        self,
        declared: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(queue, "LEASE_REFRESH_INTERVAL", timedelta(milliseconds=30))
        job = _submit(declared, params={"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.01})
        await runner.plan_one(adb, registry)
        chunk = (await queue.claim(adb, "worker-test", 1))[0]
        real_refresh = queue.refresh_lease
        outages = {"left": 2}

        async def flaky_refresh(conn: psycopg.AsyncConnection, c: queue.Chunk) -> bool:
            if outages["left"] > 0:
                outages["left"] -= 1
                raise psycopg.OperationalError("terminating connection due to administrator command")
            return await real_refresh(conn, c)

        monkeypatch.setattr(queue, "refresh_lease", flaky_refresh)

        await runner.run_chunk(adb, registry, chunk)

        assert outages["left"] == 0, "les coupures simulées ont bien eu lieu"
        assert _state(declared, job) == ("done", 20, 20)


class TestSaturation:
    """Revue de l'étape 1 : des threads bloqués immobilisaient le worker, toujours « healthy »."""

    async def test_the_loop_stops_the_worker_once_too_many_threads_are_stuck(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        threads = WorkerThreads(workers=2, stuck_limit=1)
        release = threading.Event()
        with pytest.raises(TimeoutError):
            await threads.run(release.wait, timeout_s=0.01)

        try:
            async with AsyncConnectionPool(postgres_url, min_size=1, max_size=2, kwargs={"autocommit": True}) as pool:
                with pytest.raises(WorkerSaturatedError):
                    await asyncio.wait_for(
                        runner.work(pool, registry, "worker-test", 1, idle_poll_s=0.01, threads=threads), timeout=5
                    )
        finally:
            release.set()


class TestDatabaseOutage:
    """Vu sur la pile réelle : un `docker compose restart postgres` tuait le worker pour de bon."""

    async def test_the_loop_waits_for_the_database_instead_of_dying(
        self,
        declared: psycopg.Connection,
        postgres_url: str,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        job = _submit(declared, params={"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0})
        real_plan_one = runner.plan_one
        outages = {"left": 3}

        async def flaky_plan_one(*args: object, **kwargs: object) -> str | None:
            if outages["left"] > 0:
                outages["left"] -= 1
                raise psycopg.errors.AdminShutdown("terminating connection due to administrator command")
            return await real_plan_one(*args, **kwargs)  # type: ignore[arg-type]

        monkeypatch.setattr(runner, "plan_one", flaky_plan_one)
        monkeypatch.setattr(runner, "OUTAGE_BACKOFF_S", (0.01,))

        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=3, kwargs={"autocommit": True}) as pool:
            await TestConcurrency._run_until_settled(pool, registry, declared, job, concurrency=2)

        assert outages["left"] == 0, "les coupures simulées ont bien eu lieu"
        assert _state(declared, job) == ("done", 40, 40)


class TestGracefulShutdown:
    """Revue de l'étape 1 : `docker compose stop` coupait les chunks en cours sans les rendre."""

    async def test_an_idle_worker_stops_at_once(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        """Pas d'attente de la pause en cours : docker ne doit pas attendre pour rien."""
        stop = asyncio.Event()
        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=2, kwargs={"autocommit": True}) as pool:
            worker = asyncio.create_task(runner.work(pool, registry, "worker-test", 1, idle_poll_s=60, stop=stop))
            await asyncio.sleep(0.2)

            stop.set()

            await asyncio.wait_for(worker, timeout=2)

    async def test_chunks_in_flight_finish_and_nothing_new_is_claimed(
        self, declared: psycopg.Connection, postgres_url: str, registry: Registry
    ) -> None:
        job = _submit(declared, params={"task_count": 200, "chunk_size": 20, "seconds_per_task": 0.01})
        stop = asyncio.Event()
        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=3, kwargs={"autocommit": True}) as pool:
            worker = asyncio.create_task(runner.work(pool, registry, "worker-test", 2, idle_poll_s=0.05, stop=stop))
            for _ in range(200):
                if _state(declared, job)[1] >= 40:
                    break
                await asyncio.sleep(0.02)

            stop.set()
            await asyncio.wait_for(worker, timeout=5)

        states = dict(
            declared.execute(f"SELECT state, count(*) FROM {SCHEMA_NAME}.job_chunks GROUP BY state").fetchall()
        )
        assert "running" not in states, "les chunks en vol ont fini avant l'arrêt"
        assert states.get("pending", 0) > 0, "rien de nouveau n'a été réclamé après la demande d'arrêt"

    async def test_chunks_that_outlast_the_grace_are_left_to_be_handed_back(
        self,
        declared: psycopg.Connection,
        adb: psycopg.AsyncConnection,
        postgres_url: str,
        registry: Registry,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(runner, "SHUTDOWN_GRACE_S", 0.05)
        _submit(declared, params={"task_count": 20, "chunk_size": 20, "seconds_per_task": 0.1})
        stop = asyncio.Event()
        async with AsyncConnectionPool(postgres_url, min_size=1, max_size=2, kwargs={"autocommit": True}) as pool:
            worker = asyncio.create_task(runner.work(pool, registry, "worker-test", 1, idle_poll_s=0.05, stop=stop))
            for _ in range(100):
                running = declared.execute(
                    f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'running'"
                ).fetchone()
                if running and running[0]:
                    break
                await asyncio.sleep(0.02)

            stop.set()
            await asyncio.wait_for(worker, timeout=2)

        recovery = await queue.release_own(adb, "worker-test")

        assert recovery.requeued == 1
