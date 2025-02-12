# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import json
from datetime import datetime
from typing import Any

from fastapi.encoders import jsonable_encoder

from pixano.features import (
    BaseSchema,
    SchemaGroup,
    Source,
    schema_to_group,
)
from pixano.features.schemas import BBox, CompressedRLE, Image, SequenceFrame

from ..dataset_info import DatasetInfo
from ..dataset_schema import DatasetItem
from .dataset_exporter import DatasetExporter


class COCODatasetExporter(DatasetExporter):
    """Default JSON dataset exporter."""

    def initialize_export_data(self, info: DatasetInfo, sources: list[Source]) -> dict[str, Any]:
        """Initialize the dictionary or list of dictionaries to be exported.

        Args:
            info: The dataset information.
            sources: The list of sources.

        Returns:
            A dictionary containing the data to be exported.
        """
        export_data = {
            "info": {
                "id": info.id,
                "name": info.name,
                "year": datetime.now().year,
                "version": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
                "description": info.description,
                "contributor": "",
                "url": "",
                "date_created": datetime.now(),
            },
            "licenses": [
                {
                    "id": 0,
                    "name": "Exported from Pixano",
                    "url": "",
                }
            ],
            "images": [],
            "annotations": [],
            "categories": [],
        }
        return export_data

    def export_dataset_item(self, export_data: dict[str, Any], dataset_item: DatasetItem) -> None:
        """Store the dataset item in the `export_data` dictionary.

        Args:
            export_data: A dictionary containing the data to be exported.
            dataset_item: The dataset item to be exported.
        """
        data: dict[str, BaseSchema | list[BaseSchema] | None] = dataset_item.to_schemas_data(self.dataset.schema)
        for schema_name, schema_data in data.items():
            if schema_data is None or isinstance(schema_data, list) and len(schema_data) == 0:
                continue
            elif isinstance(schema_data, list):
                group = schema_to_group(schema_data[0])
                if group == SchemaGroup.VIEW:
                    export_data["images"].extend(
                        [coco_image(s, schema_name) for s in schema_data if isinstance(s, Image)]
                    )
                elif group == SchemaGroup.ANNOTATION:
                    anns = {s["entity_id"]: s for s in export_data["annotations"]}
                    for schema in schema_data:
                        if isinstance(schema, BBox | CompressedRLE):
                            entity_id = schema.entity_ref.id
                            if entity_id in anns.keys():
                                anns[entity_id] = coco_annotation(schema, anns[entity_id])
                            else:
                                anns[entity_id] = coco_annotation(schema)

                    export_data["annotations"].extend(list(anns.values()))
            else:
                group = schema_to_group(schema_data)
                if group == SchemaGroup.VIEW:
                    export_data["images"].append(coco_image(schema_data, schema_name))
                elif group == SchemaGroup.ANNOTATION and isinstance(schema_data, BBox | CompressedRLE):
                    anns = {s["entity_id"]: s for s in export_data["annotations"]}
                    entity_id = schema_data.entity_ref.id
                    if entity_id in anns.keys():
                        anns[entity_id] = coco_annotation(schema_data, anns[entity_id])
                    else:
                        anns[entity_id] = coco_annotation(schema_data)
                    export_data["annotations"] = list(anns.values())

    def save_data(self, export_data: dict[str, Any], split: str, file_name: str, file_num: int) -> None:
        """Save data to the specified directory.

        The saved directory has the following structure:
            export_dir/{split}_{file_name}_0.json
                      /...
                      /{split}_{file_name}_{file_num}.json
                      /...
                      /{split}_{file_name}_n.json


        Args:
            export_data: The dictionary containing the data to be saved.
            split: The split of the dataset item being saved.
            file_name: The name of the file to save the data in.
            file_num: The number of the file to save the data in.
        """
        json_path = self.export_dir / f"{split}_{file_name}_{file_num}.json"
        json_path.write_text(json.dumps(jsonable_encoder(export_data), indent=4), encoding="utf-8")


def coco_image(image: Image, view: str) -> dict[str, Any]:
    """Return image in COCO format.

    Args:
        image (Image): Image
        view (str): Image view

    Returns:
        Image in COCO format
    """
    coco_img = {
        "id": image.id,
        "view": view,
        "width": image.width,
        "height": image.height,
        "file_name": image.url,
        "license": 0,
        "date_captured": image.created_at,
    }
    if isinstance(image, SequenceFrame):
        coco_img["timestamp"] = image.timestamp
        coco_img["frame_index"] = image.frame_index
    return coco_img


def coco_annotation(ann: BBox | CompressedRLE, existing_coco_ann: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return annotation in COCO format.

    Args:
        ann (BBox | CompressedRLE): Annotation
        existing_coco_ann (dict[str, Any]): Existing annotation in COCO format to complete

    Returns:
        Annotation in COCO format
    """
    coco_ann = {}
    if existing_coco_ann is not None:
        coco_ann = existing_coco_ann
        if isinstance(ann, BBox):
            coco_ann["bbox"] = ann.xywh_coords
            coco_ann["confidence"] = ann.confidence
        elif isinstance(ann, CompressedRLE):
            coco_ann["segmentation"] = ann.to_polygons()
            coco_ann["area"] = ann.area
    else:
        if isinstance(ann, BBox):
            coco_ann = {
                "id": ann.id,
                "entity_id": ann.entity_ref.id,
                "image_id": ann.view_ref.id,
                "category_id": None,  # TODO: category
                "segmentation": None,
                "area": None,
                "bbox": ann.coords,
                "confidence": ann.confidence,
                "iscrowd": 0,
            }
        elif isinstance(ann, CompressedRLE):
            coco_ann = {
                "id": ann.id,
                "entity_id": ann.entity_ref.id,
                "image_id": ann.view_ref.id,
                "category_id": None,  # TODO: category
                "segmentation": ann.to_polygons(),
                "area": ann.area,
                "bbox": None,
                "iscrowd": 0,
            }
    return coco_ann
