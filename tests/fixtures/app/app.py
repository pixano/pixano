# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from functools import lru_cache
from pathlib import Path

import pytest

from pixano.app.main import create_app
from pixano.app.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset


@pytest.fixture()
def app_and_settings(dataset_image_bboxes_keypoint: Dataset, dataset_multi_view_tracking_and_image: Dataset):
    temp_dir = Path(tempfile.mkdtemp())
    settings = Settings(library_dir=str(temp_dir))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override

    for dataset in [dataset_image_bboxes_keypoint, dataset_multi_view_tracking_and_image]:
        dataset._move_dataset(Path(temp_dir) / dataset.info.name)

    return app, settings


@pytest.fixture()
def empty_app_and_settings():
    temp_dir = Path(tempfile.mkdtemp())
    settings = Settings(library_dir=str(temp_dir))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override

    return app, settings
