# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path

from typer.testing import CliRunner

from pixano.app.cli import app


runner = CliRunner()


class TestInit:
    def test_creates_subdirectories(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "my_data"
            result = runner.invoke(app, ["init", str(data_dir)])
            assert result.exit_code == 0
            assert (data_dir / "library").is_dir()
            assert (data_dir / "media").is_dir()
            assert (data_dir / "models").is_dir()
            assert "Initialized" in result.stdout

    def test_idempotent(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "my_data"
            result1 = runner.invoke(app, ["init", str(data_dir)])
            assert result1.exit_code == 0
            result2 = runner.invoke(app, ["init", str(data_dir)])
            assert result2.exit_code == 0
            assert (data_dir / "library").is_dir()
            assert (data_dir / "media").is_dir()
            assert (data_dir / "models").is_dir()
