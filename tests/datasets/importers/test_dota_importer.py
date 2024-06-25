# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa

from pixano.core import BBoxType, ImageType
from pixano.data import DOTAImporter


class DOTAImporterTestCase(unittest.TestCase):
    """DOTAImporter test case"""

    def setUp(self):
        """Tests setup"""

        input_dirs = {
            "image": Path("tests/assets/coco_dataset/image"),
            "objects": Path("tests/assets/coco_dataset/objects"),
        }
        self.importer = DOTAImporter(
            name="DOTA",
            description="DOTA dataset from COCO",
            input_dirs=input_dirs,
            splits=["val"],
        )

    def test_import_dataset(self):
        """Test DOTAImporter import_dataset method"""

        with tempfile.TemporaryDirectory() as temp_dir:
            # Set import directory
            import_dir = Path(temp_dir) / "dota"

            # Import dataset
            dataset = self.importer.import_dataset(import_dir, copy=True)

            # Check that db.json exists
            spec_json_path = import_dir / "db.json"
            self.assertTrue(spec_json_path.exists())

            # Check db.json content
            self.assertEqual("DOTA", dataset.info.name)
            self.assertEqual(dataset.info.num_elements, 1)
            self.assertEqual(
                18, len(dataset.info.features_values.objects["category"].values)
            )

            # Check that db.lance exists
            db_lance_path = import_dir / "db.lance"
            self.assertTrue(db_lance_path.exists())

            # Check db.lance content
            ds = dataset.connect()
            table = ds.open_table("db")
            self.assertEqual(len(table), 1)
            self.assertIn(pa.field("id", pa.string()), table.schema)
            self.assertIn(pa.field("split", pa.string()), table.schema)

            # Check that image.lance exists
            db_lance_path = import_dir / "image.lance"
            self.assertTrue(db_lance_path.exists())

            # Check image.lance content
            ds = dataset.connect()
            table = ds.open_table("image")
            self.assertEqual(len(table), 1)
            self.assertIn(pa.field("id", pa.string()), table.schema)
            self.assertIn(pa.field("image", ImageType), table.schema)

            # Check that objects.lance exists
            db_lance_path = import_dir / "objects.lance"
            self.assertTrue(db_lance_path.exists())

            # Check objects.lance content
            ds = dataset.connect()
            table = ds.open_table("objects")
            self.assertEqual(len(table), 323)
            self.assertIn(pa.field("id", pa.string()), table.schema)
            self.assertIn(pa.field("bbox", BBoxType), table.schema)
