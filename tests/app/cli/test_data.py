# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from pixano.app.cli import app


runner = CliRunner()


def _create_source_dir(base: Path, name: str = "my_dataset") -> Path:
    """Create a minimal source directory with split folders and files."""
    source = base / name
    train = source / "train"
    train.mkdir(parents=True)
    (train / "img_001.jpg").write_text("fake image 1")
    (train / "img_002.jpg").write_text("fake image 2")
    val = source / "val"
    val.mkdir(parents=True)
    (val / "img_003.jpg").write_text("fake image 3")
    return source


def _mock_builder():
    """Return a mock builder class and instance."""
    mock_dataset = MagicMock()
    mock_dataset.num_rows = 3
    mock_builder_instance = MagicMock()
    mock_builder_instance.build.return_value = mock_dataset
    mock_builder_cls = MagicMock(return_value=mock_builder_instance)
    return mock_builder_cls, mock_builder_instance


class TestImportCopiesMedia:
    @patch("importlib.import_module")
    def test_create_copies_media(self, mock_import_module):
        """Source files appear in data_dir/media/<name>/."""
        mock_builder_cls, _ = _mock_builder()
        mock_module = MagicMock()
        mock_module.ImageFolderBuilder = mock_builder_cls
        mock_import_module.return_value = mock_module

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--type",
                    "image",
                ],
            )

            assert result.exit_code == 0, result.stdout
            dest = data_dir / "media" / "my_dataset"
            assert dest.is_dir()
            assert (dest / "train" / "img_001.jpg").read_text() == "fake image 1"
            assert (dest / "train" / "img_002.jpg").read_text() == "fake image 2"
            assert (dest / "val" / "img_003.jpg").read_text() == "fake image 3"

    def test_create_fails_if_dest_exists(self):
        """Exit code != 0 and error message contains 'already exists'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()
            # Pre-create the destination
            dest = data_dir / "media" / "my_dataset"
            dest.mkdir(parents=True)

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--type",
                    "image",
                ],
            )

            assert result.exit_code != 0
            assert "already exists" in result.stdout or "already exists" in (result.stderr or "")

    @patch("importlib.import_module")
    def test_overwrite_clears_and_copies(self, mock_import_module):
        """Old files removed, new files present after overwrite."""
        mock_builder_cls, _ = _mock_builder()
        mock_module = MagicMock()
        mock_module.ImageFolderBuilder = mock_builder_cls
        mock_import_module.return_value = mock_module

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()

            # Pre-create destination with an old file
            dest = data_dir / "media" / "my_dataset"
            dest.mkdir(parents=True)
            (dest / "old_file.txt").write_text("old content")

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--type",
                    "image",
                    "--mode",
                    "overwrite",
                ],
            )

            assert result.exit_code == 0, result.stdout
            assert not (dest / "old_file.txt").exists()
            assert (dest / "train" / "img_001.jpg").read_text() == "fake image 1"

    @patch("importlib.import_module")
    def test_add_merges(self, mock_import_module):
        """Existing files preserved, new files added."""
        mock_builder_cls, _ = _mock_builder()
        mock_module = MagicMock()
        mock_module.ImageFolderBuilder = mock_builder_cls
        mock_import_module.return_value = mock_module

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()

            # Pre-create destination with an existing file
            dest = data_dir / "media" / "my_dataset" / "train"
            dest.mkdir(parents=True)
            (dest / "existing.jpg").write_text("existing content")

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--type",
                    "image",
                    "--mode",
                    "add",
                ],
            )

            assert result.exit_code == 0, result.stdout
            # Existing file preserved
            assert (dest / "existing.jpg").read_text() == "existing content"
            # New files added
            assert (dest / "img_001.jpg").read_text() == "fake image 1"

    @patch("importlib.import_module")
    def test_name_override(self, mock_import_module):
        """--name custom copies to data_dir/media/custom/."""
        mock_builder_cls, _ = _mock_builder()
        mock_module = MagicMock()
        mock_module.ImageFolderBuilder = mock_builder_cls
        mock_import_module.return_value = mock_module

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--type",
                    "image",
                    "--name",
                    "custom",
                ],
            )

            assert result.exit_code == 0, result.stdout
            dest = data_dir / "media" / "custom"
            assert dest.is_dir()
            assert (dest / "train" / "img_001.jpg").exists()
            # Original name dir should not exist
            assert not (data_dir / "media" / "my_dataset").exists()
