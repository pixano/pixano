# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.applications import FastAPI
from fastapi.testclient import TestClient

from pixano.app.main import create_app
from pixano.app.settings import Settings, get_settings
from pixano.datasets.dataset_info import DatasetInfo


@pytest.fixture()
def app_and_settings():
    temp_dir = Path(tempfile.mkdtemp())
    settings = Settings(library_dir=str(temp_dir))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override
    return app, settings


def test_get_datasets_not_found(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings

    client = TestClient(app)
    response = client.get("/datasets")
    assert response.status_code == 404
    assert response.json() == {"detail": f"No datasets found in {str(settings.data_dir)}."}


def test_get_datasets(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings
    data_dir = Path(settings.data_dir)

    infos = []
    for dataset in ["coco", "voc"]:
        (data_dir / dataset).mkdir(parents=True)
        dataset_info = DatasetInfo(
            name=dataset,
            description=f"{dataset} dataset",
        )
        dataset_info.to_json(data_dir / dataset / "info.json")
        infos.append(dataset_info)

    client = TestClient(app)
    response = client.get("/datasets")
    assert response.status_code == 200
    assert response.json() == [info.model_dump() for info in infos]
