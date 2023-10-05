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

import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from pixano.api import Settings
from pixano.apps.main import create_app


class AppTestCase(unittest.TestCase):
    def setUp(self):
        self.settings = Settings(data_dir=Path("unit_testing/assets/"))
        self.client = TestClient(create_app(self.settings))

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
        response = self.client.get("/datasets/vdp_dataset")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertIn("id", output)
        self.assertIn("name", output)
        self.assertIn("description", output)
        self.assertIn("preview", output)

    def test_get_dataset_items(self):
        response = self.client.get("/datasets/vdp_dataset/items")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertIn("total", output)
        self.assertIn("page", output)
        self.assertIn("size", output)
        self.assertIn("pages", output)

    def test_get_dataset_stats(self):
        response = self.client.get("/datasets/vdp_dataset/stats")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertGreaterEqual(len(output), 1)

        for stat in output:
            self.assertIn("name", stat)
            self.assertIn("type", stat)
            self.assertIn("histogram", stat)

    def test_get_item_details(self):
        response = self.client.get("/datasets/vdp_dataset/items/127")
        output = response.json()

        self.assertEqual(response.status_code, 200)

        self.assertIn("itemData", output)
        self.assertIn("itemObjects", output)

        self.assertIn("id", output["itemData"])
        self.assertIn("views", output["itemData"])
        self.assertIn("features", output["itemData"])
        self.assertIn("ground truth", output["itemObjects"])

    def test_post_item_details(self):
        response = self.client.post(
            "/datasets/vdp_dataset/items/127/details",
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
