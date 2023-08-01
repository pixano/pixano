from tempfile import tempdir
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from pixano.data.image_importer import ImageImporter


class ImageImporterTestCase(unittest.TestCase):
    def setUp(self):
        self.input_dirs = {"image": Path("test_data/images")}
        self.importer = ImageImporter(
            name="Demo - Agriculture",
            description="LIST Days - Demo - Agriculture",
            splits=["demo", "train"],
        )
    
    def test_import_existing_file(self):
            with tempfile.TemporaryDirectory() as library_dir:
                import_dir = Path(library_dir) / "demo_agriculture"
                ds = self.importer.import_dataset(self.input_dirs, import_dir, portable=False)

                # Verify that spec.json exists in import_dir
                spec_json_path = import_dir / "spec.json"
                self.assertTrue(spec_json_path.exists(), "spec.json file does not exist.")

                # Verify that db.lance exists and is a valid JSON file
                db_lance_path = import_dir / "db.lance"
                self.assertTrue(db_lance_path.exists(), "db.lance file does not exist.")
    
    def test_import_correct_data(self):
        with tempfile.TemporaryDirectory() as library_dir:
            import_dir = Path(library_dir) / "demo_agriculture"
            ds = self.importer.import_dataset(self.input_dirs, import_dir, portable=False)

            for r in ds.to_batches():
                db: pd.DataFrame = r.to_pandas()

                # Assertions to check for data correctness
                self.assertIsInstance(db, pd.DataFrame, "db is not a pandas DataFrame.")
                self.assertFalse(db.empty, "db DataFrame is empty.")
                self.assertGreaterEqual(len(db), 4, "Dataframe should have at least 10 rows.")
                self.assertIn("split", db.columns, "Column 'split' not found in DataFrame.")
