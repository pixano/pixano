# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The writers that patch `info.json` raw, rather than re-serializing what this build read of it."""

import json
import stat
import tempfile
from pathlib import Path
from typing import Any

from pixano.datasets import Dataset, DatasetInfo
from pixano.schemas import BBox, Entity, Image, Record


# A view whose schema comes from a later build: `DatasetInfo.from_json` drops it, the file keeps it.
UNREADABLE_VIEW_NAME = "lidar"
UNREADABLE_VIEW = {"base": "FutureView", "fields": {}}
# Readable by the owner and everyone else: what a dataset copied in by hand usually carries.
SHARED_PERMISSIONS = 0o644


def _dataset() -> Dataset:
    target = Path(tempfile.mkdtemp()) / "ds"
    dataset = Dataset.create(
        target, DatasetInfo(name="ds", record=Record, entity=Entity, bbox=BBox, views={"image": Image})
    )
    dataset.add_records({"records": [Record(id="r1")]})
    dataset.add_data("entities", [Entity(id="e1", record_id="r1")], raise_or_warn="none")
    return dataset


def _info_json(dataset: Dataset) -> dict[str, Any]:
    return json.loads(dataset._info_file.read_text(encoding="utf-8"))


def _write_info_json(dataset: Dataset, info_json: dict[str, Any]) -> None:
    dataset._info_file.write_text(json.dumps(info_json, indent=4), encoding="utf-8")


def _outdated(dataset: Dataset) -> None:
    """Take the dataset back one spec version, so that the next opener migrates it."""
    info_json = _info_json(dataset)
    info_json["spec_version"] = Dataset._CURRENT_SPEC_VERSION - 1
    _write_info_json(dataset, info_json)


def _leftover_temporary_files(dataset: Dataset) -> list[Path]:
    return list(dataset.path.glob(f"{Dataset._INFO_FILE}.*.tmp"))


class TestStorageMigrationPatch:
    def test_keeps_views_this_build_cannot_deserialize(self) -> None:
        dataset = _dataset()
        info_json = _info_json(dataset)
        info_json["views"][UNREADABLE_VIEW_NAME] = UNREADABLE_VIEW
        _write_info_json(dataset, info_json)
        _outdated(dataset)

        migrated = Dataset(dataset.path)

        assert UNREADABLE_VIEW_NAME not in migrated.info.views  # dropped on read, the premise
        assert migrated.info.spec_version == Dataset._CURRENT_SPEC_VERSION
        info_json = _info_json(migrated)
        assert info_json["spec_version"] == Dataset._CURRENT_SPEC_VERSION
        assert info_json["views"][UNREADABLE_VIEW_NAME] == UNREADABLE_VIEW
        assert _leftover_temporary_files(migrated) == []

    def test_keeps_the_permissions_of_info_json(self) -> None:
        """A temporary file is created readable by its owner alone; the rename must not carry that over."""
        dataset = _dataset()
        _outdated(dataset)
        dataset._info_file.chmod(SHARED_PERMISSIONS)

        migrated = Dataset(dataset.path)

        assert migrated.info.spec_version == Dataset._CURRENT_SPEC_VERSION
        assert stat.S_IMODE(migrated._info_file.stat().st_mode) == SHARED_PERMISSIONS

    def test_a_remote_dataset_gets_its_info_json_written_whole(self, mocker) -> None:
        """An object store has no directory for a temporary file nor permissions to keep: the
        document is written whole, which an object store does atomically."""
        from s3path import S3Path

        from pixano.datasets.dataset_features_values import DatasetFeaturesValues

        outdated = Dataset._CURRENT_SPEC_VERSION - 1
        stored = {"id": "remote", "spec_version": outdated, "views": {UNREADABLE_VIEW_NAME: UNREADABLE_VIEW}}
        written: list[str] = []
        mocker.patch.object(S3Path, "stat", side_effect=AssertionError("local inode assumptions"))
        mocker.patch.object(S3Path, "is_file", return_value=False)
        mocker.patch.object(S3Path, "read_text", return_value=json.dumps(stored))
        mocker.patch.object(S3Path, "write_text", side_effect=lambda content, encoding: written.append(content))
        mocker.patch.object(
            DatasetInfo, "from_json", return_value=DatasetInfo(id="remote", record=Record, spec_version=outdated)
        )
        mocker.patch.object(DatasetFeaturesValues, "from_json", return_value=DatasetFeaturesValues())
        mocker.patch.object(Dataset, "_connect")
        mocker.patch.object(Dataset, "_load_record_embedding_space")

        dataset = Dataset(S3Path("/bucket/dataset"))

        assert dataset.info.spec_version == Dataset._CURRENT_SPEC_VERSION
        assert [json.loads(content) for content in written] == [
            {**stored, "spec_version": Dataset._CURRENT_SPEC_VERSION}
        ]
