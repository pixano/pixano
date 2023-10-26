# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

import tempfile
import unittest
from pathlib import Path

import pyarrow as pa

from pixano.core import BBoxType, ImageType
from pixano.data.importers.dota_importer import DOTAImporter


class DOTAImporterTestCase(unittest.TestCase):
    def setUp(self):
        self.input_dirs = {
            "image": Path("unit_testing/assets/coco_dataset/image"),
            "objects": Path("unit_testing/assets/coco_dataset/objects"),
        }
        self.importer = DOTAImporter(
            name="DOTA",
            description="DOTA dataset from COCO",
            splits=["val"],
        )

    def test_import_dataset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set import directory
            import_dir = Path(temp_dir) / "dota"

            # Import dataset
            dataset = self.importer.import_dataset(
                self.input_dirs,
                import_dir,
                portable=False,
            )

            # Check that db.json exists
            spec_json_path = import_dir / "db.json"
            self.assertTrue(spec_json_path.exists())

            # Check db.json content
            self.assertEqual("DOTA", dataset.info.name)
            self.assertEqual(dataset.info.num_elements, 1)

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
