# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests for planning jobs and putting them on the queue."""

import os

import psycopg
import pytest

from pixano.api import jobs
from pixano.api.jobs import SCHEMA_NAME, queries


TEST_DATABASE_URL = "PIXANO_TEST_DATABASE_URL"


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
        conn.execute(f"TRUNCATE {SCHEMA_NAME}.jobs CASCADE")
        yield conn
        conn.execute(f"TRUNCATE {SCHEMA_NAME}.jobs CASCADE")


class TestPlanChunks:
    """Splitting a selection is pure arithmetic and needs no database."""

    def test_splits_into_full_chunks_and_a_remainder(self) -> None:
        chunks = list(jobs.plan_chunks([f"i{n}" for n in range(10)], chunk_size=4))

        assert [count for _, _, count in chunks] == [4, 4, 2]
        assert [seq for seq, _, _ in chunks] == [0, 1, 2]

    def test_carries_the_identifiers_in_the_payload(self) -> None:
        """The payload stays opaque to the engine; the job kind reads it."""
        chunks = list(jobs.plan_chunks(["a", "b", "c"], chunk_size=2))

        assert [payload for _, payload, _ in chunks] == [{"item_ids": ["a", "b"]}, {"item_ids": ["c"]}]

    def test_a_single_item_is_one_chunk(self) -> None:
        assert len(list(jobs.plan_chunks(["only"], chunk_size=64))) == 1

    def test_an_empty_selection_plans_nothing(self) -> None:
        assert list(jobs.plan_chunks([], chunk_size=8)) == []

    def test_refuses_a_meaningless_chunk_size(self) -> None:
        with pytest.raises(ValueError, match="chunk_size"):
            list(jobs.plan_chunks(["a"], chunk_size=0))


class TestConnect:
    """A missing queue is a deployment state, not a crash."""

    def test_no_configured_url_is_refused_clearly(self) -> None:
        with pytest.raises(jobs.QueueUnavailableError, match="PIXANO_DATABASE_URL"):
            jobs.connect(None)

    def test_an_unreachable_database_is_refused_clearly(self) -> None:
        with pytest.raises(jobs.QueueUnavailableError, match="injoignable"):
            jobs.connect("postgresql://nobody@127.0.0.1:1/none?connect_timeout=1")


class TestEnqueue:
    def test_writes_the_job_and_all_of_its_chunks(self, queue: psycopg.Connection) -> None:
        job = jobs.enqueue(
            queue,
            kind="fake",
            dataset_id="ds",
            item_ids=[f"i{n}" for n in range(100)],
            chunk_size=16,
        )

        row = queue.execute(
            f"SELECT count(*), sum(task_count) FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s",
            (job.id,),
        ).fetchone()
        assert row == (7, 100)
        assert job.total_tasks == 100
        assert job.state == "pending"

    def test_the_job_and_its_chunks_land_together(
        self, queue: psycopg.Connection, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A worker must never see a job without its work, or it would settle it as done.

        The failure is forced into the chunk insert — after the job row exists — because
        that is the only window where a non-transactional implementation would leave an
        empty job behind.
        """
        monkeypatch.setattr(
            queries,
            "INSERT_CHUNKS",
            f"INSERT INTO {SCHEMA_NAME}.job_chunks (job_id, seq, task_count) " "VALUES (%s, 0, 0), (%s, %s, %s)",
        )

        with pytest.raises(psycopg.Error):
            jobs.enqueue(queue, kind="fake", dataset_id="ds", item_ids=["a"])

        row = queue.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.jobs").fetchone()
        assert row is not None and row[0] == 0

    def test_stores_the_parameters_as_given(self, queue: psycopg.Connection) -> None:
        params = {"model": "clip", "batch": 16}

        job = jobs.enqueue(queue, kind="embed", dataset_id="ds", item_ids=["a"], params=params)

        row = queue.execute(f"SELECT params FROM {SCHEMA_NAME}.jobs WHERE id = %s", (job.id,)).fetchone()
        assert row is not None and row[0] == params

    def test_refuses_an_empty_selection(self, queue: psycopg.Connection) -> None:
        with pytest.raises(ValueError, match="rien à exécuter"):
            jobs.enqueue(queue, kind="fake", dataset_id="ds", item_ids=[])


class TestReadAndCancel:
    def test_reads_a_job_back(self, queue: psycopg.Connection) -> None:
        job = jobs.enqueue(queue, kind="fake", dataset_id="ds", item_ids=["a", "b"])

        assert jobs.get(queue, job.id) == job

    def test_an_unknown_job_is_reported_as_missing(self, queue: psycopg.Connection) -> None:
        with pytest.raises(jobs.JobNotFoundError):
            jobs.get(queue, "00000000-0000-0000-0000-000000000000")

    def test_lists_the_most_recent_first(self, queue: psycopg.Connection) -> None:
        first = jobs.enqueue(queue, kind="a", dataset_id="ds", item_ids=["x"])
        second = jobs.enqueue(queue, kind="b", dataset_id="ds", item_ids=["y"])

        assert [job.id for job in jobs.list_jobs(queue)][:2] == [second.id, first.id]

    def test_cancelling_empties_the_claimable_pool(self, queue: psycopg.Connection) -> None:
        job = jobs.enqueue(queue, kind="fake", dataset_id="ds", item_ids=[f"i{n}" for n in range(50)])

        cancelled = jobs.cancel(queue, job.id)

        assert cancelled.state == "cancelled"
        row = queue.execute(
            f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s AND state = 'pending'",
            (job.id,),
        ).fetchone()
        assert row is not None and row[0] == 0

    def test_a_job_with_work_in_flight_is_not_settled_yet(self, queue: psycopg.Connection) -> None:
        """A running chunk is left to its worker, which gives it back between two batches."""
        job = jobs.enqueue(queue, kind="fake", dataset_id="ds", item_ids=["a", "b"], chunk_size=1)
        queue.execute(
            f"UPDATE {SCHEMA_NAME}.job_chunks SET state = 'running', "
            "lease_until = now() + interval '2 minutes' WHERE seq = 0"
        )

        cancelled = jobs.cancel(queue, job.id)

        assert cancelled.state == "pending"
        row = queue.execute(
            f"SELECT count(*) FROM {SCHEMA_NAME}.job_chunks WHERE job_id = %s AND state = 'running'",
            (job.id,),
        ).fetchone()
        assert row is not None and row[0] == 1

    def test_cancelling_twice_is_harmless(self, queue: psycopg.Connection) -> None:
        job = jobs.enqueue(queue, kind="fake", dataset_id="ds", item_ids=["a"])

        jobs.cancel(queue, job.id)
        again = jobs.cancel(queue, job.id)

        assert again.state == "cancelled"
