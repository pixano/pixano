# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from pixano.datasets import Dataset
from pixano.datasets.io import ImportSpec, import_dataset
from pixano.datasets.io.engine import ImportEngine
from pixano.datasets.io.errors import JobStateError
from pixano.datasets.utils.errors import DatasetBusyError
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

    def test_rollback_after_concurrent_edit_refuses_without_changes(self, base_dataset):
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

        versions = {name: dataset.open_table(name).version for name in dataset.info.tables}
        with pytest.raises(JobStateError, match="changed since"):
            ImportEngine(tmp_path / "data").rollback(result.dataset_path, "addjob2")
        after = Dataset(result.dataset_path)
        assert after.open_table("records").count_rows() == before["records"] + 8
        assert after.get_data("records", ids="user_manual_row") is not None  # edit survives
        assert {name: after.open_table(name).version for name in after.info.tables} == versions
        assert result.manifest_path.exists()

    @pytest.mark.parametrize("invalid_anchor", ["legacy", "missing_table", "missing_version", "later_version"])
    def test_prevalidates_every_table_before_restoring(self, base_dataset, invalid_anchor):
        tmp_path, _ = base_dataset
        result = import_dataset(
            tmp_path / "src2",
            tmp_path / "data",
            _spec("ds", "add", "added"),
            importer=ToyImporter(num_records=3),
            job_id="guarded",
        )
        manifest = json.loads(result.manifest_path.read_text())
        dataset = Dataset(result.dataset_path)
        if invalid_anchor == "legacy":
            manifest.pop("rollback_safe")
        elif invalid_anchor == "missing_table":
            dataset._db_connection.drop_table("images")
        elif invalid_anchor == "missing_version":
            manifest["pre_import_versions"]["images"] = 999999
        else:
            # Even a raw Lance write that bypasses Pixano's token is detected.
            dataset.open_table("images").delete("id = 'missing'")
        result.manifest_path.write_text(json.dumps(manifest))
        names = [name for name in dataset.info.tables if name != "images" or invalid_anchor != "missing_table"]
        versions = {name: Dataset(result.dataset_path).open_table(name).version for name in names}
        with pytest.raises(JobStateError):
            ImportEngine(tmp_path / "data").rollback(result.dataset_path, "guarded")
        assert {name: Dataset(result.dataset_path).open_table(name).version for name in names} == versions

    def test_rollback_holds_lock_through_restore(self, base_dataset, monkeypatch):
        from lancedb.table import LanceTable

        from pixano.schemas import Record

        tmp_path, _ = base_dataset
        result = import_dataset(
            tmp_path / "src2",
            tmp_path / "data",
            _spec("ds", "add", "added"),
            importer=ToyImporter(num_records=3),
            job_id="locked",
        )
        writer = Dataset(result.dataset_path)
        original_restore = LanceTable.restore
        attempted = []

        def restore_with_competing_writer(table, *args, **kwargs):
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(writer.add_records, {"records": Record(id="later")}, check_integrity="none")
                with pytest.raises(DatasetBusyError):
                    future.result(timeout=10)
            attempted.append(True)
            return original_restore(table, *args, **kwargs)

        monkeypatch.setattr(LanceTable, "restore", restore_with_competing_writer)
        ImportEngine(tmp_path / "data").rollback(result.dataset_path, "locked")
        assert attempted
        assert Dataset(result.dataset_path).get_data("records", ids="later") is None

    def test_resumed_add_cannot_rollback_edits_during_interruption(self, base_dataset):
        from pixano.schemas import Record

        tmp_path, _ = base_dataset
        cursors = []

        class Interrupted(ToyImporter):
            def iter_batches(self, source, spec, plan, cursor=None):
                for bundle in super().iter_batches(source, spec, plan, cursor):
                    yield bundle
                    raise RuntimeError("interrupted")

        with pytest.raises(RuntimeError, match="interrupted"):
            import_dataset(
                tmp_path / "src2",
                tmp_path / "data",
                _spec("ds", "add", "added"),
                importer=Interrupted(num_records=6, batch_size=2),
                job_id="resumed",
                engine=ImportEngine(tmp_path / "data", flush_rows=1, checkpoint=lambda c, n: cursors.append(c)),
            )
        dataset = Dataset(tmp_path / "data" / "library" / "ds")
        dataset.add_records({"records": Record(id="during_gap")}, check_integrity="none")
        result = import_dataset(
            tmp_path / "src2",
            tmp_path / "data",
            _spec("ds", "add", "added"),
            importer=ToyImporter(num_records=6, batch_size=2),
            job_id="resumed",
            resume_cursor=cursors[-1],
        )
        with pytest.raises(JobStateError, match="resumed"):
            ImportEngine(tmp_path / "data").rollback(result.dataset_path, "resumed")
        assert Dataset(result.dataset_path).get_data("records", ids="during_gap") is not None

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
