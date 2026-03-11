from pathlib import Path
from unittest.mock import MagicMock, patch

from PIL import Image as PILImage
from typer.testing import CliRunner

from pixano.cli import app
from pixano.datasets import Dataset


runner = CliRunner()
VOC_INFO_SPEC = f"{(Path(__file__).resolve().parents[2] / 'examples' / 'voc' / 'info.py')}:{'dataset_info'}"
VQAV2_INFO_SPEC = f"{(Path(__file__).resolve().parents[2] / 'examples' / 'vqav2' / 'info.py')}:{'dataset_info'}"


def test_data_import_dry_run_reports_clean_metadata(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    source_dir = tmp_path / "voc"
    split_dir = source_dir / "train"
    split_dir.mkdir(parents=True)
    (split_dir / "item_0.jpg").write_bytes(b"fake-image-bytes")
    (split_dir / "metadata.jsonl").write_text('{"image":"item_0.jpg"}\n', encoding="utf-8")

    result = runner.invoke(
        app,
        [
            "data",
            "import",
            str(data_dir),
            str(source_dir),
            "--info",
            VOC_INFO_SPEC,
            "--dry-run",
        ],
    )

    assert result.exit_code == 0
    assert "Metadata validation passed with 0 warnings" in result.output
    assert "Mapping: image -> logical view 'image'" in result.output
    assert "Dry-run completed successfully. No dataset was created." in result.output
    assert not (data_dir / "library" / "voc_2007_sample").exists()


def test_data_import_dry_run_strict_rejects_aliases(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    source_dir = tmp_path / "voc"
    split_dir = source_dir / "train"
    split_dir.mkdir(parents=True)
    (split_dir / "item_0.jpg").write_bytes(b"fake-image-bytes")
    (split_dir / "metadata.jsonl").write_text(
        '{"image":"item_0.jpg","objects":{"category":["person"]}}\n', encoding="utf-8"
    )

    result = runner.invoke(
        app,
        [
            "data",
            "import",
            str(data_dir),
            str(source_dir),
            "--info",
            VOC_INFO_SPEC,
            "--dry-run",
            "--metadata-validation",
            "strict",
        ],
    )

    assert result.exit_code == 1
    assert "Metadata validation passed with 0 warnings" in result.output
    assert "Error: aliased_metadata_key" in result.output


def test_data_import_requires_info(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    source_dir = tmp_path / "voc"
    (source_dir / "train").mkdir(parents=True)

    result = runner.invoke(app, ["data", "import", str(data_dir), str(source_dir)])

    assert result.exit_code != 0
    assert "--info" in result.output


@patch("importlib.import_module")
def test_data_import_uses_dataset_info_workspace_and_snake_case_name(mock_import_module, tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    source_dir = tmp_path / "voc"
    split_dir = source_dir / "train"
    split_dir.mkdir(parents=True)
    (split_dir / "item_0.jpg").write_bytes(b"fake-image-bytes")
    (split_dir / "metadata.jsonl").write_text('{"image":"item_0.jpg"}\n', encoding="utf-8")

    mock_dataset = MagicMock()
    mock_dataset.num_rows = 1
    mock_builder_instance = MagicMock()
    mock_builder_instance.preflight_metadata.return_value.warning_count = 0
    mock_builder_instance.preflight_metadata.return_value.normalized_examples = []
    mock_builder_instance.preflight_metadata.return_value.aliases = {}
    mock_builder_instance.preflight_metadata.return_value.inferred = {}
    mock_builder_instance.preflight_metadata.return_value.errors = {}
    mock_builder_instance.build.return_value = mock_dataset
    mock_builder_cls = MagicMock(return_value=mock_builder_instance)
    mock_module = MagicMock()
    mock_module.ImageFolderBuilder = mock_builder_cls
    mock_import_module.return_value = mock_module

    result = runner.invoke(
        app,
        [
            "data",
            "import",
            str(data_dir),
            str(source_dir),
            "--info",
            VOC_INFO_SPEC,
        ],
    )

    assert result.exit_code == 0
    mock_import_module.assert_called_once_with("pixano.datasets.builders.folders.image")
    mock_builder_cls.assert_called_once()
    assert mock_builder_cls.call_args.kwargs["target_name"] == "voc_2007_sample"


def test_data_import_preserves_message_question_type(tmp_path: Path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    source_dir = tmp_path / "vqav2"
    split_dir = source_dir / "validation"
    split_dir.mkdir(parents=True)

    image_path = split_dir / "item_0.jpg"
    PILImage.new("RGB", (4, 4), color=(255, 0, 0)).save(image_path)
    (split_dir / "metadata.jsonl").write_text(
        (
            '{"image":"item_0.jpg","messages":[{"question":{"content":"Is this red?",'
            '"question_type":"open"},"responses":[{"content":"yes"}]}]}\n'
        ),
        encoding="utf-8",
    )

    result = runner.invoke(
        app,
        [
            "data",
            "import",
            str(data_dir),
            str(source_dir),
            "--info",
            VQAV2_INFO_SPEC,
        ],
    )

    assert result.exit_code == 0, result.output

    dataset = Dataset(data_dir / "library" / "vqav2_sample")
    rows = dataset.open_table("messages").search().limit(2).to_list()

    assert rows[0]["type"] == "QUESTION"
    assert rows[0]["question_type"] == "OPEN"
    assert rows[1]["type"] == "ANSWER"
    assert rows[1]["question_type"] == ""
