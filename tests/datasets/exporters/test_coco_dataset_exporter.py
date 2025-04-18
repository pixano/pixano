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
from pixano.features import BBox, CompressedRLE, Entity, Image, Source


class TestCOCODatasetExporter:
    def test_initialize_export_data(
        self,
        dataset_image_bboxes_keypoint: Dataset,
        dataset_multi_view_tracking_and_image: Dataset,
    ):
        for ds in [dataset_image_bboxes_keypoint, dataset_multi_view_tracking_and_image]:
            exporter = COCODatasetExporter(ds, "/")
            info = ds.info
            sources = [Source(name="test", kind="model")]
            export_data = exporter.initialize_export_data(info, sources)

            assert list(export_data.keys()) == ["info", "licenses", "images", "annotations", "categories"]
            assert export_data["info"]["id"] == info.id
            assert export_data["info"]["name"] == info.name
            assert export_data["info"]["description"] == info.description

    def test_export_dataset_item(
        self,
        dataset_image_bboxes_keypoint: Dataset,
        dataset_multi_view_tracking_and_image: Dataset,
    ):
        for ds in [dataset_image_bboxes_keypoint, dataset_multi_view_tracking_and_image]:
            exporter = COCODatasetExporter(ds, "/")
            dataset_items = ds.get_dataset_items(limit=2)

            for dataset_item in dataset_items:
                export_data = {"annotations": [], "images": []}
                export_data = exporter.export_dataset_item(export_data, dataset_item)

                images = []
                annotations = {}
                for schema_name, schema_data in dataset_item.to_schemas_data(ds.schema).items():
                    schemas = schema_data if isinstance(schema_data, list) else [schema_data]
                    for schema in schemas:
                        if (isinstance(schema, Entity) and hasattr(schema, "category")) or isinstance(
                            schema, BBox | CompressedRLE
                        ):
                            entity_id = schema.id if isinstance(schema, Entity) else schema.entity_ref.id
                            if entity_id in annotations.keys():
                                annotations[entity_id] = coco_annotation(
                                    ann=schema,
                                    existing_coco_ann=annotations[entity_id],
                                    category_dict=exporter.category_dict,
                                )
                            else:
                                annotations[entity_id] = coco_annotation(
                                    ann=schema,
                                    category_dict=exporter.category_dict,
                                )
                        elif isinstance(schema, Image):
                            images.append(coco_image(schema, schema_name))

                expected_export_data = {
                    "annotations": list(annotations.values()),
                    "images": images,
                }

                assert export_data == expected_export_data

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
