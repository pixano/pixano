# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What several suites share: a live PostgreSQL for the tests that need one, and another chunk
writing a dataset while the worker writes it."""

import os
import threading
from collections.abc import AsyncIterator, Callable, Iterator
from contextlib import AbstractContextManager, contextmanager
from pathlib import Path

import psycopg
import pytest
from pixano_worker import runner
from pixano_worker.schema import SCHEMA_NAME, ensure_schema

from pixano.datasets import Dataset


# A dedicated variable, and deliberately so: a developer running the worker has
# PIXANO_DATABASE_URL in their environment. If the tests hooked onto it, running pytest
# would truncate their working database. It must not be possible to target a deployment by
# accident.
TEST_DATABASE_URL = "PIXANO_TEST_DATABASE_URL"


@pytest.fixture(scope="session")
def postgres_url() -> str:
    """URL of the throwaway database reserved for the tests."""
    url = os.environ.get(TEST_DATABASE_URL, "")
    if not url:
        pytest.skip(f"{TEST_DATABASE_URL} not set")
    return url


def _refuse_a_populated_database(conn: psycopg.Connection) -> None:
    """Forbid wiping a schema that holds jobs.

    The dedicated variable only protects against forgetfulness; it does not protect against
    the hand that points it at a real database. This safeguard catches the remaining case — at
    the cost of one query per test, which is trivial next to a queue wiped by mistake.
    """
    exists = conn.execute(f"SELECT to_regclass('{SCHEMA_NAME}.jobs')").fetchone()
    if exists is None or exists[0] is None:
        return
    row = conn.execute(f"SELECT count(*) FROM {SCHEMA_NAME}.jobs").fetchone()
    if row is not None and row[0]:
        raise RuntimeError(
            f"{TEST_DATABASE_URL} points at a database that holds {row[0]} job(s). "
            "The tests wipe the schema: point them at a throwaway database."
        )


@pytest.fixture
def blank_db(postgres_url: str) -> Iterator[psycopg.Connection]:
    """Connection to a database without the jobs schema, wiped before and after the test."""
    with psycopg.connect(postgres_url, autocommit=True) as conn:
        _refuse_a_populated_database(conn)
        conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")
        yield conn
        conn.execute(f"DROP SCHEMA IF EXISTS {SCHEMA_NAME} CASCADE")


@pytest.fixture
def db(blank_db: psycopg.Connection) -> psycopg.Connection:
    """Connection to a database whose schema is installed."""
    ensure_schema(blank_db)
    return blank_db


@pytest.fixture
async def adb(db: psycopg.Connection, postgres_url: str) -> AsyncIterator[psycopg.AsyncConnection]:
    """Asynchronous connection to the same database, for the queue and the runner.

    Both connections are in autocommit: what the test prepares through `db` is visible right
    away through `adb`, and conversely.
    """
    async with await psycopg.AsyncConnection.connect(postgres_url, autocommit=True) as conn:
        yield conn


# How long a test waits for the thread that writes a dataset to take its lock, or to let it go:
# far beyond what either takes, so that only a hang reaches it.
LOCK_HANDOVER_TIMEOUT_S = 10.0


@contextmanager
def _writing(path: Path, dataset_id: str) -> Iterator[threading.Event]:
    """This worker's chunk of another job writes the dataset at `path`, in another thread, until the
    block ends or the event it yields is set.

    It holds the runner's write lock for that dataset, as `runner._execute` does around `write`,
    and the dataset's own write lock, as a write does.
    """
    holding, done = threading.Event(), threading.Event()

    def write() -> None:
        with runner._write_lock(dataset_id), Dataset(path).write_lock():
            holding.set()
            done.wait(LOCK_HANDOVER_TIMEOUT_S)

    writer = threading.Thread(target=write, name="someone-writing")
    writer.start()
    assert holding.wait(LOCK_HANDOVER_TIMEOUT_S), "the other writer never took the lock"
    try:
        yield done
    finally:
        done.set()
        writer.join(LOCK_HANDOVER_TIMEOUT_S)


@pytest.fixture
def writing() -> Callable[..., AbstractContextManager[threading.Event]]:
    """Another chunk writing a dataset for the length of a block (`_writing`)."""
    return _writing
