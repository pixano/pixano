# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pixano.api import serve


@pytest.fixture
def bundled_app(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    bundle = tmp_path / "dist"
    (bundle / "_app").mkdir(parents=True)
    (bundle / "index.html").write_text("<!doctype html><title>Pixano</title>")
    (bundle / "favicon.ico").write_bytes(b"\x00\x00\x01\x00pixano-icon")
    (bundle / "robots.txt").write_text("User-agent: *\nDisallow:\n")
    monkeypatch.setattr(serve, "TEMPLATE_PATH", str(bundle))
    monkeypatch.setattr(serve, "ASSETS_PATH", str(bundle / "_app"))
    monkeypatch.setattr(serve.App, "get_env", lambda _: "none")
    monkeypatch.setitem(serve.task_functions, "none", lambda coro: coro.close())
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    app = serve.App(data_dir=str(data_dir)).app
    with TestClient(app, follow_redirects=False) as client:
        yield client, bundle


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
    assert "<title>Pixano</title>" in home.text
    assert client.get("/health").json() == {"status": "ok"}

    route = client.get("/dataset/example?tab=records")
    assert route.status_code == 307
    assert route.headers["location"] == "/#/dataset/example?tab=records"

    for path in ("/io/missing-route", "/_app/missing.js"):
        response = client.get(path)
        assert response.status_code == 404
        assert "location" not in response.headers
