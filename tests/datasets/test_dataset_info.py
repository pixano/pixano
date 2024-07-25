# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import tempfile
from pathlib import Path

from pixano.datasets.dataset_info import DatasetInfo


class TestDatasetInfo:
    def test_init(self):
        info = DatasetInfo()
        assert info == DatasetInfo(id="", name="", description="", size="Unknown", num_elements=0, preview="")

        info = DatasetInfo(
            id="id", name="pascal", description="PASCAL VOC 2007", size="8GB", num_elements=100, preview="/preview"
        )

        assert set(info.model_fields.keys()) == {"id", "name", "description", "size", "num_elements", "preview"}

    def test_to_json(self):
        info = DatasetInfo(
            id="id", name="pascal", description="PASCAL VOC 2007", size="8GB", num_elements=100, preview="/preview"
        )
        temp_file = Path(tempfile.NamedTemporaryFile(suffix=".json").name)
        info.to_json(temp_file)
        assert (
            Path(temp_file).read_text()
            == """{
    "id": "id",
    "name": "pascal",
    "description": "PASCAL VOC 2007",
    "size": "8GB",
    "num_elements": 100,
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
    "num_elements": 100,
    "preview": "/preview"
}"""
        )
        info = DatasetInfo.from_json(temp_file)
        assert info == DatasetInfo(
            id="id", name="pascal", description="PASCAL VOC 2007", size="8GB", num_elements=100, preview="/preview"
        )
