# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi.encoders import jsonable_encoder

from pixano.datasets.utils.labels import CATEGORY_IDS
from pixano.features import (
    BaseSchema,
    SchemaGroup,
    Source,
    schema_to_group,
)
from pixano.features.schemas import BBox, CompressedRLE, Entity, Image, SequenceFrame

from ..dataset import Dataset
from ..dataset_info import DatasetInfo
from ..dataset_schema import DatasetItem
from .dataset_exporter import DatasetExporter


class COCODatasetExporter(DatasetExporter):
    """Default JSON dataset exporter."""

    def __init__(
        self,
        dataset: Dataset,
        export_dir: str | Path,
        overwrite: bool = False,
        category_format: str = "coco91",
        custom_category_dict: dict[str, int] | None = None,
    ):
        """Initialize a new instance of the DatasetExporter class.

        Args:
            dataset: The dataset to be exported.
            export_dir: The directory where the exported files will be saved.
            overwrite: Whether to overwrite existing directory.
            category_format: Category format for name to ID conversion ("coco91", "coco80", "voc").
            custom_category_dict: Custom category dictionary for name to ID conversion (supersedes category_format).
        """
        self.dataset = dataset
        self.export_dir = Path(export_dir)
        self._overwrite = overwrite
        self.category_dict = (
            custom_category_dict if custom_category_dict is not None else CATEGORY_IDS[category_format]
        )

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

    def export_dataset_item(self, export_data: dict[str, Any], dataset_item: DatasetItem) -> dict[str, Any]:
        """Store the dataset item in the `export_data` dictionary.

        Args:
            export_data: A dictionary containing the data to be exported.
            dataset_item: The dataset item to be exported.

        Returns:
            A dictionary containing the data to be exported.
        """
        data: dict[str, BaseSchema | list[BaseSchema] | None] = dataset_item.to_schemas_data(self.dataset.schema)
        # Keep annotations in a dictionary to merge BBox, CompressedRLE, and Category before adding to export_data
        anns = {s["id"]: s for s in export_data["annotations"]}
        for schema_name, schema_data in data.items():
            if schema_data:
                schema_data = schema_data if isinstance(schema_data, list) else [schema_data]
                group = schema_to_group(schema_data[0])
                if group == SchemaGroup.VIEW:
                    export_data["images"].extend(
                        [coco_image(s, schema_name) for s in schema_data if isinstance(s, Image)]
                    )
                elif group == SchemaGroup.ENTITY:
                    for schema in schema_data:
                        if isinstance(schema, Entity) and hasattr(schema, "category"):
                            ann_id = f"{schema.view_ref.id}_{schema.id}"
                            anns[ann_id] = coco_annotation(
                                ann=schema,
                                existing_coco_ann=anns[ann_id] if ann_id in anns.keys() else None,
                                category_dict=self.category_dict,
                            )
                elif group == SchemaGroup.ANNOTATION:
                    for schema in schema_data:
                        if isinstance(schema, BBox | CompressedRLE):
                            ann_id = f"{schema.view_ref.id}_{schema.entity_ref.id}"
                            anns[ann_id] = coco_annotation(
                                ann=schema,
                                existing_coco_ann=anns[ann_id] if ann_id in anns.keys() else None,
                            )
        export_data["annotations"] = list(anns.values())
        return export_data

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
        image: Image
        view: Image view

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


def coco_annotation(
    ann: BBox | CompressedRLE | Entity,
    existing_coco_ann: dict[str, Any] | None = None,
    category_dict: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Return annotation in COCO format.

    Args:
        ann: Annotation
        existing_coco_ann: Existing annotation in COCO format to complete
        category_dict: Category dictonary for name to ID conversion
    Returns:
        Annotation in COCO format
    """
    # Load the existing COCO format or initialize a new one
    coco_ann = (
        existing_coco_ann
        if existing_coco_ann is not None
        else {
            "id": f"{ann.view_ref.id}_{ann.id if isinstance(ann, Entity) else ann.entity_ref.id}",
            "image_id": ann.view_ref.id,
            "category_id": None,
            "category_name": None,
            "segmentation": None,
            "area": None,
            "bbox": None,
            "confidence": None,
            "iscrowd": 0,
            "pixano_entity_id": ann.id if isinstance(ann, Entity) else ann.entity_ref.id,
        }
    )
    # Add the specific elements from the annotation into the COCO format
    if isinstance(ann, Entity):
        category_name = str(ann.category).strip().lower()
        coco_ann["category_name"] = category_name
        coco_ann["category_id"] = (
            category_dict[category_name] if category_dict is not None and category_name in category_dict else None
        )
    else:
        if isinstance(ann, BBox):
            coco_ann["pixano_bbox_id"] = ann.id
            coco_ann["bbox"] = ann.xywh_coords
            coco_ann["confidence"] = ann.confidence
        elif isinstance(ann, CompressedRLE):
            coco_ann["pixano_segmentation_id"] = ann.id
            coco_ann["segmentation"] = ann.to_polygons()
            coco_ann["area"] = ann.area
    return coco_ann
