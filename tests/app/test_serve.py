# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pixano.api import serve


NEW_UI_TITLE = "<title>Pixano v1.0</title>"
LEGACY_UI_TITLE = "<title>Pixano</title>"


def _serve_bundles(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Install a fake build of both UIs and return the new UI's bundle directory."""
    bundle = tmp_path / "dist"
    (bundle / "_app").mkdir(parents=True)
    (bundle / "index.html").write_text(f"<!doctype html>{NEW_UI_TITLE}")
    (bundle / "favicon.ico").write_bytes(b"\x00\x00\x01\x00pixano-icon")
    (bundle / "robots.txt").write_text("User-agent: *\nDisallow:\n")
    legacy_bundle = tmp_path / "legacy_dist"
    (legacy_bundle / "_legacy_app").mkdir(parents=True)
    (legacy_bundle / "index.html").write_text(f"<!doctype html>{LEGACY_UI_TITLE}")
    monkeypatch.setattr(serve, "TEMPLATE_PATH", str(bundle))
    monkeypatch.setattr(serve, "ASSETS_PATH", str(bundle / "_app"))
    monkeypatch.setattr(serve, "LEGACY_TEMPLATE_PATH", str(legacy_bundle))
    monkeypatch.setattr(serve, "LEGACY_ASSETS_PATH", str(legacy_bundle / "_legacy_app"))
    monkeypatch.setattr(serve.App, "get_env", lambda _: "none")
    monkeypatch.setitem(serve.task_functions, "none", lambda coro: coro.close())
    return bundle


def _client(tmp_path: Path) -> TestClient:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    return TestClient(serve.App(data_dir=str(data_dir)).app, follow_redirects=False)


@pytest.fixture
def bundled_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("ACTIVATE_UI_V1_0", raising=False)
    bundle = _serve_bundles(tmp_path, monkeypatch)
    with _client(tmp_path) as client:
        yield client, bundle


@pytest.fixture
def new_ui_enabled_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("ACTIVATE_UI_V1_0", "true")
    _serve_bundles(tmp_path, monkeypatch)
    with _client(tmp_path) as client:
        yield client


@pytest.mark.parametrize("filename,media_type", [("favicon.ico", "image/x-icon"), ("robots.txt", "text/plain")])
def test_root_static_files_serve_packaged_bytes(bundled_app, filename: str, media_type: str):
    client, bundle = bundled_app
    expected = (bundle / filename).read_bytes()

    response = client.get(f"/{filename}")

    assert response.status_code == 200
    assert response.content == expected
    assert response.headers["content-type"].split(";")[0] == media_type
    assert "location" not in response.headers

    head = client.head(f"/{filename}")
    assert head.status_code == 200
    assert head.content == b""
    assert int(head.headers["content-length"]) == len(expected)


@pytest.mark.parametrize("filename", ["favicon.ico", "robots.txt"])
def test_missing_root_static_files_return_404(bundled_app, filename: str):
    client, bundle = bundled_app
    (bundle / filename).unlink()

    response = client.get(f"/{filename}")

    assert response.status_code == 404
    assert "location" not in response.headers


def test_root_static_routes_preserve_spa_and_api_routing(bundled_app):
    client, _ = bundled_app

    home = client.get("/")
    assert home.status_code == 200
    assert LEGACY_UI_TITLE in home.text
    assert client.get("/health").json() == {"status": "ok"}

    route = client.get("/dataset/example?tab=records")
    assert route.status_code == 307
    assert route.headers["location"] == "/#/dataset/example?tab=records"

    for path in ("/io/missing-route", "/_app/missing.js"):
        response = client.get(path)
        assert response.status_code == 404
        assert "location" not in response.headers


@pytest.mark.parametrize("ui_version_cookie", [None, serve.NEW_UI_COOKIE_VALUE, "legacy"])
def test_root_serves_the_legacy_ui_while_the_new_one_is_disabled(bundled_app, ui_version_cookie: str | None):
    client, _ = bundled_app
    if ui_version_cookie is not None:
        client.cookies.set(serve.UI_VERSION_COOKIE, ui_version_cookie)

    home = client.get("/")

    assert home.status_code == 200
    assert LEGACY_UI_TITLE in home.text


def test_root_serves_the_new_ui_once_enabled_and_requested(new_ui_enabled_app):
    client = new_ui_enabled_app

    assert LEGACY_UI_TITLE in client.get("/").text

    client.cookies.set(serve.UI_VERSION_COOKIE, serve.NEW_UI_COOKIE_VALUE)
    assert NEW_UI_TITLE in client.get("/").text

    client.cookies.set(serve.UI_VERSION_COOKIE, "legacy")
    assert LEGACY_UI_TITLE in client.get("/").text


@pytest.mark.parametrize("activate_ui_v1_0,expected", [(None, False), ("false", False), ("true", True), ("1", True)])
def test_ui_options_follow_the_deployment_setting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, activate_ui_v1_0: str | None, expected: bool
):
    if activate_ui_v1_0 is None:
        monkeypatch.delenv("ACTIVATE_UI_V1_0", raising=False)
    else:
        monkeypatch.setenv("ACTIVATE_UI_V1_0", activate_ui_v1_0)
    _serve_bundles(tmp_path, monkeypatch)

    with _client(tmp_path) as client:
        assert client.get("/app/ui").json() == {"new_ui_enabled": expected}


@pytest.mark.parametrize(
    "new_ui_enabled,ui_version_cookie,expected",
    [
        (False, None, False),
        (False, serve.NEW_UI_COOKIE_VALUE, False),
        (True, None, False),
        (True, "legacy", False),
        (True, serve.NEW_UI_COOKIE_VALUE, True),
    ],
)
def test_serves_new_ui_needs_both_the_setting_and_the_request(
    new_ui_enabled: bool, ui_version_cookie: str | None, expected: bool
):
    assert serve.serves_new_ui(new_ui_enabled, ui_version_cookie) is expected
