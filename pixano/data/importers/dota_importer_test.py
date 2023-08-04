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

import pandas as pd

from pixano.data.importers.dota_importer import DOTAImporter


class DOTAImporterTestCase(unittest.TestCase):
    def setUp(self):
        self.input_dirs = {
            "objects": Path("unit_testing/assets/dota_dataset/objects"),
            "image": Path("unit_testing/assets/dota_dataset/image"),
        }

        self.importer = DOTAImporter(
            name="Dota test", description="LIST Dota", splits=["train"]
        )

    def test_import_existing_file(self):
        with tempfile.TemporaryDirectory() as library_dir:
            import_dir = Path(library_dir) / "test_dota"
            ds = self.importer.import_dataset(self.input_dirs, import_dir)

            # Verify that spec.json exists in import_dir
            spec_json_path = import_dir / "spec.json"
            self.assertTrue(spec_json_path.exists(), "spec.json file does not exist.")

            # Verify that db.lance exists
            db_lance_path = import_dir / "db.lance"
            self.assertTrue(db_lance_path.exists(), "db.lance file does not exist.")

    def test_import_data(self):
        with tempfile.TemporaryDirectory() as library_dir:
            import_dir = Path(library_dir) / "dota"
            ds = self.importer.import_dataset(self.input_dirs, import_dir)

            for r in ds.to_batches():
                db: pd.DataFrame = r.to_pandas()

                # Assertions to check for data correctness
                self.assertIsInstance(db, pd.DataFrame, "db is not a pandas DataFrame.")
                self.assertFalse(db.empty, "db DataFrame is empty.")
                self.assertGreaterEqual(
                    len(db), 1, "Dataframe should have at least 10 rows."
                )
                self.assertIn(
                    "objects", db.columns, "Column 'split' not found in DataFrame."
                )
                self.assertIn(
                    "image", db.columns, "Column 'split' not found in DataFrame."
                )
