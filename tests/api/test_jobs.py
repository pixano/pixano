# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests for recording job requests on the queue."""

import os

import psycopg
import pytest
from psycopg.types.json import Jsonb

from pixano.api import jobs
from pixano.api.jobs import SCHEMA_NAME


TEST_DATABASE_URL = "PIXANO_TEST_DATABASE_URL"

# The shape a worker publishes for a kind, reduced to what these tests need.
FAKE_SCHEMA = {
    "type": "object",
    "properties": {"task_count": {"type": "integer", "minimum": 1}},
    "required": ["task_count"],
    "additionalProperties": False,
}


@pytest.fixture
def queue() -> psycopg.Connection:
    """A connection to a throwaway queue, emptied around each test.

    Keyed on a dedicated variable, never PIXANO_DATABASE_URL: a developer running the stack
    has that one exported, and these tests delete rows.
    """
    url = os.environ.get(TEST_DATABASE_URL, "")
    if not url:
        pytest.skip(f"{TEST_DATABASE_URL} not set")
    with psycopg.connect(url, autocommit=True) as conn:
        exists = conn.execute(f"SELECT to_regclass('{SCHEMA_NAME}.jobs')").fetchone()
        if exists is None or exists[0] is None:
            pytest.skip("the queue schema is absent — pixano-worker installs it")
        conn.execute(f"TRUNCATE {SCHEMA_NAME}.jobs, {SCHEMA_NAME}.job_kinds CASCADE")
        yield conn
        conn.execute(f"TRUNCATE {SCHEMA_NAME}.jobs, {SCHEMA_NAME}.job_kinds CASCADE")


@pytest.fixture
def declared(queue: psycopg.Connection) -> psycopg.Connection:
    """A queue where a worker has declared it can run the fake kind."""
    queue.execute(
        f"INSERT INTO {SCHEMA_NAME}.job_kinds (name, params_schema, declared_by) VALUES (%s, %s, %s)",
        ("fake", Jsonb(FAKE_SCHEMA), "worker-test"),
    )
    return queue


class TestConnect:
    """A missing queue is a deployment state, not a crash."""

    def test_no_configured_url_is_refused_clearly(self) -> None:
        with pytest.raises(jobs.QueueUnavailableError, match="PIXANO_DATABASE_URL"):
            jobs.connect(None)

    def test_an_unreachable_database_is_refused_clearly(self) -> None:
        with pytest.raises(jobs.QueueUnavailableError, match="unreachable"):
            jobs.connect("postgresql://nobody@127.0.0.1:1/none?connect_timeout=1")


class TestAvailableKinds:
    def test_an_empty_registry_means_nothing_can_run(self, queue: psycopg.Connection) -> None:
        assert jobs.available_kinds(queue) == {}

    def test_reports_what_a_worker_declared(self, declared: psycopg.Connection) -> None:
        assert jobs.available_kinds(declared) == {"fake": FAKE_SCHEMA}


class TestValidation:
    """Refusing at submission beats queueing a job that cannot succeed."""

    def test_an_undeclared_kind_is_refused(self, declared: psycopg.Connection) -> None:
        with pytest.raises(jobs.UnknownKindError, match="ghost"):
            jobs.check_params(declared, "ghost", {})

    def test_the_refusal_names_what_is_available(self, declared: psycopg.Connection) -> None:
        with pytest.raises(jobs.UnknownKindError, match="fake"):
            jobs.check_params(declared, "ghost", {})

    def test_params_must_match_the_declared_schema(self, declared: psycopg.Connection) -> None:
        with pytest.raises(jobs.InvalidParamsError):
            jobs.check_params(declared, "fake", {"task_count": "beaucoup"})

    def test_a_missing_required_parameter_is_refused(self, declared: psycopg.Connection) -> None:
        with pytest.raises(jobs.InvalidParamsError):
            jobs.check_params(declared, "fake", {})

    def test_an_unexpected_parameter_is_refused(self, declared: psycopg.Connection) -> None:
        """A typo in a parameter name would otherwise be silently ignored by the worker."""
        with pytest.raises(jobs.InvalidParamsError):
            jobs.check_params(declared, "fake", {"task_count": 10, "tsak_size": 4})

    def test_valid_params_pass(self, declared: psycopg.Connection) -> None:
        jobs.check_params(declared, "fake", {"task_count": 10})


class TestSubmit:
    def test_records_the_request_without_chunks(self, declared: psycopg.Connection) -> None:
        """The worker splits the work; the application only records what was asked."""
        job = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 50})

        assert job.state == "planning"
        assert job.total_tasks == 0
        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks").fetchone()
        assert row is not None and row[0] == 0

    def test_stores_the_parameters_as_given(self, declared: psycopg.Connection) -> None:
        params = {"task_count": 7}

        job = jobs.submit(declared, kind="fake", dataset_id="ds", params=params)

        row = declared.execute(f"SELECT params FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job.id,)).fetchone()
        assert row is not None and row[0] == params

    def test_nothing_is_written_when_the_kind_is_unknown(self, declared: psycopg.Connection) -> None:
        with pytest.raises(jobs.UnknownKindError):
            jobs.submit(declared, kind="ghost", dataset_id="ds")

        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.jobs").fetchone()
        assert row is not None and row[0] == 0

    def test_nothing_is_written_when_the_params_are_invalid(self, declared: psycopg.Connection) -> None:
        with pytest.raises(jobs.InvalidParamsError):
            jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": -1})

        row = declared.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.jobs").fetchone()
        assert row is not None and row[0] == 0


class TestReadAndCancel:
    def test_reads_a_job_back(self, declared: psycopg.Connection) -> None:
        job = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 5})

        assert jobs.get(declared, job.id) == job

    def test_an_unknown_job_is_reported_as_missing(self, declared: psycopg.Connection) -> None:
        with pytest.raises(jobs.JobNotFoundError):
            jobs.get(declared, "00000000-0000-0000-0000-000000000000")

    def test_lists_the_most_recent_first(self, declared: psycopg.Connection) -> None:
        first = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 1})
        second = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 1})

        assert [job.id for job in jobs.list_jobs(declared)][:2] == [second.id, first.id]

    def test_cancelling_a_job_not_yet_planned_settles_it(self, declared: psycopg.Connection) -> None:
        """A job cancelled before the worker reached it has nothing in flight to wait for."""
        job = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 5})

        cancelled = jobs.cancel(declared, job.id)

        assert cancelled.state == "cancelled"

    def test_a_new_job_has_no_cancellation_requested(self, declared: psycopg.Connection) -> None:
        job = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 5})

        assert job.cancel_requested is False
        assert jobs.get(declared, job.id).cancel_requested is False

    def test_a_job_being_planned_can_be_cancelled(self, declared: psycopg.Connection) -> None:
        """Second review of step 1: this answered 500 with a CheckViolation.

        A job claimed by a planner carries a planning lease, and the schema refuses a lease
        outside the planning state. The first test of this case simulated the cancellation by
        hand and cleared the lease itself — which is exactly what hid the defect.
        """
        job = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 5})
        declared.execute(
            f"UPDATE {SCHEMA_NAME}.jobs SET planning_until = now() + interval '2 minutes' WHERE id = %s", (job.id,)
        )

        cancelled = jobs.cancel(declared, job.id)

        assert cancelled.state == "cancelled"

    def test_a_running_job_reports_its_cancellation_before_it_ends(self, declared: psycopg.Connection) -> None:
        """The chunks in flight finish before the job settles; the request must be visible meanwhile."""
        job = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 5})
        declared.execute(f"UPDATE {SCHEMA_NAME}.jobs SET state = 'running' WHERE id = %s", (job.id,))
        declared.execute(
            f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count, state, lease_until) "
            "VALUES (%s, 0, 5, 'running', now() + interval '2 minutes')",
            (job.id,),
        )

        cancelled = jobs.cancel(declared, job.id)

        assert (cancelled.state, cancelled.cancel_requested) == ("running", True)

    def test_cancelling_twice_is_harmless(self, declared: psycopg.Connection) -> None:
        job = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 1})

        jobs.cancel(declared, job.id)

        assert jobs.cancel(declared, job.id).state == "cancelled"


class TestOutcome:
    """A job says what it produced, not only what it attempted."""

    @staticmethod
    def _worker_finishes(
        queue: psycopg.Connection, job_id: str, produced: int, skipped: int, failed: list[str]
    ) -> None:
        """Write what the worker writes once a chunk is done."""
        task_count = produced + skipped + len(failed)
        row = queue.execute(
            f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count, state, produced, skipped) "
            "VALUES (%s, (SELECT count(*) FROM pixano_jobs.job_chunks WHERE job_id = %s), %s, 'done', %s, %s) "
            "RETURNING id",
            (job_id, job_id, task_count, produced, skipped),
        ).fetchone()
        assert row is not None
        for item in failed:
            queue.execute(
                f"INSERT INTO {SCHEMA_NAME}.job_items (job_id, chunk_id, item_id, reason, detail) "
                "VALUES (%s, %s, %s, 'refused by the inference server', %s)",
                (job_id, row[0], item, Jsonb({"status": 500})),
            )

    def test_a_new_job_has_produced_nothing(self, declared: psycopg.Connection) -> None:
        job = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 5})

        assert (job.produced, job.skipped, job.quarantined) == (0, 0, 0)

    def test_the_outcome_adds_up_across_chunks(self, declared: psycopg.Connection) -> None:
        """The nuScenes case: most records skipped, a few produced, one image refused."""
        job = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 5})
        self._worker_finishes(declared, job.id, produced=6, skipped=1, failed=["img-3"])
        self._worker_finishes(declared, job.id, produced=1, skipped=7, failed=[])

        read = jobs.get(declared, job.id)

        assert (read.produced, read.skipped, read.quarantined) == (7, 8, 1)
        assert jobs.list_jobs(declared)[0].quarantined == 1

    def test_the_quarantine_can_be_read_back(self, declared: psycopg.Connection) -> None:
        job = jobs.submit(declared, kind="fake", dataset_id="ds", params={"task_count": 5})
        self._worker_finishes(declared, job.id, produced=5, skipped=0, failed=["img-3", "img-7"])

        items = jobs.quarantine(declared, job.id, limit=10)

        assert [(item.item_id, item.reason, item.detail) for item in items] == [
            ("img-3", "refused by the inference server", {"status": 500}),
            ("img-7", "refused by the inference server", {"status": 500}),
        ]

    def test_the_quarantine_of_an_unknown_job_is_reported_as_missing(self, declared: psycopg.Connection) -> None:
        with pytest.raises(jobs.JobNotFoundError):
            jobs.quarantine(declared, "00000000-0000-0000-0000-000000000000", limit=10)
