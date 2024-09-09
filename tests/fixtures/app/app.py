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

from pixano.app.main import create_app
from pixano.app.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY


LIBRARY_DIR = ASSETS_DIRECTORY / "library"


@pytest.fixture(scope="session")
def app_and_settings(
    dataset_image_bboxes_keypoint: Dataset, dataset_multi_view_tracking_and_image: Dataset
) -> tuple[FastAPI, Settings]:  # args to ensure the fixture is called before the app fixture
    settings = Settings(library_dir=str(LIBRARY_DIR))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override

    return app, settings


@pytest.fixture()
def app_and_settings_with_copy(
    dataset_image_bboxes_keypoint_copy: Dataset, dataset_multi_view_tracking_and_image_copy: Dataset
) -> tuple[FastAPI, Settings]:
    settings = Settings(library_dir=str(dataset_image_bboxes_keypoint_copy.path.parent))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override

    return app, settings


@pytest.fixture()
def empty_app_and_settings() -> tuple[FastAPI, Settings]:
    temp_dir = Path(tempfile.mkdtemp())
    settings = Settings(library_dir=str(temp_dir))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override

    return app, settings
