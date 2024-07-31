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
        settings = Settings(library_dir="/home/user/library", data_dir="/home/user/data", model_dir="/home/user/model")

        assert settings.library_dir == "/home/user/library"
        assert settings.data_dir == Path("/home/user/data")
        assert settings.model_dir == Path("/home/user/model")

        # Test 2 all undefined:
        settings = Settings()
        assert settings.library_dir == (Path.cwd() / "library").as_posix()
        assert settings.data_dir == Path(settings.library_dir)
        assert settings.model_dir == settings.data_dir / "models"

    @pytest.mark.skip(reason="Not implemented")
    def test_init_s3(self): ...


def test_get_settings():
    assert get_settings() == Settings()
