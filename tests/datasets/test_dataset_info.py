# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
import unittest
from pathlib import Path

from pixano.datasets import DatasetInfo, DatasetTable


class DatasetInfoTestCase(unittest.TestCase):
    """DatasetInfo test case"""

    def setUp(self):
        """Tests setup"""

        self.info = DatasetInfo(
            id="datasetid001",
            name="My dataset",
            description="Dataset from a great AI project",
            estimated_size="N/A",
            num_elements=0,
            splits=["train", "val"],
            tables={
                "main": [
                    DatasetTable(
                        name="db",
                        fields={
                            "id": "str",
                            "views": "[str]",
                            "split": "str",
                        },
                    )
                ],
                "media": [
                    DatasetTable(
                        name="image",
                        fields={
                            "id": "str",
                            "image": "image",
                        },
                    )
                ],
                "objects": [
                    DatasetTable(
                        name="objects",
                        fields={
                            "id": "str",
                            "item_id": "str",
                            "view_id": "str",
                            "bbox": "bbox",
                            "category": "str",
                        },
                        source="Ground Truth",
                    )
                ],
            },
        )

    def test_save(self):
        """Test DatasetInfo save method"""

        with tempfile.TemporaryDirectory() as temp_dir:
            self.info.save(Path(temp_dir))
            saved_info = DatasetInfo.from_json(Path(temp_dir) / "db.json")

            self.assertIsInstance(saved_info, DatasetInfo)
            self.assertEqual(self.info, saved_info)

    def test_dict(self):
        """Test DatasetInfo export to dict and import from dict"""

        info_to_dict = self.info.model_dump()

        self.assertIsInstance(info_to_dict, dict)

        info_from_dict = DatasetInfo(**info_to_dict)

        self.assertIsInstance(info_from_dict, DatasetInfo)
        self.assertEqual(self.info, info_from_dict)

    def test_load_directory(self):
        """Test DatasetInfo load_directory method"""

        with tempfile.TemporaryDirectory() as temp_dir:
            dir1 = Path(temp_dir) / "dir1"
            dir2 = Path(temp_dir) / "dir2"
            dir3 = Path(temp_dir) / "dir3"

            dir1.mkdir()
            dir2.mkdir()
            dir3.mkdir()

            self.info.save(dir1)
            self.info.save(dir2)
            self.info.save(dir3)

            saved_infos = DatasetInfo.load_directory(Path(temp_dir))

            self.assertIsInstance(saved_infos, list)
            self.assertEqual(len(saved_infos), 3)

            for info in saved_infos:
                self.assertIsInstance(info, DatasetInfo)
                self.assertEqual(info, self.info)
