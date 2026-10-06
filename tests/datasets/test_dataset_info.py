# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import json
import tempfile
import threading
from pathlib import Path

import pytest

from pixano.datasets.dataset_info import BOOKMARK_TYPES, DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import BBox, Entity, Image, Record


FIXED_CREATION_DATE = "2025-01-01T00:00:00+00:00"


class TestDatasetInfo:
    def test_init(self):
        info = DatasetInfo(creation_date=FIXED_CREATION_DATE)
        assert info == DatasetInfo(
            id="",
            name="",
            description="",
            size="Unknown",
            preview="",
            creation_date=FIXED_CREATION_DATE,
            workspace=WorkspaceType.UNDEFINED,
        )

        info = DatasetInfo(
            id="id",
            name="pascal",
            description="PASCAL VOC 2007",
            size="8GB",
            preview="/preview",
            workspace=WorkspaceType.IMAGE,
        )

        assert set(type(info).model_fields.keys()) == {
            "id",
            "name",
            "description",
            "size",
            "preview",
            "creation_date",
            "bookmarks",
            "workspace",
            "storage_mode",
            "spec_version",
            "record",
            "entity",
            "entity_dynamic_state",
            "bbox",
            "bbox3d",
            "mask",
            "multi_path",
            "keypoint",
            "classification",
            "relation",
            "tracklet",
            "message",
            "timeseries",
            "text_span",
            "views",
            "tables",
        }

        with pytest.raises(ValueError, match="id must not contain spaces"):
            DatasetInfo(
                id="id with space",
                name="pascal",
                description="PASCAL VOC 2007",
                size="8GB",
                preview="/preview",
                workspace=WorkspaceType.IMAGE,
            )

    def test_to_json(self):
        info = DatasetInfo(
            id="id",
            name="pascal",
            description="PASCAL VOC 2007",
            size="8GB",
            preview="/preview",
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=Entity,
            bbox=BBox,
            views={"image": Image},
        )
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        info.to_json(temp_file)
        dumped = json.loads(temp_file.read_text())
        assert dumped["id"] == "id"
        assert dumped["name"] == "pascal"
        assert dumped["description"] == "PASCAL VOC 2007"
        assert dumped["size"] == "8GB"
        assert dumped["preview"] == "/preview"
        assert dumped["workspace"] == "image"
        assert dumped["storage_mode"] == "filesystem"
        assert dumped["spec_version"] == 2
        assert isinstance(dumped["creation_date"], str) and dumped["creation_date"]
        assert dumped["bookmarks"] == []
        assert dumped["record"] == {"base": "Record", "fields": {}}
        assert dumped["entity"] == {"base": "Entity", "fields": {}}
        assert dumped["entity_dynamic_state"] is None
        assert dumped["bbox"] == {"base": "BBox", "fields": {}}
        assert dumped["bbox3d"] is None
        assert dumped["mask"] is None
        assert dumped["keypoint"] is None
        assert dumped["classification"] is None
        assert dumped["relation"] is None
        assert dumped["tracklet"] is None
        assert dumped["message"] is None
        assert dumped["multi_path"] is None
        assert dumped["text_span"] is None
        assert dumped["timeseries"] is None
        assert dumped["views"] == {"image": {"base": "Image", "fields": {}}}

    def test_to_json_leaves_no_temporary_file(self, tmp_path):
        info = DatasetInfo(id="id", name="pascal", record=Record, views={"image": Image})
        info_fp = tmp_path / "info.json"

        info.to_json(info_fp)

        assert [p.name for p in tmp_path.iterdir()] == ["info.json"]

    def test_to_json_overwrites_a_longer_document_without_leftovers(self, tmp_path):
        # A single writer shrinking the document was already safe (the previous
        # `write_text` truncated too); this pins that the rename-based write
        # keeps it so. The failure mode that actually bit is concurrency —
        # covered by the test below.
        info_fp = tmp_path / "info.json"
        long_info = DatasetInfo(
            id="id",
            name="pascal",
            description="a description long enough to make this dump the bigger one",
            record=Record,
            entity=Entity,
            bbox=BBox,
            views={"image": Image, "second_image": Image, "third_image": Image},
        )
        long_info.to_json(info_fp)
        long_size = info_fp.stat().st_size

        short_info = DatasetInfo(id="id", name="pascal", record=Record, views={"image": Image})
        short_info.to_json(info_fp)

        assert info_fp.stat().st_size < long_size
        # Parses, and carries only the second dump.
        dumped = json.loads(info_fp.read_text())
        assert dumped["views"] == {"image": {"base": "Image", "fields": {}}}
        assert dumped["bbox"] is None

    def test_to_json_is_atomic_under_concurrent_writers(self, tmp_path):
        # `BaseService.resolve_table` persists a newly created slot from inside a
        # read, so listing several absent resources at once makes several
        # threads write this one file. Interleaved in-place writes used to leave
        # a torn document; every observation must now parse.
        info_fp = tmp_path / "info.json"
        writers = [
            DatasetInfo(
                id="id",
                name="pascal",
                description="d" * (200 * index),
                record=Record,
                views={f"image_{i}": Image for i in range(index + 1)},
            )
            for index in range(8)
        ]
        # Seed the file so readers always have something to observe.
        writers[0].to_json(info_fp)

        failures: list[Exception] = []

        def write_repeatedly(info: DatasetInfo) -> None:
            try:
                for _ in range(20):
                    info.to_json(info_fp)
            except Exception as exc:  # pragma: no cover - surfaced via `failures`
                failures.append(exc)

        def read_repeatedly() -> None:
            try:
                for _ in range(200):
                    json.loads(info_fp.read_text())
            except Exception as exc:
                failures.append(exc)

        threads = [threading.Thread(target=write_repeatedly, args=(info,)) for info in writers]
        threads += [threading.Thread(target=read_repeatedly) for _ in range(4)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()

        assert failures == []
        # The survivor is one of the writers' documents, whole.
        assert json.loads(info_fp.read_text())["id"] == "id"
        assert [p.name for p in tmp_path.iterdir()] == ["info.json"]

    def test_from_json(self):
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        temp_file.write_text(
            """{
    "id": "id",
    "name": "pascal",
    "description": "PASCAL VOC 2007",
    "size": "8GB",
    "preview": "/preview",
    "creation_date": "2025-06-01T12:00:00+00:00",
    "workspace": "image",
    "record": {
        "base": "Record",
        "fields": {}
    },
    "entity": {
        "base": "Entity",
        "fields": {}
    },
    "entity_dynamic_state": null,
    "bbox": {
        "base": "BBox",
        "fields": {}
    },
    "mask": null,
    "keypoint": null,
    "tracklet": null,
    "message": null,
    "text_span": null,
    "timeseries": null,
    "views": {
        "image": {
            "base": "Image",
            "fields": {}
        }
    }
}"""
        )
        info = DatasetInfo.from_json(temp_file)
        assert info == DatasetInfo(
            id="id",
            name="pascal",
            description="PASCAL VOC 2007",
            size="8GB",
            preview="/preview",
            creation_date="2025-06-01T12:00:00+00:00",
            workspace=WorkspaceType.IMAGE,
            spec_version=1,  # absent in the JSON above ⇒ pre-spec_version layout
            record=Record,
            entity=Entity,
            bbox=BBox,
            views={"image": Image},
        )

    def test_load_directory(self):
        temp_dir = Path(tempfile.TemporaryDirectory().name)
        for i in range(3):
            info_dir = temp_dir / f"info_{i}"
            info_dir.mkdir(parents=True, exist_ok=False)
            info = DatasetInfo(
                id=f"id_{i}",
                name=f"pascal_{i}",
                description=f"PASCAL VOC 2007_{i}",
                size="8GB",
                preview="/preview",
                creation_date=FIXED_CREATION_DATE,
                workspace=WorkspaceType.IMAGE,
                record=Record,
                entity=Entity,
                bbox=BBox,
                views={"image": Image},
            )
            info.to_json(info_dir / "info.json")

        # Without return_path
        library = DatasetInfo.load_directory(temp_dir)
        assert len(library) == 3
        for i, info in enumerate(library):
            assert info == DatasetInfo(
                id=f"id_{i}",
                name=f"pascal_{i}",
                description=f"PASCAL VOC 2007_{i}",
                size="8GB",
                preview=info.preview,
                creation_date=FIXED_CREATION_DATE,
                workspace=WorkspaceType.IMAGE,
                record=Record,
                entity=Entity,
                bbox=BBox,
                views={"image": Image},
            )

        # With return_path
        library_and_paths = DatasetInfo.load_directory(temp_dir, return_path=True)
        assert len(library_and_paths) == 3
        for i, (info, path) in enumerate(library_and_paths):
            assert info == DatasetInfo(
                id=f"id_{i}",
                name=f"pascal_{i}",
                description=f"PASCAL VOC 2007_{i}",
                size="8GB",
                preview=info.preview,
                creation_date=FIXED_CREATION_DATE,
                workspace=WorkspaceType.IMAGE,
                record=Record,
                entity=Entity,
                bbox=BBox,
                views={"image": Image},
            )
            assert path == temp_dir / f"info_{i}"

        temp_dir = Path(tempfile.TemporaryDirectory().name)
        with pytest.raises(FileNotFoundError):
            DatasetInfo.load_directory(temp_dir)

    def test_load_directory_skips_unloadable(self):
        temp_dir = Path(tempfile.TemporaryDirectory().name)

        valid_dir = temp_dir / "valid"
        valid_dir.mkdir(parents=True, exist_ok=False)
        DatasetInfo(
            id="valid_id",
            name="valid",
            description="valid dataset",
            size="8GB",
            preview="/preview",
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=Entity,
            bbox=BBox,
            views={"image": Image},
        ).to_json(valid_dir / "info.json")

        broken_dir = temp_dir / "broken"
        broken_dir.mkdir(parents=True, exist_ok=False)
        broken_payload = json.loads((valid_dir / "info.json").read_text(encoding="utf-8"))
        broken_payload["id"] = "broken_id"
        broken_payload["name"] = "broken"
        broken_payload["record"] = {"base": "TimeSeries", "fields": {}}
        (broken_dir / "info.json").write_text(json.dumps(broken_payload, indent=4), encoding="utf-8")

        library = DatasetInfo.load_directory(temp_dir)

        assert len(library) == 1
        assert library[0].id == "valid_id"

    def test_from_json_drops_unsupported_view(self):
        temp_dir = Path(tempfile.TemporaryDirectory().name)
        temp_dir.mkdir(parents=True, exist_ok=False)
        info_fp = temp_dir / "info.json"

        DatasetInfo(
            id="ds_id",
            name="ds",
            description="dataset with an unsupported view",
            size="8GB",
            preview="/preview",
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=Entity,
            bbox=BBox,
            views={"image": Image},
        ).to_json(info_fp)

        payload = json.loads(info_fp.read_text(encoding="utf-8"))
        payload["views"]["hologram"] = {"base": "HologramView", "fields": {}}
        info_fp.write_text(json.dumps(payload, indent=4), encoding="utf-8")

        info = DatasetInfo.from_json(info_fp)

        assert "image" in info.views
        assert "hologram" not in info.views

    def test_load_id(self):
        temp_dir = Path(tempfile.TemporaryDirectory().name)
        info_dir = temp_dir / "info"
        info_dir.mkdir(parents=True, exist_ok=False)
        info = DatasetInfo(
            id="id",
            name="pascal",
            description="PASCAL VOC 2007",
            size="8GB",
            preview="/preview",
            creation_date=FIXED_CREATION_DATE,
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=Entity,
            bbox=BBox,
            views={"image": Image},
        )
        info.to_json(info_dir / "info.json")

        # Without return_path
        loaded_info = DatasetInfo.load_id("id", temp_dir)
        assert loaded_info == DatasetInfo(
            id="id",
            name="pascal",
            description="PASCAL VOC 2007",
            size="8GB",
            preview=loaded_info.preview,
            creation_date=FIXED_CREATION_DATE,
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=Entity,
            bbox=BBox,
            views={"image": Image},
        )

        # With return_path
        loaded_info, path = DatasetInfo.load_id("id", temp_dir, return_path=True)
        assert loaded_info == DatasetInfo(
            id="id",
            name="pascal",
            description="PASCAL VOC 2007",
            size="8GB",
            preview=loaded_info.preview,
            creation_date=FIXED_CREATION_DATE,
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=Entity,
            bbox=BBox,
            views={"image": Image},
        )
        assert path == temp_dir / "info"

        with pytest.raises(FileNotFoundError):
            DatasetInfo.load_id("unknown", temp_dir)

    def test_rejects_tables_mapping(self):
        with pytest.raises(ValueError, match="no longer accepts a 'tables' mapping"):
            DatasetInfo(tables={"records": Record})

    def test_creation_date_auto_populated(self):
        info = DatasetInfo(id="test", name="test")
        assert info.creation_date != ""
        from datetime import datetime

        datetime.fromisoformat(info.creation_date)

    def test_creation_date_preserved_when_set(self):
        info = DatasetInfo(id="test", name="test", creation_date="2025-01-15T10:00:00+00:00")
        assert info.creation_date == "2025-01-15T10:00:00+00:00"

    def test_bookmarks_round_trip(self):
        info = DatasetInfo(
            id="id",
            name="pascal",
            bookmarks=["TODO", "FAVORITE"],
        )
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        info.to_json(temp_file)
        loaded = DatasetInfo.from_json(temp_file)
        assert loaded.bookmarks == ["TODO", "FAVORITE"]

    def test_bookmarks_constant(self):
        assert BOOKMARK_TYPES == ("TODO", "NEW", "FAVORITE")

    def test_creation_date_empty_and_stable_for_legacy_files(self):
        """Pre-creation_date datasets load "" — never a fabricated load-time date."""
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        temp_file.write_text(
            """{
    "id": "id",
    "name": "old",
    "workspace": "image",
    "record": {"base": "Record", "fields": {}},
    "views": {}
}"""
        )
        assert DatasetInfo.from_json(temp_file).creation_date == ""
        assert DatasetInfo.from_json(temp_file).creation_date == ""  # stable across loads


class TestSpecVersion:
    def test_defaults_to_2_for_new_infos(self):
        assert DatasetInfo().spec_version == 2

    def test_absent_in_json_means_version_1(self):
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        temp_file.write_text(
            """{
    "id": "id",
    "name": "old",
    "workspace": "image",
    "record": {
        "base": "Record",
        "fields": {}
    },
    "views": {}
}"""
        )
        assert DatasetInfo.from_json(temp_file).spec_version == 1
