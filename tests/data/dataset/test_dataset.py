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

import json
import tempfile
import unittest
import warnings
from pathlib import Path

import lancedb

from pixano.core import Image
from pixano.data import (
    COCOImporter,
    Dataset,
    DatasetInfo,
    DatasetItem,
    DatasetStat,
    ItemObject,
)


class DatasetTestCase(unittest.TestCase):
    def setUp(self):
        # Create temporary directory
        self.temp_dir = tempfile.TemporaryDirectory()
        self.library_dir = Path(self.temp_dir.name)

        # Create a COCO dataset
        self.import_dir = self.library_dir / "coco"
        input_dirs = {
            "image": Path("tests/assets/coco_dataset/image"),
            "objects": Path("tests/assets/coco_dataset"),
        }
        importer = COCOImporter(
            name="coco",
            description="COCO dataset",
            splits=["val"],
        )
        dataset = importer.import_dataset(input_dirs, self.import_dir, copy=True)

        # Set dataset ID
        dataset.info.id = "coco_dataset"
        dataset.save_info()

        # Create dataset stats
        self.stats = [
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
        with open(self.import_dir / "stats.json", "w", encoding="utf-8") as f:
            json.dump([stat.model_dump() for stat in self.stats], f)

        # Load thumbnail
        self.thumbnail = Image(
            uri=(self.import_dir / "preview.png").absolute().as_uri()
        )

        # Load dataset
        self.dataset = Dataset(self.import_dir)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_path_property(self):
        self.assertIsInstance(self.dataset.path, Path)
        self.assertEqual(self.dataset.path, self.import_dir)

    def test_info_property(self):
        self.assertIsInstance(self.dataset.info, DatasetInfo)
        self.assertEqual(self.dataset.info.id, "coco_dataset")

    def test_stats_property(self):
        self.assertTrue(isinstance(self.dataset.stats, list))
        self.assertEqual(self.dataset.stats, self.stats)

    def test_thumbnail_property(self):
        self.assertIsInstance(self.dataset.thumbnail, str)
        self.assertEqual(
            self.dataset.thumbnail,
            self.thumbnail.url,
        )

    def test_media_dir_property(self):
        self.assertIsInstance(self.dataset.media_dir, Path)
        self.assertEqual(self.dataset.media_dir, self.import_dir / "media")

    def test_num_rows_property(self):
        self.assertIsInstance(self.dataset.num_rows, int)
        self.assertEqual(self.dataset.num_rows, 3)

    def test_load_info(self):
        loaded_info = self.dataset.load_info()

        self.assertIsInstance(loaded_info, DatasetInfo)
        self.assertEqual(loaded_info, self.dataset.info)

        full_loaded_info = self.dataset.load_info(load_stats=True, load_thumbnail=True)

        self.assertIsInstance(full_loaded_info, DatasetInfo)
        self.assertEqual(full_loaded_info.id, "coco_dataset")
        self.assertEqual(full_loaded_info.stats, self.stats)
        self.assertEqual(full_loaded_info.preview, self.thumbnail.url)

    def test_save_info(self):
        # Edit DatasetInfo
        self.dataset.info.id = "coco_dataset_2"
        self.dataset.save_info()

        updated_info = DatasetInfo.from_json(self.import_dir / "db.json")
        self.assertEqual(updated_info.id, "coco_dataset_2")

        # Revert DatasetInfo back to normal
        self.dataset.info.id = "coco_dataset"
        self.dataset.save_info()

        updated_info = DatasetInfo.from_json(self.import_dir / "db.json")
        self.assertEqual(updated_info.id, "coco_dataset")

    def test_connect(self):
        ds = self.dataset.connect()

        self.assertIsInstance(ds, lancedb.db.DBConnection)
        self.assertIn("db", ds.table_names())
        self.assertIn("image", ds.table_names())

    def test_open_tables(self):
        ds_tables = self.dataset.open_tables()

        self.assertIsInstance(ds_tables, dict)
        self.assertIsInstance(ds_tables["main"]["db"], lancedb.db.LanceTable)
        self.assertIsInstance(ds_tables["media"]["image"], lancedb.db.LanceTable)

    def test_load_items(self):
        items = self.dataset.load_items(limit=2, offset=0)

        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 2)

        self.assertIsInstance(items[0], DatasetItem)
        self.assertEqual(items[0].id, "139")
        self.assertEqual(items[0].image[0].id, "image")
        self.assertEqual(items[0].features[0].name, "split")

        self.assertIsInstance(items[1], DatasetItem)
        self.assertEqual(items[1].id, "285")
        self.assertEqual(items[1].image[0].id, "image")
        self.assertEqual(items[1].features[0].name, "split")

        items = self.dataset.load_items(limit=1, offset=2)

        self.assertIsInstance(items, list)
        self.assertEqual(len(items), 1)

        self.assertIsInstance(items[0], DatasetItem)
        self.assertEqual(items[0].id, "632")
        self.assertEqual(items[0].image[0].id, "image")
        self.assertEqual(items[0].features[0].name, "split")

    def test_search_items(self):
        items = self.dataset.search_items(limit=1, offset=0, query={"query": "bear"})

        self.assertEqual(items, None)

        try:
            from pixano_inference import transformers

            model = transformers.CLIP()
            model.process_dataset(
                dataset_dir=self.import_dir,
                process_type="search_emb",
                views=["image"],
            )
            items = self.dataset.search_items(
                limit=1, offset=0, query={"query": "bear"}
            )
            self.assertIsInstance(items, list)
            self.assertEqual(len(items), 1)
            self.assertEqual(items[0].id, "285")

        except ImportError:
            warnings.warn(
                "Can't test search_items() fully without pixano-inference for CLIP embeddings"
            )

    def test_load_item(self):
        item = self.dataset.load_item("632", load_objects=True)

        self.assertIsInstance(item, DatasetItem)
        self.assertEqual(item.id, "632")
        self.assertEqual(item.image[0].id, "image")
        self.assertEqual(item.features[0].name, "split")
        self.assertEqual(len(item.objects), 18)

    def test_save_item(self):
        # Original item has 18 objects
        item_1 = self.dataset.load_item("632", load_objects=True)
        self.assertEqual(len(item_1.objects), 18)

        # 1. Add object to existing table
        added_object_1 = ItemObject(
            id="added_object",
            item_id="632",
            view_id="image",
            source_id="Ground Truth",
            bbox=dict(coords=[0.1, 0.1, 0.3, 0.3], format="xywh"),
        )
        item_1.objects.append(added_object_1)
        self.dataset.save_item(item_1)

        # Item should now have 19 objects
        item_2 = self.dataset.load_item("632", load_objects=True)
        self.assertEqual(len(item_2.objects), 19)

        # 2. Edit existing object
        item_2.objects = [obj for obj in item_2.objects if obj.id != "added_object"]
        added_object_2 = ItemObject(
            id="added_object",
            item_id="632",
            view_id="image",
            source_id="Ground Truth",
            bbox=dict(coords=[0.2, 0.2, 0.4, 0.4], format="xywh"),
        )
        item_2.objects.append(added_object_2)
        self.dataset.save_item(item_2)

        # Item should still have 19 objects
        item_3 = self.dataset.load_item("632", load_objects=True)
        self.assertEqual(len(item_3.objects), 19)

        # 3. Delete existing object
        item_3.objects = [obj for obj in item_3.objects if obj.id != "added_object"]
        self.dataset.save_item(item_3)

        # Item should now have 18 objects again
        item_4 = self.dataset.load_item("632", load_objects=True)
        self.assertEqual(len(item_4.objects), 18)

        # 4. Add object to new table
        added_object_3 = ItemObject(
            id="added_object",
            item_id="632",
            view_id="image",
            source_id="Pixano Annotator",
            bbox=dict(coords=[0.1, 0.1, 0.3, 0.3], format="xywh"),
        )
        item_4.objects.append(added_object_3)
        self.dataset.save_item(item_4)

        # Item should now have 19 objects
        item_5 = self.dataset.load_item("632", load_objects=True)
        self.assertEqual(len(item_5.objects), 19)

    def test_find(self):
        print(self.dataset.info.id)
        found_dataset = Dataset.find("coco_dataset", self.library_dir)

        self.assertIsInstance(found_dataset, Dataset)
        self.assertEqual(found_dataset, self.dataset)
