# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import tempfile
from pathlib import Path

from pixano.datasets.dataset import Dataset
from pixano.datasets.exporters import DefaultJSONLDatasetExporter
from pixano.features import Source


class TestDefaultJSONLDataset:
    def test_initialize_export_data(self, dataset_image_bboxes_keypoint: Dataset):
        exporter = DefaultJSONLDatasetExporter(dataset_image_bboxes_keypoint, "/")
        info = dataset_image_bboxes_keypoint.info
        sources = [Source(name="test", kind="model")]

        export_data = exporter.initialize_export_data(info, sources)
        expected_export_data = [
            {"info": info.model_dump(), "sources": [sources[0].model_dump(exclude_timestamps=True)]},
        ]

        assert export_data == expected_export_data

    def test_export_dataset_item(self, dataset_image_bboxes_keypoint: Dataset):
        exporter = DefaultJSONLDatasetExporter(dataset_image_bboxes_keypoint, "/")
        dataset_item = dataset_image_bboxes_keypoint.get_dataset_items(limit=1)[0]

        export_data = []
        export_data = exporter.export_dataset_item(export_data, dataset_item)

        expected_export_data = [dataset_item.model_dump(exclude_timestamps=True)]

        assert export_data == expected_export_data

    def test_save_data(self, dataset_image_bboxes_keypoint: Dataset):
        export_dir = Path(tempfile.mkdtemp())
        exporter = DefaultJSONLDatasetExporter(dataset_image_bboxes_keypoint, export_dir)
        export_data = [dataset_image_bboxes_keypoint.info.model_dump(), {"save": "please"}]
        exporter.save_data(export_data, "split", "file", 1)

        saved_jsonl = (export_dir / "info.json").open().readlines() + (
            export_dir / "split_file_1.jsonl"
        ).open().readlines()
        saved_jsonl = [json.loads(line) for line in saved_jsonl]
        assert saved_jsonl == export_data
