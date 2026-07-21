# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest

from pixano.datasets import Dataset
from pixano.datasets.io import ImportSpec, import_dataset
from pixano.datasets.io.engine import ImportEngine
from pixano.datasets.io.errors import JobStateError
from tests.datasets.io._toy_importer import ToyImporter


def _spec(name: str, mode: str = "create", namespace: str = "") -> ImportSpec:
    payload: dict = {"dataset": {"name": name, "workspace": "image"}, "mode": mode}
    if namespace:
        payload["ids"] = {"namespace": namespace}
    return ImportSpec.model_validate(payload)


def _counts(dataset: Dataset) -> dict[str, int]:
    return {name: dataset.open_table(name).count_rows() for name in dataset.info.tables}


@pytest.fixture()
def base_dataset(tmp_path: Path) -> tuple[Path, dict[str, int]]:
    import_dataset(
        tmp_path / "src", tmp_path / "data", _spec("ds", namespace="base"), importer=ToyImporter(num_records=10)
    )
    dataset = Dataset(tmp_path / "data" / "library" / "ds")
    return tmp_path, _counts(dataset)


class TestRollback:
    def test_clean_add_rollback_restores_versions(self, base_dataset):
        tmp_path, before = base_dataset
        result = import_dataset(
            tmp_path / "src2",
            tmp_path / "data",
            _spec("ds", mode="add", namespace="added"),
            importer=ToyImporter(num_records=7),
            job_id="addjob",
        )
        dataset = Dataset(result.dataset_path)
        assert dataset.open_table("records").count_rows() == 17

        removed = ImportEngine(tmp_path / "data").rollback(result.dataset_path, "addjob")
        assert removed == {}  # fast path: version restore
        assert _counts(Dataset(result.dataset_path)) == before
        assert not (result.dataset_path / "imports" / "addjob.manifest.json").exists()

    def test_rollback_after_concurrent_edit_takes_namespace_path(self, base_dataset):
        tmp_path, before = base_dataset
        result = import_dataset(
            tmp_path / "src2",
            tmp_path / "data",
            _spec("ds", mode="add", namespace="added"),
            importer=ToyImporter(num_records=7),
            job_id="addjob2",
        )
        dataset = Dataset(result.dataset_path)

        # Interleaved user edit: a GUI-created record AFTER the import.
        from pixano.schemas import Record

        dataset.add_records({"records": Record(id="user_manual_row")}, check_integrity="none")

        removed = ImportEngine(tmp_path / "data").rollback(result.dataset_path, "addjob2")
        assert removed and removed["records"] == 7  # surgical path: namespace delete
        after = Dataset(result.dataset_path)
        assert after.open_table("records").count_rows() == before["records"] + 1
        assert after.get_data("records", ids="user_manual_row") is not None  # edit survives

    def test_rollback_without_manifest_is_a_typed_error(self, base_dataset):
        tmp_path, _ = base_dataset
        with pytest.raises(JobStateError, match="manifest"):
            ImportEngine(tmp_path / "data").rollback(tmp_path / "data" / "library" / "ds", "ghost")

    def test_runner_rollback_flips_job_status(self, base_dataset):
        tmp_path, before = base_dataset
        from pixano.datasets.io.jobs import JobRunner, JobStore

        store = JobStore.for_data_dir(tmp_path / "data")
        runner = JobRunner(store, tmp_path / "data")
        job = runner.submit_import(
            str(tmp_path / "src3"),
            {"dataset": {"name": "ds", "workspace": "image"}, "mode": "add", "ids": {"namespace": "j3"}},
        )
        # The registry can't detect a toy source; run the import directly instead.
        runner.join(timeout=30)
        final = store.get_job(job.id)
        if final.status != "done":
            import_dataset(
                tmp_path / "src3",
                tmp_path / "data",
                _spec("ds", mode="add", namespace="j3"),
                importer=ToyImporter(num_records=3),
                job_id=job.id,
            )
            store.update_job(
                job.id,
                status="done",
                manifest_path=str(tmp_path / "data" / "library" / "ds" / "imports" / f"{job.id}.manifest.json"),
            )

        runner.rollback(job.id)
        assert store.get_job(job.id).status == "rolled_back"
        assert Dataset(tmp_path / "data" / "library" / "ds").open_table("records").count_rows() == before["records"]

    def test_rollback_restamps_storage_mode(self, tmp_path: Path):
        # Base: embedded-only. Add: uri-mode rows -> mixed. Rollback -> embedded again.
        import_dataset(
            tmp_path / "src",
            tmp_path / "data",
            _spec("mix", namespace="base"),
            importer=ToyImporter(num_records=4, media="embed"),
        )
        result = import_dataset(
            tmp_path / "src2",
            tmp_path / "data",
            _spec("mix", mode="add", namespace="added"),
            importer=ToyImporter(num_records=3, media="uri"),
            job_id="mixjob",
        )
        assert Dataset(result.dataset_path).info.storage_mode == "mixed"

        ImportEngine(tmp_path / "data").rollback(result.dataset_path, "mixjob")
        assert Dataset(result.dataset_path).info.storage_mode == "embedded"
