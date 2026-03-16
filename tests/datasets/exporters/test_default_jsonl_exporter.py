# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import tempfile
from pathlib import Path

from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_schema import build_model_dump_exclude_timestamps
from pixano.datasets.exporters import DefaultJSONLDatasetExporter


class TestDefaultJSONLDataset:
    def test_initialize_export_data(self, dataset_image_bboxes_keypoint: Dataset):
        exporter = DefaultJSONLDatasetExporter(dataset_image_bboxes_keypoint, "/")
        info = dataset_image_bboxes_keypoint.info

        export_data = exporter.initialize_export_data(info)
        expected_export_data = [
            {"info": info.model_dump(exclude={"tables"})},
        ]

        assert export_data == expected_export_data

    def test_export_record(self, dataset_image_bboxes_keypoint: Dataset):
        exporter = DefaultJSONLDatasetExporter(dataset_image_bboxes_keypoint, "/")
        records = dataset_image_bboxes_keypoint.get_data("record", limit=1)
        record_id = records[0].id
        record_data = exporter._get_record_data(record_id)

        export_data = []
        export_data = exporter.export_record(export_data, record_data)

        assert len(export_data) == 1
        exported = export_data[0]
        # The exported dict should have keys for each table
        assert "record" in exported

    def test_save_data(self, dataset_image_bboxes_keypoint: Dataset):
        export_dir = Path(tempfile.mkdtemp())
        exporter = DefaultJSONLDatasetExporter(dataset_image_bboxes_keypoint, export_dir)
        export_data = [dataset_image_bboxes_keypoint.info.model_dump(exclude={"tables"}), {"save": "please"}]
        exporter.save_data(export_data, "split", "file", 1)

        saved_jsonl = (export_dir / "info.json").open().readlines() + (
            export_dir / "split_file_1.jsonl"
        ).open().readlines()
        saved_jsonl = [json.loads(line) for line in saved_jsonl]
        assert saved_jsonl == export_data
