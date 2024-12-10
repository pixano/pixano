# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import tempfile
from pathlib import Path

import pytest

from pixano.datasets.dataset_info import DatasetInfo


class TestDatasetInfo:
    def test_init(self):
        info = DatasetInfo()
        assert info == DatasetInfo(id="", name="", description="", size="Unknown", preview="")

        info = DatasetInfo(id="id", name="pascal", description="PASCAL VOC 2007", size="8GB", preview="/preview")

        assert set(info.model_fields.keys()) == {"id", "name", "description", "size", "preview"}

        with pytest.raises(ValueError, match="id must not contain spaces"):
            DatasetInfo(
                id="id with space", name="pascal", description="PASCAL VOC 2007", size="8GB", preview="/preview"
            )

    def test_to_json(self):
        info = DatasetInfo(id="id", name="pascal", description="PASCAL VOC 2007", size="8GB", preview="/preview")
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        info.to_json(temp_file)
        assert (
            Path(temp_file).read_text()
            == """{
    "id": "id",
    "name": "pascal",
    "description": "PASCAL VOC 2007",
    "size": "8GB",
    "preview": "/preview"
}"""
        )

    def test_from_json(self):
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        temp_file.write_text(
            """{
    "id": "id",
    "name": "pascal",
    "description": "PASCAL VOC 2007",
    "size": "8GB",
    "preview": "/preview"
}"""
        )
        info = DatasetInfo.from_json(temp_file)
        assert info == DatasetInfo(
            id="id", name="pascal", description="PASCAL VOC 2007", size="8GB", preview="/preview"
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
                preview=info.preview,  # TODO: remove hard coded value
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
                preview=info.preview,  # TODO: remove hard coded value
            )
            assert path == temp_dir / f"info_{i}"

        temp_dir = Path(tempfile.TemporaryDirectory().name)
        with pytest.raises(FileNotFoundError):
            DatasetInfo.load_directory(temp_dir)

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
        )
        info.to_json(info_dir / "info.json")

        # Without return_path
        loaded_info = DatasetInfo.load_id("id", temp_dir)
        assert loaded_info == DatasetInfo(
            id="id",
            name="pascal",
            description="PASCAL VOC 2007",
            size="8GB",
            preview=loaded_info.preview,  # TODO: remove hard coded value
        )

        # With return_path
        loaded_info, path = DatasetInfo.load_id("id", temp_dir, return_path=True)
        assert loaded_info == DatasetInfo(
            id="id",
            name="pascal",
            description="PASCAL VOC 2007",
            size="8GB",
            preview=loaded_info.preview,  # TODO: remove hard coded value
        )
        assert path == temp_dir / "info"

        with pytest.raises(FileNotFoundError):
            DatasetInfo.load_id("unknown", temp_dir)
