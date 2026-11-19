# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A throwaway job queue, for the tests that queue processing jobs on it."""

import os
from collections.abc import Iterator

import psycopg
import pytest
from psycopg.types.json import Jsonb

from pixano.api.jobs import SCHEMA_NAME
from pixano.api.jobs.follow_ups import EMBEDDINGS_KIND


# Never PIXANO_DATABASE_URL: a developer running the stack has that one exported, and these tests
# delete rows.
TEST_DATABASE_URL = "PIXANO_TEST_DATABASE_URL"

# The parameters a worker publishes for the embeddings kind, reduced to what the tests need.
EMBEDDINGS_SCHEMA = {
    "type": "object",
    "properties": {"model": {"type": "string", "minLength": 1}},
    "required": ["model"],
}


@pytest.fixture
def queue_url() -> Iterator[str]:
    """The URL of a throwaway queue, emptied around each test."""
    url = os.environ.get(TEST_DATABASE_URL, "")
    if not url:
        pytest.skip(f"{TEST_DATABASE_URL} not set")
    with psycopg.connect(url, autocommit=True) as conn:
        exists = conn.execute(f"SELECT to_regclass('{SCHEMA_NAME}.jobs')").fetchone()
        if exists is None or exists[0] is None:
            pytest.skip("the queue schema is absent — pixano-worker installs it")
        conn.execute(f"TRUNCATE {SCHEMA_NAME}.jobs, {SCHEMA_NAME}.job_kinds CASCADE")
        yield url
        conn.execute(f"TRUNCATE {SCHEMA_NAME}.jobs, {SCHEMA_NAME}.job_kinds CASCADE")


@pytest.fixture
def embeddings_declared(queue_url: str) -> str:
    """The URL of a queue where a worker has declared the embeddings job."""
    with psycopg.connect(queue_url, autocommit=True) as conn:
        conn.execute(
            f"INSERT INTO {SCHEMA_NAME}.job_kinds (name, params_schema, declared_by) VALUES (%s, %s, %s)",
            (EMBEDDINGS_KIND, Jsonb(EMBEDDINGS_SCHEMA), "worker-test"),
        )
    return queue_url


def queued_jobs(url: str) -> list[tuple]:
    """The jobs on the queue, oldest first: kind, dataset, parameters."""
    with psycopg.connect(url, autocommit=True) as conn:
        return conn.execute(f"SELECT kind, dataset, params FROM {SCHEMA_NAME}.jobs ORDER BY created_at").fetchall()
