# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The job endpoints on an installation that has no job queue to offer.

The jobs panel reads a 503 from these endpoints as "this installation cannot run jobs" and shows
its `detail` as the reason. The status and a detail that says what to do are their contract.
"""

import os
import uuid
from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings


DATABASE_URL_VARIABLE = "PIXANO_DATABASE_URL"

# Never PIXANO_DATABASE_URL: a developer running the stack has that one exported.
TEST_DATABASE_URL_VARIABLE = "PIXANO_TEST_DATABASE_URL"

# Nothing listens on port 1: the connection is refused at once, with no timeout to wait for.
UNREACHABLE_DATABASE_URL = "postgresql://pixano@127.0.0.1:1/pixano"

# What a jobs panel lists when it opens.
PANEL_ENDPOINTS = ["/jobs", "/jobs/kinds"]

QUEUE_UNAVAILABLE_STATUS = 503


@pytest.fixture
def database_without_a_queue() -> Iterator[str]:
    """The URL of a database pixano-worker never set up, made for the test and dropped after.

    Made on the test database's server, beside it: that one holds the queue.
    """
    url = os.environ.get(TEST_DATABASE_URL_VARIABLE, "")
    if not url:
        pytest.skip(f"{TEST_DATABASE_URL_VARIABLE} not set")
    name = f"pixano_no_queue_{uuid.uuid4().hex}"
    with psycopg.connect(url, autocommit=True) as admin:
        try:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        except psycopg.errors.InsufficientPrivilege:
            pytest.skip("the test database's role cannot create a database")
    try:
        yield make_conninfo(**{**conninfo_to_dict(url), "dbname": name})
    finally:
        with psycopg.connect(url, autocommit=True) as admin:
            admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))


def _client(tmp_path: Path) -> TestClient:
    """A client of an app configured from the environment, as a server started by hand is."""
    settings = Settings(data_dir=tmp_path)
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


@pytest.mark.parametrize("path", PANEL_ENDPOINTS)
class TestWithoutAJobQueue:
    def test_no_database_configured_says_what_to_set(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
    ) -> None:
        monkeypatch.delenv(DATABASE_URL_VARIABLE, raising=False)

        response = _client(tmp_path).get(path)

        assert response.status_code == QUEUE_UNAVAILABLE_STATUS
        detail = response.json()["detail"]
        assert DATABASE_URL_VARIABLE in detail
        assert "pixano-worker" in detail

    def test_an_unreachable_database_says_so(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str) -> None:
        monkeypatch.setenv(DATABASE_URL_VARIABLE, UNREACHABLE_DATABASE_URL)

        response = _client(tmp_path).get(path)

        assert response.status_code == QUEUE_UNAVAILABLE_STATUS
        assert "unreachable" in response.json()["detail"]

    def test_a_database_the_worker_never_set_up_says_to_start_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, database_without_a_queue: str, path: str
    ) -> None:
        monkeypatch.setenv(DATABASE_URL_VARIABLE, database_without_a_queue)

        response = _client(tmp_path).get(path)

        assert response.status_code == QUEUE_UNAVAILABLE_STATUS
        detail = response.json()["detail"]
        assert "does not exist yet" in detail
        assert "pixano-worker" in detail
