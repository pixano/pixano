# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests de la boucle d'exécution : planification, exécution, annulation, reprise."""

import psycopg
import pytest
from pixano_worker import queue, runner
from pixano_worker.kinds import Registry, default_registry
from pixano_worker.schema import SCHEMA_NAME


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

        row = db.execute(f"SELECT name, params_schema FROM {SCHEMA_NAME}.job_kinds").fetchone()
        assert row is not None
        assert row[0] == "fake"
        assert row[1]["properties"]["task_count"]["type"] == "integer"

    def test_declaring_again_refreshes_rather_than_duplicates(
        self, db: psycopg.Connection, registry: Registry
    ) -> None:
        """Un worker redéployé met son schéma à jour sans intervention."""
        registry.declare(db, "worker-a")
        registry.declare(db, "worker-b")

        row = db.execute(f"SELECT count(*), max(declared_by) FROM {SCHEMA_NAME}.job_kinds").fetchone()
        assert row == (1, "worker-b")


class TestPlanning:
    def test_splits_a_job_into_chunks(self, declared: psycopg.Connection, registry: Registry) -> None:
        job = _submit(declared)

        runner.plan_one(declared, registry)

        assert _state(declared, job) == ("pending", 0, 200)
        row = declared.execute(
            f"SELECT count(*), sum(task_count) FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s", (job,)
        ).fetchone()
        assert row == (10, 200)

    def test_nothing_to_plan_returns_nothing(self, declared: psycopg.Connection, registry: Registry) -> None:
        assert runner.plan_one(declared, registry) is None

    def test_an_unknown_kind_fails_the_job_instead_of_stranding_it(
        self, declared: psycopg.Connection, registry: Registry
    ) -> None:
        """Sans ça, un job dont aucun worker ne connaît le type attendrait sans explication."""
        job = _submit(declared, kind="fantome")

        runner.plan_one(declared, registry)

        state, _, _ = _state(declared, job)
        assert state == "error"
        row = declared.execute(f"SELECT error FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job,)).fetchone()
        assert row is not None and row[0]["kind"] == "fantome"

    def test_invalid_parameters_fail_the_job(self, declared: psycopg.Connection, registry: Registry) -> None:
        job = _submit(declared, params={"task_count": -5})

        runner.plan_one(declared, registry)

        assert _state(declared, job)[0] == "error"

    def test_a_cancelled_job_is_never_planned(self, declared: psycopg.Connection, registry: Registry) -> None:
        """Découper le travail d'un job qu'on vient d'arrêter n'a aucun sens."""
        job = _submit(declared)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))

        assert runner.plan_one(declared, registry) is None
        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row is not None and row[0] == 0


class TestExecution:
    def test_runs_a_job_to_completion(self, declared: psycopg.Connection, registry: Registry) -> None:
        """La première moitié de la DoD du lot : un job factice de 200 tâches va au bout."""
        job = _submit(declared)
        runner.plan_one(declared, registry)

        while runner.run_batch(declared, registry, "worker-test", 8):
            pass

        assert _state(declared, job) == ("done", 200, 200)

    def test_reports_progress_as_it_goes(self, declared: psycopg.Connection, registry: Registry) -> None:
        job = _submit(declared)
        runner.plan_one(declared, registry)

        runner.run_batch(declared, registry, "worker-test", 3)

        assert _state(declared, job)[1] == 60
        events = declared.execute(
            f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE job_id = %s AND type = 'progress' " "ORDER BY id",
            (job,),
        ).fetchall()
        assert [event[0]["done_tasks"] for event in events] == [20, 40, 60]

    def test_progress_events_carry_absolute_counters(self, declared: psycopg.Connection, registry: Registry) -> None:
        """Les identifiants de séquence sont attribués avant le commit : un lecteur peut en
        sauter un, et doit pouvoir s'en remettre au suivant. Des incréments l'interdiraient."""
        _submit(declared)
        runner.plan_one(declared, registry)
        runner.run_batch(declared, registry, "worker-test", 2)

        events = declared.execute(
            f"SELECT payload FROM {SCHEMA_NAME}.job_events WHERE type = 'progress' ORDER BY id"
        ).fetchall()
        assert all("total_tasks" in event[0] for event in events)
        assert [event[0]["done_tasks"] for event in events] == [20, 40]

    def test_a_failing_chunk_fails_the_job(self, declared: psycopg.Connection, registry: Registry) -> None:
        job = _submit(declared, params={**FAST, "fail_at_chunk": 3})
        runner.plan_one(declared, registry)

        while runner.run_batch(declared, registry, "worker-test", 4):
            pass

        assert _state(declared, job)[0] == "error"

    def test_the_other_chunks_still_run(self, declared: psycopg.Connection, registry: Registry) -> None:
        """Un job ne s'arrête pas au premier item corrompu : il finit et rapporte."""
        _submit(declared, params={**FAST, "fail_at_chunk": 3})
        runner.plan_one(declared, registry)

        while runner.run_batch(declared, registry, "worker-test", 4):
            pass

        row = declared.execute(
            f"SELECT count(*) FILTER (WHERE state = 'done'), count(*) FILTER (WHERE state = 'error') "
            f"FROM {SCHEMA_NAME}.job_chunks"
        ).fetchone()
        assert row == (9, 1)


class TestCancellation:
    def test_stops_between_batches(self, declared: psycopg.Connection, registry: Registry) -> None:
        """La deuxième partie de la DoD : une annulation en cours de route s'arrête proprement.

        Le worker voit l'annulation au lot suivant : il sort ses chunks de la file plutôt que
        de les exécuter, puis conclut le job.
        """
        job = _submit(declared)
        runner.plan_one(declared, registry)
        runner.run_batch(declared, registry, "worker-test", 3)

        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))
        while runner.run_batch(declared, registry, "worker-test", 3):
            pass

        state, done, total = _state(declared, job)
        assert state == "cancelled"
        assert done == 60, "le travail déjà fait reste compté"
        assert total == 200

    def test_a_cancelled_chunk_never_comes_back(self, declared: psycopg.Connection, registry: Registry) -> None:
        """Le rendre « en attente » le ferait reréclamer sans fin, et le job ne conclurait jamais."""
        job = _submit(declared)
        runner.plan_one(declared, registry)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))

        tours = 0
        while runner.run_batch(declared, registry, "worker-test", 4) and tours < 20:
            tours += 1

        assert tours < 20, "la boucle ne se termine pas"
        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'pending'").fetchone()
        assert row is not None and row[0] == 0

    def test_work_already_done_is_not_undone(self, declared: psycopg.Connection, registry: Registry) -> None:
        job = _submit(declared)
        runner.plan_one(declared, registry)
        runner.run_batch(declared, registry, "worker-test", 2)
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET cancel_requested_at = now() WHERE id = %s", (job,))
        declared.execute(f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'cancelled' WHERE state = 'pending'")

        while runner.run_batch(declared, registry, "worker-test", 3):
            pass

        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE state = 'done'").fetchone()
        assert row is not None and row[0] == 2


class TestRecovery:
    def test_an_interrupted_job_resumes_where_it_stopped(
        self, declared: psycopg.Connection, registry: Registry
    ) -> None:
        """La troisième partie de la DoD, simulée : un worker meurt, un autre reprend.

        Ce qu'un `kill -9` laisse derrière lui, ce sont des chunks en cours avec un bail. Le
        worker qui redémarre rend les siens ; ceux d'un worker qui ne revient pas expirent.
        """
        job = _submit(declared)
        runner.plan_one(declared, registry)
        runner.run_batch(declared, registry, "worker-mort", 2)
        queue.claim(declared, "worker-mort", 3)

        released = queue.release_own(declared, "worker-mort")
        assert released == 3
        while runner.run_batch(declared, registry, "worker-vivant", 8):
            pass

        assert _state(declared, job) == ("done", 200, 200)

    def test_no_task_is_counted_twice_after_a_resume(self, declared: psycopg.Connection, registry: Registry) -> None:
        """Reprendre ne doit pas gonfler la progression au-delà du total."""
        job = _submit(declared)
        runner.plan_one(declared, registry)
        runner.run_batch(declared, registry, "worker-mort", 4)
        queue.claim(declared, "worker-mort", 2)
        queue.release_own(declared, "worker-mort")

        while runner.run_batch(declared, registry, "worker-vivant", 8):
            pass

        state, done, total = _state(declared, job)
        assert (state, done) == ("done", total)
