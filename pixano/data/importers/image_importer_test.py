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

from pixano.data.importers.image_importer import ImageImporter


class ImageImporterTestCase(unittest.TestCase):
    def setUp(self):
        self.input_dirs = {
            "image": Path("unit_testing/assets/vdp_dataset/media/test/20180306_101220")
        }
        self.importer = ImageImporter(
            name="VDP",
            description="Image dataset using VDP",
            splits=["cam_0"],
        )

    def test_import_dataset(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            # Set import directory
            import_dir = Path(temp_dir) / "vdp"

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
            self.assertEqual("VDP", dataset.info.name)
            self.assertEqual(3, dataset.info.num_elements)

            # Check that db.lance exists
            db_lance_path = import_dir / "db.lance"
            self.assertTrue(db_lance_path.exists())

            # Check db.lance content
            ds = dataset.connect()
            table = ds.open_table("db")
            self.assertEqual(len(table), 3)
            self.assertIn(pa.field("id", pa.string()), table.schema)
            self.assertIn(pa.field("split", pa.string()), table.schema)
