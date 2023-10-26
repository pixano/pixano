# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
#
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

import json
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from pixano.api import Settings
from pixano.apps.main import create_app
from pixano.data import COCOImporter


class AppTestCase(unittest.TestCase):
    def setUp(self):
        # Create temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        library_dir = Path(self.temp_dir.name)

        # Create a COCO dataset
        import_dir = library_dir / "coco"
        input_dirs = {
            "image": Path("unit_testing/assets/coco_dataset/image"),
            "objects": Path("unit_testing/assets/coco_dataset"),
        }
        importer = COCOImporter(
            name="coco",
            description="COCO dataset",
            splits=["val"],
        )
        dataset = importer.import_dataset(input_dirs, import_dir, portable=False)

        # Set dataset ID
        dataset.info.id = "coco_dataset"
        dataset.save_info()

        # Create dataset stats
        stats = [
            {
                "name": "Some numerical statistics",
                "type": "numerical",
                "histogram": [
                    {"bin_start": 0.0, "bin_end": 1.0, "counts": 2, "split": "train"},
                    {"bin_start": 1.0, "bin_end": 2.0, "counts": 4, "split": "train"},
                    {"bin_start": 2.0, "bin_end": 3.0, "counts": 6, "split": "train"},
                    {"bin_start": 3.0, "bin_end": 4.0, "counts": 8, "split": "train"},
                ],
                "range": [0.0, 10.0],
            },
            {
                "name": "Some categorical statistics",
                "type": "categorical",
                "histogram": [
                    {"Some categorical statistics": "a", "counts": 2, "split": "train"},
                    {"Some categorical statistics": "b", "counts": 4, "split": "train"},
                    {"Some categorical statistics": "c", "counts": 6, "split": "train"},
                    {"Some categorical statistics": "d", "counts": 8, "split": "train"},
                ],
            },
        ]
        with open(import_dir / "stats.json", "w", encoding="utf-8") as f:
            json.dump(stats, f)

        # Launch app
        self.settings = Settings(data_dir=library_dir)
        self.client = TestClient(create_app(self.settings))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_get_dataset_list(self):
        response = self.client.get("/datasets")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertGreaterEqual(len(output), 1)

        for ds in output:
            self.assertIn("id", ds)
            self.assertIn("name", ds)
            self.assertIn("description", ds)
            self.assertIn("preview", ds)

    def test_get_dataset(self):
        response = self.client.get("/datasets/coco_dataset")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertIn("id", output)
        self.assertIn("name", output)
        self.assertIn("description", output)
        self.assertIn("preview", output)

    def test_get_dataset_items(self):
        response = self.client.get("/datasets/coco_dataset/items")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertIn("total", output)
        self.assertIn("page", output)
        self.assertIn("size", output)
        self.assertIn("pages", output)

    def test_get_dataset_stats(self):
        response = self.client.get("/datasets/coco_dataset/stats")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertGreaterEqual(len(output), 1)

        for stat in output:
            self.assertIn("name", stat)
            self.assertIn("type", stat)
            self.assertIn("histogram", stat)

    def test_get_item_details(self):
        response = self.client.get("/datasets/coco_dataset/items/139")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertIn("itemData", output)
        self.assertIn("itemObjects", output)

        self.assertIn("id", output["itemData"])
        self.assertIn("views", output["itemData"])
        self.assertIn("features", output["itemData"])
        self.assertIn("Ground Truth", output["itemObjects"])

    def test_post_item_details(self):
        response = self.client.post(
            "/datasets/coco_dataset/items/127/details",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={
                "itemData": [
                    {"name": "feature", "dtype": "text", "value": "a text feature"}
                ],
                "itemObjects": [
                    {"id": "object1", "source_id": "unit test"},
                    {"id": "object2", "source_id": "unit test"},
                ],
            },
        )

        self.assertEqual(response.status_code, 200)
