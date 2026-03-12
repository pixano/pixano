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
from pixano.datasets.exporters.coco_dataset_exporter import coco_image
from pixano.features import BBox, CompressedRLE, Image, SequenceFrame


class TestCOCODatasetExporter:
    def test_initialize_export_data(
        self,
        dataset_image_bboxes_keypoint: Dataset,
        dataset_multi_view_tracking_and_image: Dataset,
    ):
        for ds in [dataset_image_bboxes_keypoint, dataset_multi_view_tracking_and_image]:
            exporter = COCODatasetExporter(ds, "/")
            info = ds.info
            export_data = exporter.initialize_export_data(info)

            assert list(export_data.keys()) == ["info", "licenses", "images", "annotations", "categories"]
            assert export_data["info"]["id"] == info.id
            assert export_data["info"]["name"] == info.name
            assert export_data["info"]["description"] == info.description

    def test_export_record(
        self,
        dataset_image_bboxes_keypoint: Dataset,
        dataset_multi_view_tracking_and_image: Dataset,
    ):
        for ds in [dataset_image_bboxes_keypoint, dataset_multi_view_tracking_and_image]:
            exporter = COCODatasetExporter(ds, "/")
            records = ds.get_records(limit=2)

            for record in records:
                record_data = exporter._get_record_data(record.id)
                export_data = {"annotations": [], "images": []}
                export_data = exporter.export_record(export_data, record_data)

                images = []
                for schema_name, schema_row in record_data.items():
                    rows = schema_row if isinstance(schema_row, list) else ([schema_row] if schema_row else [])
                    for schema in rows:
                        if isinstance(schema, Image | SequenceFrame):
                            images.append(coco_image(schema, schema_name))

                assert export_data["images"] == images
                for annotation in export_data["annotations"]:
                    assert annotation["image_id"] != ""
                    assert annotation["pixano_entity_id"] != ""
                    assert annotation["bbox"] is not None or annotation["segmentation"] is not None

    def test_save_data(
        self,
        dataset_image_bboxes_keypoint: Dataset,
        dataset_multi_view_tracking_and_image: Dataset,
    ):
        for ds in [dataset_image_bboxes_keypoint, dataset_multi_view_tracking_and_image]:
            export_dir = Path(tempfile.mkdtemp())
            exporter = COCODatasetExporter(ds, export_dir)
            export_data = {"save": "please"}
            exporter.save_data(export_data, "split", "file", 1)

            save_json = json.load((export_dir / "split_file_1.json").open())
            assert save_json == export_data
