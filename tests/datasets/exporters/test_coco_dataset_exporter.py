# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import tempfile
from pathlib import Path

from pixano.datasets.dataset import Dataset
from pixano.datasets.exporters import COCODatasetExporter
from pixano.datasets.exporters.coco_dataset_exporter import coco_annotation, coco_image
from pixano.features import Source


class TestCOCODatasetExporter:
    def test_initialize_export_data(self, dataset_image_bboxes_keypoint: Dataset):
        exporter = COCODatasetExporter(dataset_image_bboxes_keypoint, "/")
        info = dataset_image_bboxes_keypoint.info
        sources = [Source(name="test", kind="model")]

        export_data = exporter.initialize_export_data(info, sources)

        assert list(export_data.keys()) == ["info", "licenses", "images", "annotations", "categories"]
        assert export_data["info"]["id"] == info.id
        assert export_data["info"]["name"] == info.name
        assert export_data["info"]["description"] == info.description

    def test_export_dataset_item(self, dataset_image_bboxes_keypoint: Dataset):
        exporter = COCODatasetExporter(dataset_image_bboxes_keypoint, "/")
        dataset_items = dataset_image_bboxes_keypoint.get_dataset_items(limit=2)
        dataset_item = dataset_items[0]
        export_data = {
            "annotations": [],
            "images": [],
        }

        exporter.export_dataset_item(export_data, dataset_item)
        expected_export_data = {
            "annotations": [coco_annotation(bbox) for bbox in dataset_item.bboxes],
            "images": [coco_image(dataset_item.image, "image")],
        }

        assert export_data == expected_export_data

        dataset_item = dataset_items[1]
        export_data = {
            "annotations": [],
            "images": [],
        }

        exporter.export_dataset_item(export_data, dataset_item)
        expected_export_data = {
            "annotations": [coco_annotation(bbox) for bbox in dataset_item.bboxes],
            "images": [coco_image(dataset_item.image, "image")],
        }

        assert export_data == expected_export_data

    def test_save_data(self, dataset_image_bboxes_keypoint: Dataset):
        export_dir = Path(tempfile.mkdtemp())
        exporter = COCODatasetExporter(dataset_image_bboxes_keypoint, export_dir)
        export_data = {"save": "please"}
        exporter.save_data(export_data, "split", "file", 1)

        save_json = json.load((export_dir / "split_file_1.json").open())
        assert save_json == export_data
