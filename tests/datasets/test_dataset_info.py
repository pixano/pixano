# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import json
import tempfile
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
            "record",
            "entity",
            "entity_dynamic_state",
            "bbox",
            "mask",
            "multi_path",
            "keypoint",
            "tracklet",
            "message",
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
        assert isinstance(dumped["creation_date"], str) and dumped["creation_date"]
        assert dumped["bookmarks"] == []
        assert dumped["record"] == {"base": "Record", "fields": {}}
        assert dumped["entity"] == {"base": "Entity", "fields": {}}
        assert dumped["entity_dynamic_state"] is None
        assert dumped["bbox"] == {"base": "BBox", "fields": {}}
        assert dumped["mask"] is None
        assert dumped["keypoint"] is None
        assert dumped["tracklet"] is None
        assert dumped["message"] is None
        assert dumped["multi_path"] is None
        assert dumped["text_span"] is None
        assert dumped["views"] == {"image": {"base": "Image", "fields": {}}}

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
        payload["views"]["timeseries"] = {"base": "TimeSeries", "fields": {}}
        info_fp.write_text(json.dumps(payload, indent=4), encoding="utf-8")

        info = DatasetInfo.from_json(info_fp)

        assert "image" in info.views
        assert "timeseries" not in info.views

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
