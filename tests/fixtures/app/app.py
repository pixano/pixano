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
from pixano.datasets.dataset import Dataset
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY


LIBRARY_DIR = ASSETS_DIRECTORY / "library"
MEDIA_DIR = ASSETS_DIRECTORY / "sample_data"


@pytest.fixture(scope="session")
def app_and_settings(
    dataset_image_bboxes_keypoint: Dataset, dataset_multi_view_tracking_and_image: Dataset
) -> tuple[FastAPI, Settings]:  # args to ensure the fixture is called before the app fixture
    settings = Settings(library_dir=str(LIBRARY_DIR), media_dir=str(MEDIA_DIR))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override

    return app, settings


@pytest.fixture(scope="session")
def app_and_settings_with_client(app_and_settings):
    return *app_and_settings, TestClient(app_and_settings[0])


@pytest.fixture()
def app_and_settings_copy(
    dataset_image_bboxes_keypoint_copy: Dataset, dataset_multi_view_tracking_and_image_copy: Dataset
) -> tuple[FastAPI, Settings]:
    library_dir = Path(tempfile.mkdtemp())
    settings = Settings(library_dir=str(library_dir), media_dir=str(MEDIA_DIR), models_dir=str(library_dir))

    for dataset in [dataset_image_bboxes_keypoint_copy, dataset_multi_view_tracking_and_image_copy]:
        dataset.info.id = dataset.info.name
        dataset.info.to_json(dataset._info_file)
        dataset._move_dataset(library_dir / dataset.info.name)

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override

    return app, settings


@pytest.fixture()
def app_and_settings_with_client_copy(app_and_settings_copy):
    return *app_and_settings_copy, TestClient(app_and_settings_copy[0])


@pytest.fixture()
def empty_app_and_settings() -> tuple[FastAPI, Settings]:
    temp_dir = Path(tempfile.mkdtemp())
    settings = Settings(library_dir=str(temp_dir), media_dir=str(temp_dir), models_dir=str(temp_dir))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override

    return app, settings


@pytest.fixture()
def empty_app_and_settings_with_client(empty_app_and_settings):
    return *empty_app_and_settings, TestClient(empty_app_and_settings[0])
