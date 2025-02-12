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
from pixano.features import Source
from pixano.features.schemas.schema_group import SchemaGroup


class TestCOCODatasetExporter:
    def test_initialize_export_data(self, dataset_image_bboxes_keypoint: Dataset):
        exporter = COCODatasetExporter(dataset_image_bboxes_keypoint, "/")
        info = dataset_image_bboxes_keypoint.info
        sources = [Source(name="test", kind="model")]

        export_data = exporter.initialize_export_data(info, sources)
        expected_export_data = {
            "info": info.model_dump(),
            "sources": [sources[0].model_dump(exclude_timestamps=True)],
            "annotations": {"bboxes": [], "keypoint": []},
            "entities": {"entities": []},
            "items": [],
            "views": {"image": []},
        }

        assert export_data == expected_export_data

    def test_export_dataset_item(self, dataset_image_bboxes_keypoint: Dataset):
        exporter = COCODatasetExporter(dataset_image_bboxes_keypoint, "/")
        dataset_items = dataset_image_bboxes_keypoint.get_dataset_items(limit=2)
        dataset_item = dataset_items[0]
        info = dataset_image_bboxes_keypoint.info
        export_data = {
            "info": info.model_dump(),
            "annotations": {"bboxes": [], "keypoint": []},
            "entities": {"entities": []},
            "items": [],
            "views": {"image": []},
        }

        exporter.export_dataset_item(export_data, dataset_item)
        expected_export_data = {
            "info": info.model_dump(),
            "annotations": {
                "bboxes": [bbox.model_dump(exclude_timestamps=True) for bbox in dataset_item.bboxes],
                "keypoint": [],
            },
            "entities": {"entities": [entity.model_dump(exclude_timestamps=True) for entity in dataset_item.entities]},
            "items": [
                dataset_image_bboxes_keypoint.schema.schemas[SchemaGroup.ITEM.value](
                    id=dataset_item.id, split=dataset_item.split, metadata=dataset_item.metadata
                ).model_dump(exclude_timestamps=True)
            ],
            "views": {"image": [dataset_item.image.model_dump(exclude_timestamps=True)]},
        }

        assert export_data == expected_export_data

        dataset_item = dataset_items[1]
        export_data = {
            "info": info.model_dump(),
            "annotations": {"bboxes": [], "keypoint": []},
            "entities": {"entities": []},
            "items": [],
            "views": {"image": []},
        }

        exporter.export_dataset_item(export_data, dataset_item)
        expected_export_data = {
            "info": info.model_dump(),
            "annotations": {
                "bboxes": [bbox.model_dump(exclude_timestamps=True) for bbox in dataset_item.bboxes],
                "keypoint": [],
            },
            "entities": {"entities": [entity.model_dump(exclude_timestamps=True) for entity in dataset_item.entities]},
            "items": [
                dataset_image_bboxes_keypoint.schema.schemas[SchemaGroup.ITEM.value](
                    id=dataset_item.id, split=dataset_item.split, metadata=dataset_item.metadata
                ).model_dump(exclude_timestamps=True)
            ],
            "views": {"image": [dataset_item.image.model_dump(exclude_timestamps=True)]},
        }

        assert export_data == expected_export_data

    def test_save_data(self, dataset_image_bboxes_keypoint: Dataset):
        export_dir = Path(tempfile.mkdtemp())
        exporter = COCODatasetExporter(dataset_image_bboxes_keypoint, export_dir)
        export_data = {"save": "please"}
        exporter.save_data(export_data, "split", "file", 1)

        save_json = json.load((export_dir / "split_file_1.json").open())
        assert save_json == export_data
