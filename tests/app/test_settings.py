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
        # Test 1 all defined:
        settings = Settings(
            library_dir="/home/user/library", media_dir="/home/user/media", models_dir="/home/user/models"
        )

        assert settings.library_dir == Path("/home/user/library")
        assert settings.media_dir == Path("/home/user/media")
        assert settings.models_dir == Path("/home/user/models")

        # Test 2 all undefined:
        settings = Settings()
        assert settings.library_dir == Path.cwd() / "library"
        assert settings.media_dir == Path.cwd() / "media"
        assert settings.models_dir == settings.library_dir / "models"

    @pytest.mark.skip(reason="Not implemented")
    def test_init_s3(self): ...


def test_get_settings():
    assert get_settings() == Settings()
