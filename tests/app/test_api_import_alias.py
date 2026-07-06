# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets import Dataset
from tests.assets.sample_data.metadata import IMAGE_JPG_ASSET_URL


@pytest.fixture()
def client_and_data_dir(tmp_path: Path) -> tuple[TestClient, Path]:
    data_dir = tmp_path / "data"
    (data_dir / "library").mkdir(parents=True)
    settings = Settings(library_dir=str(data_dir / "library"))
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app), data_dir


def _wait_for_job(client: TestClient, job_id: str, timeout: float = 30.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = client.get(f"/datasets/import/{job_id}").json()
        if payload["status"] in ("done", "error"):
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: {payload}")


class TestDeprecatedImportAlias:
    def test_unlabeled_images_import(self, client_and_data_dir, tmp_path: Path):
        client, data_dir = client_and_data_dir
        source = tmp_path / "photos"
        source.mkdir()
        for stem in ("a", "b"):
            shutil.copy(IMAGE_JPG_ASSET_URL, source / f"{stem}.jpg")

        response = client.post(
            "/datasets/import",
            json={"source_dir": str(source), "import_type": "unlabeled_images", "dataset_name": "My Photos"},
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"job_id", "status", "message", "dataset_id"}  # legacy shape preserved

        final = _wait_for_job(client, body["job_id"])
        assert final["status"] == "done", final["message"]
        assert "2 image(s)" in final["message"]

        dataset = Dataset(data_dir / "library" / "my_photos")
        assert dataset.open_table("records").count_rows() == 2
        assert dataset.open_table("images").count_rows() == 2
        assert dataset.info.storage_mode == "embedded"

    def test_missing_source_reports_error(self, client_and_data_dir):
        client, _ = client_and_data_dir
        response = client.post("/datasets/import", json={"source_dir": "/nope/missing"})
        final = _wait_for_job(client, response.json()["job_id"])
        assert final["status"] == "error"
        assert "not found" in final["message"].lower()

    def test_unknown_import_type_is_rejected(self, client_and_data_dir):
        client, _ = client_and_data_dir
        response = client.post("/datasets/import", json={"source_dir": "/tmp", "import_type": "labeled_images"})
        assert response.status_code == 400

    def test_unknown_job_404s(self, client_and_data_dir):
        client, _ = client_and_data_dir
        assert client.get("/datasets/import/does-not-exist").status_code == 404
