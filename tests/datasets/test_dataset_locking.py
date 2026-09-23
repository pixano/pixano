# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path

import pytest

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.io import ImportEngine, ImportSpec, import_dataset
from pixano.datasets.locking import dataset_mutation_lock, mark_dataset_mutated
from pixano.datasets.utils.errors import DatasetBusyError, DatasetReplacedError
from pixano.schemas import Record
from tests.datasets.io._toy_importer import ToyImporter


def _hold_process_lock(path, ready, release):
    with dataset_mutation_lock(Path(path)):
        ready.set()
        release.wait(30)


@contextmanager
def _other_process_lock(path):
    context = multiprocessing.get_context("spawn")
    ready, release = context.Event(), context.Event()
    process = context.Process(target=_hold_process_lock, args=(str(path), ready, release))
    process.start()
    try:
        assert ready.wait(15), "child did not acquire its dataset lock"
        yield process
    finally:
        if process.is_alive():
            release.set()
        process.join(15)
        if process.is_alive():
            process.terminate()
            process.join(5)


def test_mutations_fail_fast_across_processes_and_release_after_exit(tmp_path):
    dataset = Dataset.create(tmp_path / "ds", DatasetInfo(record=Record))
    with _other_process_lock(dataset.path) as owner:
        with pytest.raises(DatasetBusyError, match="retry"):
            dataset.add_records({"records": Record(id="blocked")})
        owner.terminate()
        owner.join(5)
    dataset.add_records({"records": Record(id="allowed")})
    assert dataset.get_records(ids="allowed") is not None
    assert dataset.get_records(ids="blocked") is None


def test_nested_writes_are_reentrant_and_refresh_stale_handles(tmp_path):
    dataset = Dataset.create(tmp_path / "ds", DatasetInfo(record=Record))
    cached = Dataset(dataset.path)
    cached.open_table("records")  # cache an empty snapshot
    with dataset_mutation_lock(dataset.path):
        with dataset.write_lock():
            dataset.add_records({"records": Record(id="existing")})
    with cached.write_lock():
        assert cached.get_records(ids="existing") is not None
        cached.delete_records(["existing"])
    assert cached.get_records() == []


def test_cached_writer_rejects_replaced_directory_even_with_same_dataset_id(tmp_path):
    dataset = Dataset.create(tmp_path / "ds", DatasetInfo(id="same-id", record=Record))
    dataset.path.rename(tmp_path / "old")
    replacement = Dataset.create(dataset.path, DatasetInfo(id="same-id", record=Record))
    with pytest.raises(DatasetReplacedError):
        dataset.add_records({"records": Record(id="stale")})
    assert replacement.get_records() == []


def test_writer_detects_promotion_during_dataset_construction(tmp_path, monkeypatch):
    original = Dataset.create(tmp_path / "ds", DatasetInfo(id="same-id", record=Record))
    staged = Dataset.create(tmp_path / "staged", DatasetInfo(id="same-id", record=Record))
    connect = Dataset._connect
    replaced = False

    def promote_during_connect(dataset):
        nonlocal replaced
        if not replaced and dataset.path == original.path:
            original.path.rename(tmp_path / "old")
            staged.path.rename(original.path)
            replaced = True
        return connect(dataset)

    monkeypatch.setattr(Dataset, "_connect", promote_during_connect)
    stale = Dataset(original.path)
    with pytest.raises(DatasetReplacedError):
        stale.add_records({"records": Record(id="stale")})
    assert Dataset(original.path).get_records() == []


def test_add_holds_lock_between_flushes(tmp_path):
    spec = ImportSpec.model_validate({"dataset": {"name": "ds", "workspace": "image"}})
    first = import_dataset(tmp_path / "source", tmp_path / "data", spec, importer=ToyImporter(num_records=2))
    writer = Dataset(first.dataset_path)
    attempts = []

    def checkpoint(cursor, counts):
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(writer.add_records, {"records": Record(id="interleaved")}, check_integrity="none")
            with pytest.raises(DatasetBusyError):
                result.result(timeout=10)
        attempts.append(cursor)

    import_dataset(
        tmp_path / "source",
        tmp_path / "data",
        spec.model_copy(update={"mode": "add"}),
        importer=ToyImporter(num_records=8, batch_size=2),
        engine=ImportEngine(tmp_path / "data", flush_rows=1, checkpoint=checkpoint),
    )
    assert len(attempts) > 1
    assert Dataset(first.dataset_path).get_records(ids="interleaved") is None


def test_overwrite_promotion_uses_live_dataset_lock(tmp_path):
    info = DatasetInfo(record=Record)
    live = Dataset.create(tmp_path / "live", info)
    staged = Dataset.create(tmp_path / "staged", DatasetInfo(record=Record))
    with _other_process_lock(live.path):
        with pytest.raises(DatasetBusyError):
            ImportEngine(tmp_path)._promote(staged.path, live.path, "overwrite")
    assert live.path.is_dir() and staged.path.is_dir()


def test_create_cannot_claim_a_target_reserved_for_promotion(tmp_path):
    target = tmp_path / "between-trash-and-promotion"
    with _other_process_lock(target):
        with pytest.raises(DatasetBusyError):
            Dataset.create(target, DatasetInfo(record=Record))
    assert not target.exists()


def test_cached_constraint_updates_preserve_other_writers(tmp_path):
    dataset = Dataset.create(tmp_path / "ds", DatasetInfo(record=Record))
    other = Dataset(dataset.path)
    dataset.add_constraint("records", "status", ["new"])
    other.add_constraint("records", "split", ["train"])
    dataset.add_constraint("records", "status", ["new", "validated"])
    constraints = Dataset(dataset.path).features_values.records["records"]
    assert {value.name: value.values for value in constraints} == {
        "status": ["new", "validated"],
        "split": ["train"],
    }


def test_remote_dataset_does_not_use_local_stat_or_lock_paths(mocker):
    from s3path import S3Path

    from pixano.datasets.dataset_features_values import DatasetFeaturesValues
    from pixano.datasets.io.errors import UnsupportedStorageError

    path = S3Path("/bucket/dataset")
    mocker.patch.object(S3Path, "stat", side_effect=AssertionError("local inode assumptions"))
    mocker.patch.object(S3Path, "resolve", side_effect=AssertionError("local path conversion"))
    mocker.patch.object(S3Path, "is_file", return_value=False)
    mocker.patch.object(DatasetInfo, "from_json", return_value=DatasetInfo(id="remote", record=Record))
    mocker.patch.object(DatasetFeaturesValues, "from_json", return_value=DatasetFeaturesValues())
    mocker.patch.object(Dataset, "_connect")
    mocker.patch.object(Dataset, "_load_record_embedding_space")
    dataset = Dataset(path)
    with dataset_mutation_lock(path), dataset.write_lock():
        mark_dataset_mutated(path)
    assert dataset.path is path
    with pytest.raises(UnsupportedStorageError):
        ImportEngine(path)
