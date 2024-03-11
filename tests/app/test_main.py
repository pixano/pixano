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
from functools import lru_cache
from pathlib import Path

from fastapi.testclient import TestClient
from pixano_inference import transformers

from pixano.app import create_app
from pixano.data import (
    COCOImporter,
    DatasetInfo,
    DatasetItem,
    DatasetStat,
    Settings,
    get_settings,
)


class AppTestCase(unittest.TestCase):
    """Pixano app test case"""

    def setUp(self):
        """Tests setup"""

        # Create temporary directory
        # pylint: disable=consider-using-with
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name)
        (self.path / "models").mkdir()

        # Create a COCO dataset
        import_dir = self.path / "coco"
        input_dirs = {
            "image": Path("tests/assets/coco_dataset/image"),
            "objects": Path("tests/assets/coco_dataset"),
        }
        importer = COCOImporter(
            name="coco",
            description="COCO dataset",
            input_dirs=input_dirs,
            splits=["val"],
        )
        self.dataset = importer.import_dataset(import_dir, copy=True)

        # Set dataset ID
        self.dataset.info.id = "coco_dataset"
        self.dataset.save_info()

        # Create dataset stats
        stats = [
            DatasetStat(
                name="Some numerical statistics",
                type="numerical",
                histogram=[
                    {"bin_start": 0.0, "bin_end": 1.0, "counts": 2, "split": "train"},
                    {"bin_start": 1.0, "bin_end": 2.0, "counts": 4, "split": "train"},
                    {"bin_start": 2.0, "bin_end": 3.0, "counts": 6, "split": "train"},
                    {"bin_start": 3.0, "bin_end": 4.0, "counts": 8, "split": "train"},
                ],
                range=[0.0, 10.0],
            ),
            DatasetStat(
                name="Some categorical statistics",
                type="categorical",
                histogram=[
                    {"Some categorical statistics": "a", "counts": 2, "split": "train"},
                    {"Some categorical statistics": "b", "counts": 4, "split": "train"},
                    {"Some categorical statistics": "c", "counts": 6, "split": "train"},
                    {"Some categorical statistics": "d", "counts": 8, "split": "train"},
                ],
            ),
        ]
        with open(import_dir / "stats.json", "w", encoding="utf-8") as f:
            json.dump([stat.model_dump() for stat in stats], f)

        # Override app settings
        @lru_cache
        def get_settings_override():
            return Settings(library_dir=self.temp_dir.name)

        # Create app
        app = create_app(settings=get_settings_override())
        app.dependency_overrides[get_settings] = get_settings_override
        self.client = TestClient(app)

    def tearDown(self):
        """Tests teardown"""

        self.temp_dir.cleanup()

    def test_get_datasets(self):
        """Test /datasets endpoint (GET)"""

        response = self.client.get("/datasets")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertEqual(len(output), 1)

        for ds in output:
            ds_info = DatasetInfo.model_validate(ds)
            self.assertIsInstance(ds_info, DatasetInfo)

    def test_get_dataset(self):
        """Test /datasets/{dataset_id} endpoint (GET)"""

        response = self.client.get("/datasets/coco_dataset")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        ds_info = DatasetInfo.model_validate(output)
        self.assertIsInstance(ds_info, DatasetInfo)

    def test_get_dataset_items(self):
        """Test /datasets/{dataset_id}/items endpoint (GET)"""

        response = self.client.get("/datasets/coco_dataset/items")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertIn("items", output)
        self.assertIn("total", output)
        self.assertIn("page", output)
        self.assertIn("size", output)
        self.assertIn("pages", output)

        self.assertEqual(len(output["items"]), 3)

        for item in output["items"]:
            ds_item = DatasetItem.model_validate(item)
            self.assertIsInstance(ds_item, DatasetItem)

    def test_search_dataset_items(self):
        """Test /datasets/{dataset_id}/search endpoint (POST)"""

        # Without embeddings
        response = self.client.post(
            "/datasets/coco_dataset/search",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={"model": "CLIP", "search": "bear"},
        )

        self.assertEqual(response.status_code, 404)

        # With embeddings
        model = transformers.CLIP()
        model.process_dataset(
            dataset_dir=self.path / "coco",
            process_type="search_emb",
            views=["image"],
        )

        response = self.client.post(
            "/datasets/coco_dataset/search",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json={"model": "CLIP", "search": "bear"},
        )
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertIn("items", output)
        self.assertIn("total", output)
        self.assertIn("page", output)
        self.assertIn("size", output)
        self.assertIn("pages", output)

        self.assertEqual(len(output["items"]), 3)

        for item in output["items"]:
            ds_item = DatasetItem.model_validate(item)
            self.assertIsInstance(ds_item, DatasetItem)

    def test_get_dataset_item(self):
        """Test /datasets/{dataset_id}/items/{item_id} endpoint (GET)"""

        # get item uuid from original id
        item_uuid = self.dataset.get_item_uuid("139")
        response = self.client.get(f"/datasets/coco_dataset/items/{item_uuid}")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        ds_item = DatasetItem.model_validate(output)
        self.assertIsInstance(ds_item, DatasetItem)

    def test_post_dataset_item(self):
        """Test /datasets/{dataset_id}/items/{item_id} endpoint (POST)"""

        # get item uuid from original id
        item_uuid = self.dataset.get_item_uuid("139")
        response_1 = self.client.get(f"/datasets/coco_dataset/items/{item_uuid}")
        output = response_1.json()

        ds_item = DatasetItem.model_validate(output)

        response_2 = self.client.post(
            "/datasets/coco_dataset/items/127",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
            },
            json=ds_item.model_dump(),
        )

        self.assertEqual(response_2.status_code, 200)

    def test_get_dataset_item_embeddings(self):
        """Test /datasets/{dataset_id}/items/{item_id}/embeddings/{model_id}
        endpoint (GET)"""

        response = self.client.get("/datasets/coco_dataset/items/139/embeddings/SAM")

        # NOTE: Can't test embeddings without model weights
        self.assertEqual(response.status_code, 404)

    def test_get_models(self):
        """Test /models endpoint (GET)"""

        with tempfile.NamedTemporaryFile(dir=self.path / "models", suffix=".onnx"):
            response = self.client.get("/models")
            output = response.json()

            self.assertEqual(response.status_code, 200)

            self.assertEqual(len(output), 1)

            for model in output:
                self.assertIsInstance(model, str)
                self.assertIn(".onnx", model)
