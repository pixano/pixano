# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from pixano.cli import app
from pixano.cli.data import _echo_follow_ups
from pixano.datasets import Dataset
from pixano.datasets.io.jobs import FollowUp, JobStore
from tests.datasets.io._review_fixture import (
    DROPPED_ENTITIES,
    KEPT_ENTITIES,
    REVIEW_DATASET_NAME,
    build_review_dataset,
)
from tests.datasets.io.formats.test_jsonl_importer import SPECS, materialize_corpus
from tests.fixtures.job_queue import queued_jobs


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


class TestExportCommand:
    """`--review-status` selects the model annotations to export (spec amendment 2026-10-05)."""

    @staticmethod
    def _data_dir_with_review_dataset(tmp_path: Path) -> Path:
        data_dir = tmp_path / "data"
        build_review_dataset(data_dir / "library" / REVIEW_DATASET_NAME)
        return data_dir

    @pytest.mark.parametrize(
        ("requested", "recorded", "exported"),
        [
            pytest.param(["accepted", "accepted"], ["accepted"], KEPT_ENTITIES, id="accepted-without-repeats"),
            pytest.param(
                ["accepted", "pending"],
                ["pending", "accepted"],
                KEPT_ENTITIES | DROPPED_ENTITIES,
                id="both-in-declaration-order",
            ),
        ],
    )
    def test_review_status_selects_model_annotations(
        self, tmp_path: Path, requested: list[str], recorded: list[str], exported: set[str]
    ):
        data_dir = self._data_dir_with_review_dataset(tmp_path)
        destination = tmp_path / "out"

        flags = [argument for status in requested for argument in ("--review-status", status)]
        result = runner.invoke(app, ["data", "export", str(data_dir), REVIEW_DATASET_NAME, str(destination), *flags])

        assert result.exit_code == 0, result.output
        line = json.loads((destination / "train" / "metadata.jsonl").read_text(encoding="utf-8").splitlines()[1])
        assert {entity["id"] for entity in line["entities"]} == exported
        spec = yaml.safe_load((destination / "dataset.yaml").read_text(encoding="utf-8"))
        assert spec["options"] == {"review_statuses": recorded}

    def test_review_status_applies_to_coco(self, tmp_path: Path):
        data_dir = self._data_dir_with_review_dataset(tmp_path)
        destination = tmp_path / "out"

        result = runner.invoke(
            app,
            ["data", "export", str(data_dir), REVIEW_DATASET_NAME, str(destination)]
            + ["--format", "coco", "--review-status", "accepted"],
        )

        assert result.exit_code == 0, result.output
        document = json.loads((destination / "instances_train.json").read_text(encoding="utf-8"))
        exported = {annotation["pixano_id"] for annotation in document["annotations"]}
        assert exported == {"e_human", "e_truth", "e_accepted", "e_child", "e_mixed"}

    @pytest.mark.parametrize("status", ["bogus", "corrected", "rejected"])
    def test_unknown_review_status_fails_before_writing(self, tmp_path: Path, status: str):
        data_dir = self._data_dir_with_review_dataset(tmp_path)
        destination = tmp_path / "out"

        result = runner.invoke(
            app, ["data", "export", str(data_dir), REVIEW_DATASET_NAME, str(destination), "--review-status", status]
        )

        assert result.exit_code == 1
        assert "review_statuses" in result.output
        assert not destination.exists()


class TestFormatsCommand:
    def test_lists_builtin_formats(self):
        result = runner.invoke(app, ["data", "formats"])
        assert result.exit_code == 0
        assert "pixano_jsonl" in result.output


@pytest.mark.parametrize("command", ["optimize", "fix-creation-dates"])
def test_dataset_maintenance_reports_busy_writer(tmp_path: Path, command: str):
    from pixano.datasets.locking import dataset_mutation_lock

    data_dir, source = _prepare_source(tmp_path)
    assert runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes"]).exit_code == 0
    acquired, release = threading.Event(), threading.Event()

    def writer():
        with dataset_mutation_lock(data_dir / "library" / "voc_like"):
            acquired.set()
            release.wait(30)

    thread = threading.Thread(target=writer)
    thread.start()
    try:
        assert acquired.wait(10)
        args = ["data", command, str(data_dir)]
        if command == "optimize":
            args.append("voc_like")
        result = runner.invoke(app, args)
        assert result.exit_code == 1, result.output
        assert "being modified" in result.output and "retry" in result.output
    finally:
        release.set()
        thread.join(timeout=10)


class TestJobsCommand:
    def test_cli_import_records_into_the_shared_store(self, tmp_path: Path):
        data_dir, source = _prepare_source(tmp_path)
        assert runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes"]).exit_code == 0

        from pixano.datasets.io.jobs import JobStore

        jobs = JobStore.for_data_dir(data_dir).list_jobs()
        assert jobs and jobs[0].status == "done" and jobs[0].kind == "import"
        assert jobs[0].spec["__source"] == str(source.resolve())
        assert jobs[0].cursor

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


class TestEmbeddingsAfterTheImport:
    """The embeddings job an import queues once done: asked for, or by default where it can run."""

    @staticmethod
    def _import(tmp_path: Path, *flags: str):
        data_dir, source = _prepare_source(tmp_path)
        result = runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes", *flags])
        return result, JobStore.for_data_dir(data_dir).list_jobs()[0]

    def test_by_default_without_a_queue_nothing_is_asked(self, tmp_path: Path):
        result, job = self._import(tmp_path)

        assert result.exit_code == 0, result.output
        assert job.follow_ups == [] and "Embeddings" not in result.output

    def test_by_default_where_the_job_can_run_it_is_queued(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, embeddings_declared: str
    ):
        monkeypatch.setenv("PIXANO_DATABASE_URL", embeddings_declared)
        monkeypatch.setenv("PIXANO_EMBEDDINGS_MODEL", "clip")

        result, job = self._import(tmp_path)

        assert result.exit_code == 0, result.output
        (follow_up,) = job.follow_ups
        assert f"Embeddings (clip) queued as job {follow_up.job_id}" in result.output
        assert queued_jobs(embeddings_declared) == [("embeddings", job.dataset, {"model": "clip"})]

    def test_no_embeddings_asks_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, embeddings_declared: str
    ):
        monkeypatch.setenv("PIXANO_DATABASE_URL", embeddings_declared)
        monkeypatch.setenv("PIXANO_EMBEDDINGS_MODEL", "clip")

        result, job = self._import(tmp_path, "--no-embeddings")

        assert result.exit_code == 0, result.output
        assert job.follow_ups == [] and queued_jobs(embeddings_declared) == []

    def test_asked_for_without_a_queue_the_import_says_why(self, tmp_path: Path):
        """The import is done all the same: its data is in."""
        result, job = self._import(tmp_path, "--embeddings", "--embeddings-model", "clip")

        assert result.exit_code == 0, result.output
        assert job.status == "done"
        assert "Embeddings (clip) not queued: no job queue is configured" in result.output

    def test_asked_for_without_a_model_says_how_to_name_one(self, tmp_path: Path):
        """The command asks no inference: it names its own option."""
        result, _ = self._import(tmp_path, "--embeddings")

        assert result.exit_code == 0, result.output
        assert "Embeddings not queued: no embeddings model — pass --embeddings-model" in result.output

    def test_a_model_named_asks_for_the_job(self, tmp_path: Path):
        result, job = self._import(tmp_path, "--embeddings-model", "clip")

        assert result.exit_code == 0, result.output
        assert "Embeddings (clip) not queued: no job queue is configured" in result.output

    def test_no_embeddings_reads_no_deployment(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """A setting the server would refuse does not stop an import that asks for no embeddings."""
        monkeypatch.setenv("PIXANO_EMBEDDINGS_AFTER_IMPORT", "maybe")

        result, job = self._import(tmp_path, "--no-embeddings")

        assert result.exit_code == 0, result.output
        assert job.status == "done" and job.follow_ups == []

    def test_an_invalid_deployment_leaves_the_import_done_and_says_so(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setenv("PIXANO_EMBEDDINGS_AFTER_IMPORT", "maybe")

        result, job = self._import(tmp_path)

        assert result.exit_code == 0, result.output
        assert job.status == "done"
        assert "Embeddings not considered: the deployment's settings are invalid" in result.output

    def test_by_default_an_import_without_a_still_image_asks_nothing(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, embeddings_declared: str
    ):
        """A video's frames are not still images: an import of them reads no refusal."""
        monkeypatch.setenv("PIXANO_DATABASE_URL", embeddings_declared)
        monkeypatch.setenv("PIXANO_EMBEDDINGS_MODEL", "clip")
        data_dir, source = _prepare_source(tmp_path, "frames_masks")

        result = runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes"])

        assert result.exit_code == 0, result.output
        assert JobStore.for_data_dir(data_dir).list_jobs()[0].follow_ups == []
        assert "Embeddings" not in result.output and queued_jobs(embeddings_declared) == []

    def test_the_dataset_is_looked_for_where_the_import_wrote_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, embeddings_declared: str
    ):
        """Whatever library the environment names, as the stack's does."""
        monkeypatch.setenv("PIXANO_DATABASE_URL", embeddings_declared)
        monkeypatch.setenv("PIXANO_EMBEDDINGS_MODEL", "clip")
        monkeypatch.setenv("LIBRARY_DIR", str(tmp_path / "elsewhere"))

        result, job = self._import(tmp_path)

        assert result.exit_code == 0, result.output
        (follow_up,) = job.follow_ups
        assert follow_up.job_id, follow_up

    def test_jobs_show_prints_the_follow_ups(self, tmp_path: Path):
        data_dir, source = _prepare_source(tmp_path)
        runner.invoke(app, ["data", "import", str(data_dir), str(source), "--yes", "--embeddings-model", "clip"])
        job = JobStore.for_data_dir(data_dir).list_jobs()[0]

        shown = runner.invoke(app, ["data", "jobs", str(data_dir), "show", job.id])

        assert shown.exit_code == 0, shown.output
        assert json.loads(shown.output)["follow_ups"] == [follow_up.to_json() for follow_up in job.follow_ups]


def test_an_import_in_a_process_whose_environment_the_server_refuses_ends_done(tmp_path: Path):
    """In a fresh process, loading the server is where the environment is read first."""
    data_dir, source = _prepare_source(tmp_path)

    imported = subprocess.run(
        [
            sys.executable,
            "-c",
            "from pixano.cli import app; app()",
            "data",
            "import",
            str(data_dir),
            str(source),
            "--yes",
        ],
        capture_output=True,
        text=True,
        env={**os.environ, "PIXANO_EMBEDDINGS_AFTER_IMPORT": "maybe"},
        check=False,
    )

    assert imported.returncode == 0, imported.stderr
    assert "Embeddings not considered: the deployment's settings are invalid" in imported.stderr
    assert JobStore.for_data_dir(data_dir).list_jobs()[0].status == "done"


def test_the_command_line_starts_without_the_server():
    """Loading the API reads every server setting: a value it refuses would break every command."""
    loaded = subprocess.run(
        [sys.executable, "-c", "import sys, pixano.cli; print('pixano.api' in sys.modules)"],
        capture_output=True,
        text=True,
        check=True,
    )

    assert loaded.stdout.strip() == "False"


def _interrupted_import(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, *flags: str) -> tuple[Path, Path, JobStore]:
    """Run an import of three images that fails after its first committed flush.

    Returns:
        The data directory, the source, and the job store, whose last job is the failed import.
    """
    import PIL.Image

    from pixano.datasets.io.engine import ImportEngine
    from pixano.datasets.io.formats.pixano_jsonl.importer import PixanoJsonlImporter

    source = tmp_path / "source"
    source.mkdir()
    for name in ("a", "b", "c"):
        PIL.Image.new("RGB", (8, 8), "red").save(source / f"{name}.png")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    monkeypatch.chdir(tmp_path)
    original_batches = PixanoJsonlImporter.iter_batches

    def fail_after_first(self, source, spec, plan, cursor=None):
        for ordinal, bundle in enumerate(original_batches(self, source, spec, plan, cursor)):
            if ordinal == 1:
                raise RuntimeError("interrupted CLI import")
            yield bundle

    class SmallFlushEngine(ImportEngine):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, flush_rows=1, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(PixanoJsonlImporter, "iter_batches", fail_after_first)
        patch.setattr("pixano.datasets.io.engine.ImportEngine", SmallFlushEngine)
        imported = runner.invoke(app, ["data", "import", str(data_dir), "source", "--name", "ds", "--yes", *flags])
    assert imported.exit_code == 1, imported.output
    return data_dir, source, JobStore.for_data_dir(data_dir)


class TestJobsCliRecovery:
    def test_cli_failure_boot_and_resume_preserve_all_records(self, tmp_path: Path, monkeypatch):
        from pixano.datasets.io.engine import state_dir
        from pixano.datasets.io.jobs import boot_recover

        data_dir, source, store = _interrupted_import(tmp_path, monkeypatch)
        job = store.list_jobs()[0]
        assert job.status == "error" and job.cursor
        assert job.spec["__source"] == str(source.resolve())
        staged = state_dir(data_dir) / "staging" / f"ds-{job.id}"
        assert Dataset(staged).open_table("records").count_rows() == 1
        boot_recover(data_dir)
        assert staged.exists()

        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        monkeypatch.chdir(elsewhere)
        resumed = runner.invoke(app, ["data", "jobs", str(data_dir), "resume", job.id])
        assert resumed.exit_code == 0, resumed.output
        assert store.get_job(job.id).status == "done"
        dataset = Dataset(data_dir / "library" / "ds")
        assert dataset.open_table("records").count_rows() == 3
        assert dataset.open_table("images").count_rows() == 3
        record_ids = {row.id for row in dataset.get_data("records")}
        assert {row.record_id for row in dataset.get_data("images")} == record_ids

    def test_a_resumed_import_queues_what_its_first_run_was_asked(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, embeddings_declared: str
    ):
        """Asked for when the import started, the embeddings are kept with its job through the failure."""
        monkeypatch.setenv("PIXANO_DATABASE_URL", embeddings_declared)
        data_dir, _, store = _interrupted_import(tmp_path, monkeypatch, "--embeddings", "--embeddings-model", "clip")
        job = store.list_jobs()[0]
        assert job.follow_ups == [FollowUp(kind="embeddings", params={"model": "clip"})]

        resumed = runner.invoke(app, ["data", "jobs", str(data_dir), "resume", job.id])

        assert resumed.exit_code == 0, resumed.output
        (follow_up,) = store.get_job(job.id).follow_ups
        assert f"Embeddings (clip) queued as job {follow_up.job_id}" in resumed.output
        assert queued_jobs(embeddings_declared) == [("embeddings", store.get_job(job.id).dataset, {"model": "clip"})]

    @pytest.mark.parametrize("python_option", ["--importer", "--info-py"])
    def test_file_based_python_import_is_restart_only(self, tmp_path: Path, monkeypatch, python_option):
        from pixano.datasets.io.engine import ImportEngine
        from pixano.datasets.io.jobs import JobStore
        from pixano.datasets.io.spec import ImportSpec, resolve_dataset_info
        from tests.datasets.io._toy_importer import ToyImporter

        data_dir, source = _prepare_source(tmp_path)
        monkeypatch.setattr("pixano.cli._schema_loader.load_importer", lambda _: ToyImporter(num_records=2))
        info = resolve_dataset_info(ImportSpec.model_validate(SPECS["voc_like"]))
        monkeypatch.setattr("pixano.cli._schema_loader.load_info", lambda _: info)

        def fail_at_finalize(self, *args, **kwargs):
            raise RuntimeError("finalization interrupted")

        monkeypatch.setattr(ImportEngine, "_finalize", fail_at_finalize)
        imported = runner.invoke(
            app, ["data", "import", str(data_dir), str(source), "--yes", python_option, "custom.py:Custom"]
        )
        assert imported.exit_code == 1, imported.output
        job = JobStore.for_data_dir(data_dir).list_jobs()[0]
        assert job.status == "error" and not job.cursor
        resumed = runner.invoke(app, ["data", "jobs", str(data_dir), "resume", job.id])
        assert resumed.exit_code == 1
        assert "no committed checkpoint" in resumed.output

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


class TestSayingWhatBecameOfTheFollowUps:
    def test_each_job_on_a_line_of_its_own(self, capsys: pytest.CaptureFixture[str]):
        """The embeddings of every model a dataset holds: one line each, queued or not."""
        _echo_follow_ups(
            [
                FollowUp(kind="embeddings", params={"model": "clip"}, job_id="j1"),
                FollowUp(kind="embeddings", params={"model": "siglip"}, error="not queued: no worker"),
            ]
        )

        out, err = capsys.readouterr()
        assert out == "Embeddings (clip) queued as job j1: follow it in the dataset's Jobs panel.\n"
        assert err == "Embeddings (siglip) not queued: no worker\n"
