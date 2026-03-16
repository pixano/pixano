# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import tempfile
from pathlib import Path

from pixano.datasets.dataset import Dataset
from pixano.datasets.exporters import DefaultJSONDatasetExporter
from pixano.schemas.schema_group import SchemaGroup


class TestDefaultJSONDatasetExporter:
    def test_initialize_export_data(self, dataset_image_bboxes_keypoint: Dataset):
        exporter = DefaultJSONDatasetExporter(dataset_image_bboxes_keypoint, "/")
        info = dataset_image_bboxes_keypoint.info

        export_data = exporter.initialize_export_data(info)
        # The new exporter no longer includes sources; verify expected keys
        assert "info" in export_data
        assert export_data["info"] == info.json_info_dump()

    def test_export_record(self, dataset_image_bboxes_keypoint: Dataset):
        exporter = DefaultJSONDatasetExporter(dataset_image_bboxes_keypoint, "/")
        info = dataset_image_bboxes_keypoint.info

        records = dataset_image_bboxes_keypoint.get_records(limit=2)
        _TS_EXCLUDE = {"created_at", "updated_at"}

        for record in records:
            record_data = exporter._get_record_data(record.id)
            export_data = exporter.initialize_export_data(info)
            export_data = exporter.export_record(export_data, record_data)

            # Build expected export data
            expected_export_data = exporter.initialize_export_data(info)

            # Record row
            expected_export_data["records"].append(record_data["records"].model_dump(exclude=_TS_EXCLUDE))

            # Views
            image_data = record_data.get("images")
            if image_data:
                images = image_data if isinstance(image_data, list) else [image_data]
                expected_export_data["views"]["images"].extend([img.model_dump(exclude=_TS_EXCLUDE) for img in images])

            # Entities
            entity_data = record_data.get("entities")
            if entity_data:
                entities = entity_data if isinstance(entity_data, list) else [entity_data]
                expected_export_data["entities"]["entities"].extend(
                    [e.model_dump(exclude=_TS_EXCLUDE) for e in entities]
                )

            # Annotations
            bbox_data = record_data.get("bboxes")
            if bbox_data:
                bboxes = bbox_data if isinstance(bbox_data, list) else [bbox_data]
                expected_export_data["annotations"]["bboxes"].extend(
                    [b.model_dump(exclude=_TS_EXCLUDE) for b in bboxes]
                )

            assert export_data == expected_export_data

    def test_save_data(self, dataset_image_bboxes_keypoint: Dataset):
        export_dir = Path(tempfile.mkdtemp())
        exporter = DefaultJSONDatasetExporter(dataset_image_bboxes_keypoint, export_dir)
        export_data = {"save": "please"}
        exporter.save_data(export_data, "split", "file", 1)

        save_json = json.load((export_dir / "split_file_1.json").open())
        assert save_json == export_data
