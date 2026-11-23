# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The two questions the app answers apart: is the process alive, and can it serve.

`/health/live` tests nothing, so it answers 200 whatever is down. `/health/ready` tests what the
app depends on, answers 503 while any of it is missing, and names it: a probe reads the status, an
operator reads `missing`. The inference is not one of them: the app serves without it, so an
inference that does not answer is named under `degraded`, and the app stays ready.
"""

import asyncio
import logging
import os
import socket
import threading
import time
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.routers import health
from pixano.api.settings import Settings, get_settings
from pixano.inference.provider import InferenceProvider
from pixano.inference.types import InferenceTask, ModelInfo, ServerInfo


# Never PIXANO_DATABASE_URL: a developer running the stack has that one exported.
TEST_DATABASE_URL_VARIABLE = "PIXANO_TEST_DATABASE_URL"

# Nothing listens on port 1: the connection is refused at once, with no timeout to wait for.
UNREACHABLE_DATABASE_URL = "postgresql://pixano@127.0.0.1:1/pixano"
UNREACHABLE_S3_ENDPOINT = "http://127.0.0.1:1"

LIBRARY_BUCKET = "pixano-bucket"

NOT_CONFIGURED = {"status": "not_configured", "detail": None}
OK = {"status": "ok", "detail": None}

# What a test waits for a dependency that hangs, in place of the 2 s of a deployment.
SHORT_CHECK_TIMEOUT_S = 0.2


def _client(tmp_path: Path, *, library: bool = True, **deployment: object) -> TestClient:
    """A client of an app whose library is a local directory, there unless `library` says not.

    `deployment` holds what the deployment configures beside the storage: PIXANO_DATABASE_URL, the
    inference providers.
    """
    if library:
        (tmp_path / "library").mkdir()
    return _client_of(Settings(data_dir=tmp_path, **deployment))


def _client_of(settings: Settings) -> TestClient:
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


class _Provider(InferenceProvider):
    """An inference provider that answers its models as the test says: a list, an error, or never."""

    def __init__(self, answer: list[ModelInfo] | Exception | None) -> None:
        self._answer = answer
        self.asked = 0

    @property
    def name(self) -> str:
        return "fake"

    async def list_models(self, task: InferenceTask | None = None) -> list[ModelInfo]:
        self.asked += 1
        if self._answer is None:
            await asyncio.sleep(3600)
        if isinstance(self._answer, Exception):
            raise self._answer
        return self._answer or []

    async def get_server_info(self) -> ServerInfo:
        return ServerInfo(version="0", models=[], models_to_task={})


def _with_provider(tmp_path: Path, provider: _Provider) -> TestClient:
    return _client(tmp_path, inference_providers={"fake": provider}, default_inference_provider="fake")


class TestLiveness:
    def test_live_answers_and_tests_nothing(self, tmp_path: Path) -> None:
        """Nothing the app depends on is there — no library, no database — and it is alive all the same."""
        client = _client(tmp_path, library=False, PIXANO_DATABASE_URL=UNREACHABLE_DATABASE_URL)

        response = client.get("/health/live")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}

    def test_health_stays_what_it_was(self, tmp_path: Path) -> None:
        """The probes written before the two routes call it: it still tests nothing."""
        client = _client(tmp_path, library=False, PIXANO_DATABASE_URL=UNREACHABLE_DATABASE_URL)

        response = client.get("/health")

        assert response.status_code == 200
        assert response.json() == {"status": "ok"}


class TestReadinessOfTheStorage:
    def test_ready_with_the_storage_alone(self, tmp_path: Path) -> None:
        """What is not configured is said so, and fails nothing."""
        response = _client(tmp_path).get("/health/ready")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "missing": [],
            "degraded": [],
            "checks": {"storage": OK, "postgresql": NOT_CONFIGURED, "inference": NOT_CONFIGURED},
        }

    def test_not_ready_without_the_library_directory(self, tmp_path: Path) -> None:
        client = _client(tmp_path, library=False)

        response = client.get("/health/ready")

        assert response.status_code == 503
        body = response.json()
        assert (body["status"], body["missing"]) == ("unavailable", ["storage"])
        assert body["checks"]["storage"] == {"status": "unavailable", "detail": health.LIBRARY_DIRECTORY_MISSING}
        assert client.get("/health/live").status_code == 200

    def test_ready_again_once_the_library_directory_is_there(self, tmp_path: Path) -> None:
        client = _client(tmp_path, library=False)
        assert client.get("/health/ready").status_code == 503

        (tmp_path / "library").mkdir()

        assert client.get("/health/ready").status_code == 200


class _S3(BaseHTTPRequestHandler):
    """An S3 that answers every request with the status the test chose, and remembers what was asked."""

    def do_HEAD(self) -> None:
        self.server.asked.append((self.command, self.path))  # type: ignore[attr-defined]
        self.send_response(self.server.status)  # type: ignore[attr-defined]
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def s3() -> Iterator[HTTPServer]:
    """An S3 endpoint on this machine. It answers 200 unless the test changes its `status`."""
    server = HTTPServer(("127.0.0.1", 0), _S3)
    server.status = 200  # type: ignore[attr-defined]
    server.asked = []  # type: ignore[attr-defined]
    thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def _s3_client(tmp_path: Path, endpoint: str) -> TestClient:
    """A client of an app whose library is on S3, under a key of a bucket."""
    return _client_of(
        Settings(
            library_dir=f"s3://{LIBRARY_BUCKET}/library",
            models_dir=tmp_path / "models",
            aws_endpoint=endpoint,
            aws_region="us-east-1",
            aws_access_key="key",
            aws_secret_key="secret",
        )
    )


class TestReadinessOfAnS3Library:
    def test_ready_when_the_bucket_answers(self, tmp_path: Path, s3: HTTPServer) -> None:
        """One HEAD of the bucket, and nothing of the library's key: an empty library holds no object."""
        response = _s3_client(tmp_path, f"http://127.0.0.1:{s3.server_port}").get("/health/ready")

        assert response.status_code == 200
        assert response.json()["checks"]["storage"] == OK
        assert s3.asked == [("HEAD", f"/{LIBRARY_BUCKET}")]  # type: ignore[attr-defined]

    def test_not_ready_when_the_bucket_is_refused(self, tmp_path: Path, s3: HTTPServer) -> None:
        s3.status = 404  # type: ignore[attr-defined]

        response = _s3_client(tmp_path, f"http://127.0.0.1:{s3.server_port}").get("/health/ready")

        assert response.status_code == 503
        body = response.json()
        assert body["missing"] == ["storage"]
        assert body["checks"]["storage"] == {"status": "unavailable", "detail": health.LIBRARY_BUCKET_UNREACHABLE}

    def test_not_ready_when_s3_is_unreachable(self, tmp_path: Path) -> None:
        response = _s3_client(tmp_path, UNREACHABLE_S3_ENDPOINT).get("/health/ready")

        assert response.status_code == 503
        assert response.json()["missing"] == ["storage"]


@pytest.fixture
def silent_database_url() -> Iterator[str]:
    """The URL of a database whose server takes the connection and never answers it."""
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        listener.listen()
        yield f"postgresql://pixano@127.0.0.1:{listener.getsockname()[1]}/pixano"


@pytest.fixture
def live_database_url() -> str:
    """The URL of the tests' PostgreSQL. Only connected to: nothing is read or written."""
    url = os.environ.get(TEST_DATABASE_URL_VARIABLE, "")
    if not url:
        pytest.skip(f"{TEST_DATABASE_URL_VARIABLE} not set")
    return url


class TestReadinessOfPostgreSQL:
    def test_not_ready_names_postgresql_when_it_is_unreachable(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The app is alive and not ready. Why goes to the log: the error names the database's host."""
        client = _client(tmp_path, PIXANO_DATABASE_URL=UNREACHABLE_DATABASE_URL)

        with caplog.at_level(logging.WARNING, logger=health.logger.name):
            response = client.get("/health/ready")

        assert response.status_code == 503
        assert response.json() == {
            "status": "unavailable",
            "missing": ["postgresql"],
            "degraded": [],
            "checks": {
                "storage": OK,
                "postgresql": {"status": "unavailable", "detail": health.POSTGRESQL_UNREACHABLE},
                "inference": NOT_CONFIGURED,
            },
        }
        assert "127.0.0.1" not in response.text
        assert "127.0.0.1" in caplog.text
        assert client.get("/health/live").status_code == 200

    def test_gives_up_on_a_database_that_never_answers(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, silent_database_url: str
    ) -> None:
        """The readiness answers within the time a check is given, not when the connection times out.

        psycopg waits no less than 2 s for a connection: the answer comes well before that.
        """
        monkeypatch.setattr(health, "CHECK_TIMEOUT_S", SHORT_CHECK_TIMEOUT_S)
        client = _client(tmp_path, PIXANO_DATABASE_URL=silent_database_url)

        started = time.monotonic()
        response = client.get("/health/ready")
        elapsed = time.monotonic() - started

        assert response.status_code == 503
        body = response.json()
        assert body["missing"] == ["postgresql"]
        assert body["checks"]["postgresql"]["detail"] == f"no answer within {SHORT_CHECK_TIMEOUT_S:g} s"
        assert elapsed < 1.5

    def test_ready_again_once_postgresql_is_back_without_a_restart(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Nothing is remembered from one call to the next: each opens a connection of its own.

        PostgreSQL is stood in for by what opens the connection, which refuses, then accepts. The
        timeout of the connection is the readiness's, whatever the URL sets: a URL that waits a
        minute would hold a thread that long on every call.
        """
        down = True
        asked: list[dict] = []

        class _Connection:
            def close(self) -> None:
                pass

        def connect(url: str, **options: object) -> _Connection:
            asked.append({"url": url, **options})
            if down:
                raise psycopg.OperationalError("connection refused")
            return _Connection()

        monkeypatch.setattr(health.psycopg, "connect", connect)
        url = f"{UNREACHABLE_DATABASE_URL}?connect_timeout=60"
        client = _client(tmp_path, PIXANO_DATABASE_URL=url)

        assert client.get("/health/ready").json()["missing"] == ["postgresql"]
        down = False
        response = client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["checks"]["postgresql"] == OK
        assert asked == [{"url": url, "connect_timeout": health.CLIENT_TIMEOUT_S}] * 2

    def test_ready_with_a_postgresql_that_answers(self, tmp_path: Path, live_database_url: str) -> None:
        """A connection is all that is asked of it: the tables of the queue are not read."""
        client = _client(tmp_path, PIXANO_DATABASE_URL=live_database_url)

        response = client.get("/health/ready")

        assert response.status_code == 200
        assert response.json()["checks"]["postgresql"] == OK

    def test_ready_again_once_the_database_url_reaches_a_postgresql(
        self, tmp_path: Path, live_database_url: str
    ) -> None:
        """The same app, not restarted, first without its database, then with a real one."""
        (tmp_path / "library").mkdir()
        settings = Settings(data_dir=tmp_path, PIXANO_DATABASE_URL=UNREACHABLE_DATABASE_URL)
        client = _client_of(settings)
        assert client.get("/health/ready").status_code == 503

        settings.database_url = live_database_url

        assert client.get("/health/ready").status_code == 200


class TestReadinessOfTheInference:
    """The app serves everything that needs no model without the inference: it never fails the readiness."""

    def test_ready_when_the_default_provider_answers(self, tmp_path: Path) -> None:
        provider = _Provider([ModelInfo(name="sam2", task="image_mask_generation")])

        response = _with_provider(tmp_path, provider).get("/health/ready")

        assert response.status_code == 200
        body = response.json()
        assert body["checks"]["inference"] == OK
        assert body["degraded"] == []
        assert provider.asked == 1

    def test_still_ready_when_the_default_provider_fails(
        self, tmp_path: Path, caplog: pytest.LogCaptureFixture
    ) -> None:
        """The inference is down: the app is ready, and says what it serves without. Why goes to the log."""
        client = _with_provider(tmp_path, _Provider(ConnectionError("connection refused by 10.0.0.7")))

        with caplog.at_level(logging.WARNING, logger=health.logger.name):
            response = client.get("/health/ready")

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "missing": [],
            "degraded": ["inference"],
            "checks": {
                "storage": OK,
                "postgresql": NOT_CONFIGURED,
                "inference": {"status": "unavailable", "detail": health.INFERENCE_UNREACHABLE},
            },
        }
        assert "10.0.0.7" not in response.text
        assert "degraded: the inference provider fake" in caplog.text
        assert "10.0.0.7" in caplog.text
        assert "not ready" not in caplog.text

    def test_a_provider_that_never_answers_does_not_hold_the_answer(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The inference hangs: the app is ready, and says so well within the time a probe waits.

        The inference is given its own, shorter time. The 2 s of the other dependencies are left as
        a deployment has them: an answer that came after them would fail the probe of an app that
        can serve.
        """
        monkeypatch.setattr(health, "OPTIONAL_CHECK_TIMEOUT_S", SHORT_CHECK_TIMEOUT_S)

        started = time.monotonic()
        response = _with_provider(tmp_path, _Provider(None)).get("/health/ready")
        elapsed = time.monotonic() - started

        assert response.status_code == 200
        body = response.json()
        assert (body["status"], body["missing"], body["degraded"]) == ("ok", [], ["inference"])
        assert body["checks"]["inference"] == {
            "status": "unavailable",
            "detail": f"no answer within {SHORT_CHECK_TIMEOUT_S:g} s",
        }
        assert elapsed < 1.5

    def test_the_inference_is_given_less_than_the_second_a_probe_waits(self) -> None:
        """Kubernetes waits one second for a probe unless told otherwise: a hanging inference must fit in it."""
        assert health.OPTIONAL_CHECK_TIMEOUT_S < 1 < health.CHECK_TIMEOUT_S

    def test_a_provider_that_is_not_the_default_is_not_asked(self, tmp_path: Path) -> None:
        """The default provider is the one a request that names none is sent to: it alone is tested."""
        default, other = _Provider([]), _Provider(ConnectionError("connection refused"))
        client = _client(
            tmp_path, inference_providers={"fake": default, "other": other}, default_inference_provider="fake"
        )

        response = client.get("/health/ready")

        assert response.status_code == 200
        assert (default.asked, other.asked) == (1, 0)

    def test_providers_without_a_default_are_not_configured(self, tmp_path: Path) -> None:
        provider = _Provider(ConnectionError("connection refused"))

        response = _client(tmp_path, inference_providers={"fake": provider}).get("/health/ready")

        assert response.status_code == 200
        assert response.json()["checks"]["inference"] == NOT_CONFIGURED


def test_a_dependency_that_hangs_holds_its_own_threads_and_no_more(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Probes go on calling while a dependency hangs: each is answered in time, and names it alone.

    The checks of the storage that hang keep the threads of the storage, two here. The calls that
    follow start none, and PostgreSQL, which answers, is still said to.
    """
    threads = ThreadPoolExecutor(max_workers=2)
    back = threading.Event()
    hanging: list[Path] = []

    def hang(library_dir: Path) -> None:
        hanging.append(library_dir)
        back.wait(timeout=30)

    class _Connection:
        def close(self) -> None:
            pass

    monkeypatch.setattr(health, "CHECK_TIMEOUT_S", SHORT_CHECK_TIMEOUT_S)
    monkeypatch.setattr(health, "_STORAGE_THREADS", threads)
    monkeypatch.setattr(health, "_library_directory_exists", hang)
    monkeypatch.setattr(health.psycopg, "connect", lambda url, **options: _Connection())
    client = _client(tmp_path, PIXANO_DATABASE_URL=UNREACHABLE_DATABASE_URL)

    try:
        for _ in range(4):
            response = client.get("/health/ready")
            assert response.status_code == 503
            assert response.json()["missing"] == ["storage"]
            assert response.json()["checks"]["postgresql"] == OK
        assert len(hanging) == 2

        # The storage is back: the threads it held end, and the next call is answered by one of them.
        back.set()
        monkeypatch.setattr(health, "CHECK_TIMEOUT_S", 10.0)
        assert client.get("/health/ready").status_code == 200
    finally:
        back.set()
        threads.shutdown()


def test_every_dependency_that_does_not_answer_is_named(tmp_path: Path) -> None:
    """The three are asked at once. The two the app cannot serve without are missing, in the order of
    `checks`; the inference, which it serves without, is what the app is degraded by."""
    client = _client(
        tmp_path,
        library=False,
        PIXANO_DATABASE_URL=UNREACHABLE_DATABASE_URL,
        inference_providers={"fake": _Provider(ConnectionError("connection refused"))},
        default_inference_provider="fake",
    )

    response = client.get("/health/ready")

    assert response.status_code == 503
    body = response.json()
    assert (body["status"], body["missing"], body["degraded"]) == (
        "unavailable",
        ["storage", "postgresql"],
        ["inference"],
    )
