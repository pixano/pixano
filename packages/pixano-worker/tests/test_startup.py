# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests de l'enchaînement de démarrage du worker."""

import pytest
from pixano_worker import __main__ as entrypoint
from pixano_worker.schema import SchemaVersionError


ENV = {
    "PIXANO_DATABASE_URL": "postgresql://pixano:motdepasse@postgres:5432/pixano",
    "PIXANO_INFERENCE_URL": "http://pixano-inference:7463",
    "PIXANO_LIBRARY_DIR": "/data/library",
    "PIXANO_MEDIA_ROOT": "/medias",
    "PIXANO_INFERENCE_MEDIA_ROOT": "/medias",
}


@pytest.fixture
def steps(monkeypatch: pytest.MonkeyPatch, tmp_path) -> list[str]:
    """Remplacer chaque étape de démarrage par une trace, et couper la boucle."""
    for name, value in ENV.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setenv("PIXANO_WORKER_HEARTBEAT", str(tmp_path / "battement"))

    order: list[str] = []
    monkeypatch.setattr(entrypoint, "wait_for_database", lambda *a: order.append("database"))
    monkeypatch.setattr(entrypoint, "wait_for_inference", lambda *a: order.append("inference"))
    monkeypatch.setattr(entrypoint, "psycopg", _FakePsycopg())
    monkeypatch.setattr(entrypoint, "ensure_schema", lambda conn: order.append("schema"))
    monkeypatch.setattr(entrypoint, "default_registry", _FakeRegistry)

    async def _stop(*_args: object) -> None:
        order.append("boucle")
        raise KeyboardInterrupt

    monkeypatch.setattr(entrypoint, "serve", _stop)
    return order


class _FakeRegistry:
    """Un registre qui ne déclare rien, pour isoler l'ordre de démarrage."""

    def __init__(self, *_args: object, **_kwargs: object) -> None:
        """Le registre reçoit l'adresse de l'inference, qu'un faux ignore."""

    def declare(self, *_args: object) -> int:
        return 0

    def names(self) -> list[str]:
        return []


class _FakeConnection:
    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


class _FakePsycopg:
    Error = Exception

    def connect(self, *_args, **_kwargs) -> _FakeConnection:
        return _FakeConnection()


def test_the_schema_is_checked_between_the_two_waits(steps: list[str]) -> None:
    """Un schéma incompatible est fatal : l'opérateur doit l'apprendre tout de suite, pas
    après une longue attente d'un serveur d'inférence dont ce worker ne se servira pas."""
    with pytest.raises(KeyboardInterrupt):
        entrypoint.main()

    assert steps == ["database", "schema", "inference", "boucle"]


def test_an_incompatible_schema_stops_the_worker(steps: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    def refuse(_conn: object) -> None:
        raise SchemaVersionError("version 1 ≠ version 2")

    monkeypatch.setattr(entrypoint, "ensure_schema", refuse)

    assert entrypoint.main() == 1
    assert "inference" not in steps


def test_a_database_failure_stops_the_worker(steps: list[str], monkeypatch: pytest.MonkeyPatch) -> None:
    """Une base injoignable au moment de la DDL n'est pas une raison de continuer."""

    def fail(_conn: object) -> None:
        raise entrypoint.psycopg.Error("permission refusée")

    monkeypatch.setattr(entrypoint, "ensure_schema", fail)

    assert entrypoint.main() == 1
    assert "inference" not in steps
