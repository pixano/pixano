# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import time
from pathlib import Path

import PIL.Image
import pytest
import yaml
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings


@pytest.fixture()
def client_and_dirs(tmp_path: Path) -> tuple[TestClient, Path, Path]:
    data_dir = tmp_path / "data"
    (data_dir / "library").mkdir(parents=True)
    source = tmp_path / "src"
    (source / "train").mkdir(parents=True)
    for stem in ("a", "b", "c"):
        PIL.Image.new("RGB", (16, 16), (200, 30, 40)).save(source / "train" / f"{stem}.jpg")
    (source / "dataset.yaml").write_text(
        yaml.safe_dump({"pixano": 2, "format": "pixano_jsonl", "dataset": {"name": "io_ds", "workspace": "image"}})
    )
    settings = Settings(library_dir=str(data_dir / "library"))
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app), data_dir, source


def _wait_done(client: TestClient, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = client.get(f"/io/jobs/{job_id}").json()
        if payload["status"] in ("done", "error", "cancelled", "interrupted"):
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: {payload}")


class TestIoRoutes:
    def test_formats_lists_builtins(self, client_and_dirs):
        client, _, _ = client_and_dirs
        names = {f["name"] for f in client.get("/io/formats").json()}
        assert {"pixano_jsonl", "coco", "lerobot"} <= names

    def test_analyze_import_poll_done(self, client_and_dirs):
        client, data_dir, source = client_and_dirs

        analyzed = client.post("/io/analyze", json={"source": str(source), "spec": {}}).json()
        assert analyzed["totals"]["records"] == 3
        assert analyzed["plan_id"]

        started = client.post("/io/imports", json={"plan_id": analyzed["plan_id"], "source": str(source)})
        assert started.status_code == 202
        final = _wait_done(client, started.json()["job_id"])
        assert final["status"] == "done", final["error"]
        assert final["progress"]["table_counts"]["records"] == 3
        assert (data_dir / "library" / "io_ds").is_dir()

    def test_analyze_refuses_user_python(self, client_and_dirs):
        client, _, source = client_and_dirs
        response = client.post("/io/analyze", json={"source": str(source), "spec": {"importer": "evil.py:Cls"}})
        assert response.status_code == 400

    def test_import_with_unknown_plan_conflicts(self, client_and_dirs):
        client, _, source = client_and_dirs
        response = client.post("/io/imports", json={"plan_id": "ghost", "source": str(source)})
        assert response.status_code == 409

    def test_export_job(self, client_and_dirs, tmp_path: Path):
        client, _, source = client_and_dirs
        started = client.post("/io/imports", json={"source": str(source), "spec": {}})
        assert _wait_done(client, started.json()["job_id"])["status"] == "done"

        exported = client.post(
            "/io/exports",
            json={"dataset": "io_ds", "destination": str(tmp_path / "out"), "format": "pixano_jsonl"},
        )
        assert exported.status_code == 202
        final = _wait_done(client, exported.json()["job_id"])
        assert final["status"] == "done", final["error"]
        assert (tmp_path / "out" / "dataset.yaml").is_file()

    def test_jobs_listing_and_cancel_conflicts(self, client_and_dirs):
        client, _, source = client_and_dirs
        started = client.post("/io/imports", json={"source": str(source), "spec": {}})
        job_id = started.json()["job_id"]
        _wait_done(client, job_id)
        assert any(job["job_id"] == job_id for job in client.get("/io/jobs").json())
        assert client.post(f"/io/jobs/{job_id}/cancel").status_code == 409  # already terminal
        assert client.get("/io/jobs/ghost").status_code == 404

    def test_interrupted_after_restart(self, client_and_dirs, tmp_path: Path):
        client, data_dir, _ = client_and_dirs
        from pixano.datasets.io.jobs import JobStore

        store = JobStore.for_data_dir(data_dir)
        orphan = store.create_job("import")
        store.update_job(orphan.id, status="running", pid=999_999_999)

        settings = Settings(library_dir=str(data_dir / "library"))
        app2 = create_app(settings)  # boot hook runs recovery
        app2.dependency_overrides[get_settings] = lambda: settings
        restarted = TestClient(app2)
        assert restarted.get(f"/io/jobs/{orphan.id}").json()["status"] == "interrupted"

    def test_resume_and_rollback_are_501(self, client_and_dirs):
        client, _, _ = client_and_dirs
        assert client.post("/io/jobs/x/resume").status_code == 501
        assert client.delete("/io/jobs/x").status_code == 501


class TestLegacyAliasParity:
    def test_exact_legacy_client_sequence(self, client_and_dirs, tmp_path: Path):
        client, data_dir, _ = client_and_dirs
        photos = tmp_path / "photos"
        photos.mkdir()
        for stem in ("x", "y"):
            PIL.Image.new("RGB", (8, 8), (1, 2, 3)).save(photos / f"{stem}.jpg")

        response = client.post(
            "/datasets/import",
            json={"source_dir": str(photos), "import_type": "unlabeled_images", "dataset_name": "My Photos"},
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"job_id", "status", "message", "dataset_id"}  # legacy shape

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            body = client.get(f"/datasets/import/{body['job_id']}").json()
            assert set(body) == {"job_id", "status", "message", "dataset_id"}
            if body["status"] in ("done", "error"):
                break
            time.sleep(0.05)
        assert body["status"] == "done", body["message"]
        assert "2 item(s)" in body["message"]
        assert (data_dir / "library" / "my_photos").is_dir()

    def test_alias_and_io_share_the_store(self, client_and_dirs, tmp_path: Path):
        client, _, _ = client_and_dirs
        photos = tmp_path / "photos2"
        photos.mkdir()
        PIL.Image.new("RGB", (8, 8), (9, 9, 9)).save(photos / "only.jpg")
        job_id = client.post(
            "/datasets/import", json={"source_dir": str(photos), "import_type": "unlabeled_images"}
        ).json()["job_id"]
        _wait_done(client, job_id)
        assert client.get(f"/io/jobs/{job_id}").json()["kind"] == "import"

    def test_unknown_type_and_missing_dir(self, client_and_dirs):
        client, _, _ = client_and_dirs
        assert client.post("/datasets/import", json={"source_dir": "/tmp", "import_type": "bogus"}).status_code == 400
        assert client.post("/datasets/import", json={"source_dir": "/nope/missing"}).status_code == 400
