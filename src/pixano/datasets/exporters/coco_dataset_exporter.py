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
from lancedb.pydantic import LanceModel

from pixano.datasets.utils.labels import CATEGORY_IDS
from pixano.schemas import (
    BBox,
    CompressedRLE,
    Entity,
    Image,
    SchemaGroup,
    SequenceFrame,
    schema_to_group,
)

from ..dataset import Dataset
from ..dataset_info import DatasetInfo
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

    def initialize_export_data(self, info: DatasetInfo) -> dict[str, Any]:
        """Initialize the dictionary or list of dictionaries to be exported.

        Args:
            info: The dataset information.

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

    def export_record(
        self, export_data: dict[str, Any], record_data: dict[str, LanceModel | list[LanceModel] | None]
    ) -> dict[str, Any]:
        """Store the record data in the `export_data` dictionary.

        Args:
            export_data: A dictionary containing the data to be exported.
            record_data: Dict of table_name → row(s) for this record.

        Returns:
            A dictionary containing the data to be exported.
        """
        view_rows_by_name: dict[str, list[Image | SequenceFrame]] = {}
        entity_categories: dict[str, str] = {}

        # Keep annotations in a dictionary to merge bbox/mask geometry with entity categories.
        anns = {s["id"]: s for s in export_data["annotations"]}
        for schema_name, schema_data in record_data.items():
            if schema_data:
                schema_data_list = schema_data if isinstance(schema_data, list) else [schema_data]
                group = schema_to_group(schema_data_list[0])
                if group == SchemaGroup.VIEW:
                    media_rows = [s for s in schema_data_list if isinstance(s, Image | SequenceFrame)]
                    view_rows_by_name[schema_name] = media_rows
                    export_data["images"].extend([coco_image(s, schema_name) for s in media_rows])
                elif group == SchemaGroup.ENTITY:
                    for schema in schema_data_list:
                        if isinstance(schema, Entity) and hasattr(schema, "category"):
                            entity_categories[schema.id] = str(schema.category).strip().lower()

        for schema_data in record_data.values():
            if not schema_data:
                continue
            schema_data_list = schema_data if isinstance(schema_data, list) else [schema_data]
            if schema_to_group(schema_data_list[0]) != SchemaGroup.ANNOTATION:
                continue
            for schema in schema_data_list:
                if not isinstance(schema, BBox | CompressedRLE):
                    continue
                image_id = _resolve_image_id(schema, view_rows_by_name)
                if image_id == "":
                    continue
                entity_id = schema.entity_id or schema.id
                ann_id = f"{image_id}_{entity_id}"
                anns[ann_id] = coco_annotation(
                    ann=schema,
                    image_id=image_id,
                    entity_id=entity_id,
                    category_name=entity_categories.get(entity_id),
                    existing_coco_ann=anns.get(ann_id),
                    category_dict=self.category_dict,
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
        "file_name": image.uri,
        "license": 0,
        "date_captured": "",
    }
    if isinstance(image, SequenceFrame):
        coco_img["timestamp"] = image.timestamp
        coco_img["frame_index"] = image.frame_index
    return coco_img


def _resolve_image_id(
    ann: BBox | CompressedRLE,
    view_rows_by_name: dict[str, list[Image | SequenceFrame]],
) -> str:
    if ann.frame_id:
        return ann.frame_id
    rows = view_rows_by_name.get(ann.view_id, [])
    return rows[0].id if rows else ""


def coco_annotation(
    ann: BBox | CompressedRLE,
    image_id: str,
    entity_id: str,
    category_name: str | None = None,
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
    coco_ann = (
        existing_coco_ann
        if existing_coco_ann is not None
        else {
            "id": f"{image_id}_{entity_id}",
            "image_id": image_id,
            "category_id": None,
            "category_name": None,
            "segmentation": None,
            "area": None,
            "bbox": None,
            "confidence": None,
            "iscrowd": 0,
            "pixano_entity_id": entity_id,
        }
    )
    if category_name is not None:
        coco_ann["category_name"] = category_name
        coco_ann["category_id"] = (
            category_dict[category_name] if category_dict is not None and category_name in category_dict else None
        )
    if isinstance(ann, BBox):
        coco_ann["pixano_bbox_id"] = ann.id
        coco_ann["bbox"] = ann.xywh_coords
        coco_ann["confidence"] = ann.confidence
    elif isinstance(ann, CompressedRLE):
        coco_ann["pixano_segmentation_id"] = ann.id
        coco_ann["segmentation"] = ann.to_polygons()
        coco_ann["area"] = ann.area
    return coco_ann
