# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest

from pixano.app.settings import Settings, get_settings


class TestSettings:
    def test_init_path(self):
        # Test with explicit library_dir/media_dir overrides (backward compat)
        settings = Settings(
            library_dir="/home/user/library", media_dir="/home/user/media", models_dir="/home/user/models"
        )

        assert settings.library_dir == Path("/home/user/library")
        assert settings.media_dir == Path("/home/user/media")
        assert settings.models_dir == Path("/home/user/models")

    def test_init_defaults(self):
        # All undefined: derived from data_dir (cwd by default)
        settings = Settings()
        assert settings.library_dir == Path.cwd() / "library"
        assert settings.media_dir == Path.cwd() / "media"
        assert settings.models_dir == Path.cwd() / "models"

    def test_init_data_dir(self):
        settings = Settings(data_dir="/home/user/data")
        assert settings.data_dir == Path("/home/user/data")
        assert settings.library_dir == Path("/home/user/data/library")
        assert settings.media_dir == Path("/home/user/data/media")
        assert settings.models_dir == Path("/home/user/data/models")

    def test_init_data_dir_with_overrides(self):
        settings = Settings(
            data_dir="/home/user/data",
            library_dir="/other/library",
            media_dir="/other/media",
        )
        assert settings.data_dir == Path("/home/user/data")
        assert settings.library_dir == Path("/other/library")
        assert settings.media_dir == Path("/other/media")
        assert settings.models_dir == Path("/home/user/data/models")

    @pytest.mark.skip(reason="Not implemented")
    def test_init_s3(self): ...


def test_get_settings():
    assert get_settings() == Settings()
