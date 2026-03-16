# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from pixano.cli import app


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


def _create_info_file(base: Path, name: str = "my_dataset", workspace: str = "image") -> Path:
    """Create a minimal info.py file with a DatasetInfo object."""
    info_file = base / "info.py"
    info_file.write_text(
        f"""\
from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import Record, Entity, Image

dataset_info = DatasetInfo(
    name="{name}",
    description="Test dataset",
    workspace=WorkspaceType.{workspace.upper()},
    record=Record,
    entity=Entity,
    views={{"image": Image}},
)
""",
        encoding="utf-8",
    )
    return info_file


def _mock_builder():
    """Return a mock builder class and instance."""
    mock_dataset = MagicMock()
    mock_dataset.num_rows = 3
    mock_builder_instance = MagicMock()
    mock_builder_instance.build.return_value = mock_dataset
    # Provide a realistic preflight_metadata return value
    mock_report = MagicMock()
    mock_report.warning_count = 0
    mock_report.normalized_examples = []
    mock_report.aliases = {}
    mock_report.inferred = {}
    mock_report.errors = {}
    mock_builder_instance.preflight_metadata.return_value = mock_report
    mock_builder_cls = MagicMock(return_value=mock_builder_instance)
    return mock_builder_cls, mock_builder_instance


class TestImportWithInfo:
    @patch("importlib.import_module")
    def test_create_builds_dataset(self, mock_import_module):
        """Import with --info creates a dataset in the library directory."""
        mock_builder_cls, mock_builder_instance = _mock_builder()
        mock_module = MagicMock()
        mock_module.ImageFolderBuilder = mock_builder_cls
        mock_import_module.return_value = mock_module

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()
            info_file = _create_info_file(base)

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--info",
                    f"{info_file}:dataset_info",
                ],
            )

            assert result.exit_code == 0, result.output
            # Builder should have been constructed with expected args
            mock_builder_cls.assert_called_once()
            call_kwargs = mock_builder_cls.call_args.kwargs
            assert call_kwargs["target_name"] == "my_dataset"
            assert call_kwargs["source_dir"] == source

    def test_create_fails_if_dest_exists(self):
        """Exit code != 0 and error message contains 'already exists'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()
            info_file = _create_info_file(base)
            # Pre-create the target dataset directory
            dest = data_dir / "library" / "my_dataset"
            dest.mkdir(parents=True)

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--info",
                    f"{info_file}:dataset_info",
                ],
            )

            assert result.exit_code != 0
            assert "already exists" in result.output or "already exists" in (result.stderr or "")

    @patch("importlib.import_module")
    def test_overwrite_mode(self, mock_import_module):
        """--mode overwrite should pass mode='overwrite' to builder."""
        mock_builder_cls, _ = _mock_builder()
        mock_module = MagicMock()
        mock_module.ImageFolderBuilder = mock_builder_cls
        mock_import_module.return_value = mock_module

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()
            info_file = _create_info_file(base)
            # Pre-create destination
            dest = data_dir / "library" / "my_dataset"
            dest.mkdir(parents=True)

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--info",
                    f"{info_file}:dataset_info",
                    "--mode",
                    "overwrite",
                ],
            )

            assert result.exit_code == 0, result.output
            mock_builder_instance = mock_builder_cls.return_value
            mock_builder_instance.build.assert_called_once_with(mode="overwrite")

    @patch("importlib.import_module")
    def test_add_mode(self, mock_import_module):
        """--mode add should pass mode='add' to builder."""
        mock_builder_cls, _ = _mock_builder()
        mock_module = MagicMock()
        mock_module.ImageFolderBuilder = mock_builder_cls
        mock_import_module.return_value = mock_module

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()
            info_file = _create_info_file(base)

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--info",
                    f"{info_file}:dataset_info",
                    "--mode",
                    "add",
                ],
            )

            assert result.exit_code == 0, result.output
            mock_builder_instance = mock_builder_cls.return_value
            mock_builder_instance.build.assert_called_once_with(mode="add")

    @patch("importlib.import_module")
    def test_dataset_name_derived_from_info_name(self, mock_import_module):
        """Target dataset name is the snake_case of info.name."""
        mock_builder_cls, _ = _mock_builder()
        mock_module = MagicMock()
        mock_module.ImageFolderBuilder = mock_builder_cls
        mock_import_module.return_value = mock_module

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()
            info_file = _create_info_file(base, name="Custom Dataset Name!")

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--info",
                    f"{info_file}:dataset_info",
                ],
            )

            assert result.exit_code == 0, result.output
            call_kwargs = mock_builder_cls.call_args.kwargs
            assert call_kwargs["target_name"] == "custom_dataset_name"

    @patch("importlib.import_module")
    def test_builder_receives_source_dir(self, mock_import_module):
        """Builder should be constructed with source_dir pointing to the source."""
        mock_builder_cls, _ = _mock_builder()
        mock_module = MagicMock()
        mock_module.ImageFolderBuilder = mock_builder_cls
        mock_import_module.return_value = mock_module

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()
            info_file = _create_info_file(base)

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--info",
                    f"{info_file}:dataset_info",
                ],
            )

            assert result.exit_code == 0, result.output
            call_kwargs = mock_builder_cls.call_args.kwargs
            assert call_kwargs["source_dir"] == source

    @patch("importlib.import_module")
    def test_library_dir_is_data_dir_library(self, mock_import_module):
        """Builder library_dir should be data_dir/library."""
        mock_builder_cls, _ = _mock_builder()
        mock_module = MagicMock()
        mock_module.ImageFolderBuilder = mock_builder_cls
        mock_import_module.return_value = mock_module

        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()
            info_file = _create_info_file(base)

            result = runner.invoke(
                app,
                [
                    "data",
                    "import",
                    str(data_dir),
                    str(source),
                    "--info",
                    f"{info_file}:dataset_info",
                ],
            )

            assert result.exit_code == 0, result.output
            call_kwargs = mock_builder_cls.call_args.kwargs
            assert call_kwargs["library_dir"] == data_dir / "library"

    def test_info_is_required(self):
        """Missing --info should exit with error."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base = Path(tmpdir)
            source = _create_source_dir(base)
            data_dir = base / "data"
            data_dir.mkdir()

            result = runner.invoke(app, ["data", "import", str(data_dir), str(source)])

            assert result.exit_code != 0
            assert "--info" in result.output
