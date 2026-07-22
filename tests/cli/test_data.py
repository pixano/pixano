# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from pathlib import Path

import yaml
from typer.testing import CliRunner

from pixano.cli import app
from pixano.datasets import Dataset
from tests.datasets.io.formats.test_jsonl_importer import SPECS, materialize_corpus


runner = CliRunner()


def _prepare_source(tmp_path: Path, name: str = "voc_like") -> tuple[Path, Path]:
    """Materialize a golden corpus with its dataset.yaml and an empty data dir."""
    source = materialize_corpus(name, tmp_path / "src")
    spec_payload = {"pixano": 2, "format": "pixano_jsonl", **SPECS[name]}
    (source / "dataset.yaml").write_text(yaml.safe_dump(spec_payload, sort_keys=False))
    data_dir = tmp_path / "data"
    (data_dir / "library").mkdir(parents=True)
    return data_dir, source


class TestImportCommand:
    def test_dry_run_writes_nothing(self, tmp_path: Path):
        data_dir, source = _prepare_source(tmp_path)
        result = runner.invoke(app, ["data", "import", str(data_dir), str(source), "--dry-run"])
        assert result.exit_code == 0, result.output
        assert "Dry-run completed" in result.output
        assert not any((data_dir / "library").iterdir())

    def test_import_export_reimport_round_trip(self, tmp_path: Path):
        data_dir, source = _prepare_source(tmp_path)

        imported = runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes"])
        assert imported.exit_code == 0, imported.output
        assert "imported successfully" in imported.output

        dataset = Dataset(data_dir / "library" / "voc_like")
        assert dataset.open_table("records").count_rows() == 1

        destination = tmp_path / "exported"
        exported = runner.invoke(app, ["data", "export", str(data_dir), "voc_like", str(destination)])
        assert exported.exit_code == 0, exported.output
        assert (destination / "dataset.yaml").is_file()

        # The exported folder re-imports via its own dataset.yaml — no flags needed.
        data_dir_2 = tmp_path / "data2"
        (data_dir_2 / "library").mkdir(parents=True)
        reimported = runner.invoke(
            app, ["data", "import", str(data_dir_2), str(destination), "--yes", "--name", "voc_like"]
        )
        assert reimported.exit_code == 0, reimported.output
        second = Dataset(data_dir_2 / "library" / "voc_like")
        first_ids = sorted(row["id"] for row in dataset.open_table("bboxes").search().select(["id"]).to_list())
        second_ids = sorted(row["id"] for row in second.open_table("bboxes").search().select(["id"]).to_list())
        assert second_ids == first_ids

    def test_invalid_source_fails_with_findings(self, tmp_path: Path):
        data_dir, source = _prepare_source(tmp_path)
        metadata = source / "train" / "metadata.jsonl"
        metadata.write_text(metadata.read_text() + '{"views": {"imge": "nope.jpg"}}\n')
        result = runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes"])
        assert result.exit_code == 1
        assert "undeclared_view" in result.output
        assert not any((data_dir / "library").iterdir())

    def test_create_refuses_existing(self, tmp_path: Path):
        data_dir, source = _prepare_source(tmp_path)
        assert runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes"]).exit_code == 0
        again = runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes"])
        assert again.exit_code == 1
        assert "already exists" in again.output


class TestFormatsCommand:
    def test_lists_builtin_formats(self):
        result = runner.invoke(app, ["data", "formats"])
        assert result.exit_code == 0
        assert "pixano_jsonl" in result.output


class TestMigrateJsonlCommand:
    def test_migrates_v1_tree(self, tmp_path: Path):
        v1_root = Path(__file__).parents[1] / "assets" / "jsonl_v1" / "canonical"
        destination = tmp_path / "migrated"
        result = runner.invoke(app, ["data", "migrate-jsonl", str(v1_root), str(destination)])
        assert result.exit_code == 0, result.output
        assert "Migrated 1 line(s)" in result.output

        lines = (destination / "train" / "metadata.jsonl").read_text().splitlines()
        assert json.loads(lines[0])["$pixano"] == "jsonl/2"
        migrated = json.loads(lines[1])
        assert migrated["attrs"]["status"] == "validated"
        kinds = [a["kind"] for a in migrated["entities"][0]["annotations"]]
        assert kinds == ["bbox", "keypoints"]


class TestJobsCommand:
    def test_cli_import_records_into_the_shared_store(self, tmp_path: Path):
        data_dir, source = _prepare_source(tmp_path)
        assert runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes"]).exit_code == 0

        from pixano.datasets.io.jobs import JobStore

        jobs = JobStore.for_data_dir(data_dir).list_jobs()
        assert jobs and jobs[0].status == "done" and jobs[0].kind == "import"

        listing = runner.invoke(app, ["data", "jobs", str(data_dir), "list"])
        assert listing.exit_code == 0 and "done" in listing.output

        shown = runner.invoke(app, ["data", "jobs", str(data_dir), "show", jobs[0].id])
        assert shown.exit_code == 0 and jobs[0].id in shown.output

    def test_cancel_terminal_job_errors(self, tmp_path: Path):
        data_dir, source = _prepare_source(tmp_path)
        runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes"])
        from pixano.datasets.io.jobs import JobStore

        job = JobStore.for_data_dir(data_dir).list_jobs()[0]
        result = runner.invoke(app, ["data", "jobs", str(data_dir), "cancel", job.id])
        assert result.exit_code == 1 and "already" in result.output


class TestJobsCliRecovery:
    def test_jobs_command_marks_dead_running_jobs_interrupted(self, tmp_path: Path):
        data_dir, source = _prepare_source(tmp_path)
        from pixano.datasets.io.jobs import JobStore

        store = JobStore.for_data_dir(data_dir)
        job = store.create_job("import")
        store.update_job(job.id, status="running", pid=999_999_999)

        result = runner.invoke(app, ["data", "jobs", str(data_dir), "list"])
        assert result.exit_code == 0
        assert "interrupted" in result.output
        assert store.get_job(job.id).status == "interrupted"


class TestFixCreationDates:
    def _import_legacy(self, tmp_path: Path) -> Path:
        """Import a dataset, then strip creation_date to simulate a legacy library."""
        data_dir, source = _prepare_source(tmp_path)
        assert runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes"]).exit_code == 0
        info_json = next((data_dir / "library").glob("*/info.json"))
        raw = json.loads(info_json.read_text(encoding="utf-8"))
        raw.pop("creation_date", None)
        raw["custom_note"] = "keep me"  # unknown key: must survive the rewrite
        info_json.write_text(json.dumps(raw, indent=4), encoding="utf-8")
        return data_dir

    def test_backfills_from_oldest_record_preserving_unknown_keys(self, tmp_path: Path):
        from datetime import datetime, timezone

        data_dir = self._import_legacy(tmp_path)
        result = runner.invoke(app, ["data", "fix-creation-dates", str(data_dir)])
        assert result.exit_code == 0, result.output
        assert "Updated" in result.output
        info_json = next((data_dir / "library").glob("*/info.json"))
        raw = json.loads(info_json.read_text(encoding="utf-8"))
        assert raw["creation_date"]
        assert raw["custom_note"] == "keep me"  # raw-JSON patch, not a lossy model round-trip
        dataset = Dataset(info_json.parent)
        oldest = dataset.get_data("records", sortcol="created_at", order="asc", limit=1)[0].created_at
        assert datetime.fromisoformat(raw["creation_date"]) == oldest.astimezone(timezone.utc)
        assert info_json.with_suffix(".json.bak").exists()

    def test_second_run_skips(self, tmp_path: Path):
        data_dir = self._import_legacy(tmp_path)
        assert runner.invoke(app, ["data", "fix-creation-dates", str(data_dir)]).exit_code == 0
        second = runner.invoke(app, ["data", "fix-creation-dates", str(data_dir)])
        assert second.exit_code == 0
        assert "0 dataset(s) updated" in second.output

    def test_malformed_sibling_does_not_abort(self, tmp_path: Path):
        data_dir = self._import_legacy(tmp_path)
        broken = data_dir / "library" / "aaa_broken"  # sorts before the real dataset
        broken.mkdir()
        (broken / "info.json").write_text("{not json", encoding="utf-8")
        result = runner.invoke(app, ["data", "fix-creation-dates", str(data_dir)])
        assert result.exit_code == 0, result.output
        assert "Error processing 'aaa_broken'" in result.output
        assert "1 dataset(s) updated" in result.output
