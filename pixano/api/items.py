# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

from collections import defaultdict
from pathlib import Path
from typing import Any

import lance
import pyarrow as pa
import pyarrow.dataset as ds
from fastapi_pagination.api import create_page, resolve_params
from fastapi_pagination.bases import AbstractPage, AbstractParams
from pydantic import BaseModel

from pixano.core import (
    BBox,
    CompressedRLE,
    Image,
    ObjectAnnotation,
    is_image_type,
    is_list_of_object_annotation_type,
    is_number,
    pyarrow_array_from_list,
)
from pixano.data import Dataset, EmbeddingDataset, Fields, InferenceDataset
from pixano.utils import format_bbox


class ItemFeature(BaseModel):
    """Feature

    Attributes:
        name (str): Feature name
        dtype (str): Feature dtype
        value (Any): Feature value
    """

    name: str
    dtype: str
    value: Any


ItemFeatures = list[ItemFeature]


def _create_features(
    item: list, schema: pa.schema, fields: dict[str, str]
) -> list[ItemFeature]:
    """Create features based on field types

    Args:
        row (list): Dataset item
        schema (pa.schema): Dataset schema
        fields (dict[str, str]): Dataset fields

    Returns:
        list[ItemFeature]: Item as list of features
    """

    features = []

    # Iterate on fields
    for field in schema:
        # Number fields
        if is_number(field.type):
            features.append(
                ItemFeature(name=field.name, dtype="number", value=item[field.name])
            )
        # Image fields
        elif is_image_type(field.type) or fields[field.name] == "image":
            if isinstance(item[field.name], dict):
                item[field.name] = Image.from_dict(item[field.name])
            thumbnail = item[field.name].preview_url
            features.append(
                ItemFeature(name=field.name, dtype="image", value=thumbnail)
            )
        # String fields
        elif pa.types.is_string(field.type):
            features.append(
                ItemFeature(name=field.name, dtype="text", value=item[field.name])
            )

    return features


def load_items(dataset: Dataset, params: AbstractParams = None) -> AbstractPage:
    """Get items

    Args:
        dataset (Dataset): Dataset
        params (AbstractParams, optional): FastAPI params for pagination. Defaults to None.

    Returns:
        AbstractPage: List of ItemFeatures for UI (DatasetExplorer)
    """

    # Load dataset
    ds = dataset.connect()
    main_table: lance.LanceDataset = ds.open_table("db").to_lance()
    fields = dataset.info.fields.to_dict() if dataset.info.fields else defaultdict(str)

    # Get page parameters
    params = resolve_params(params)
    raw_params = params.to_raw_params()
    total = main_table.count_rows()

    # Get page items
    start = raw_params.offset
    stop = min(raw_params.offset + raw_params.limit, total)
    if start >= stop:
        return None
    items_table = main_table.to_table(limit=raw_params.limit, offset=raw_params.offset)

    # Create items features
    items = [
        _create_features(item, main_table.schema, fields)
        for item in items_table.to_pylist()
    ]

    return create_page(items, total=total, params=params)


def load_item_objects(
    dataset: Dataset,
    item_id: str,
    media_dir: Path,
    inf_datasets: list[InferenceDataset] = [],
) -> dict:
    """Get item details

    Args:
        dataset (Dataset): Dataset
        item_id (str): Selected item ID
        media_dir (Path): Dataset media directory
        inf_datasets (list[InferenceDataset], optional): List of inference datasets. Defaults to [].

    Returns:
        dict: ImageDetails features for UI
    """

    fields = dataset.info.fields.to_dict() if dataset.info.fields else defaultdict(str)

    # Load dataset
    selected_ds = dataset.load()

    # Get item
    scanner = selected_ds.scanner(filter=f"id in ('{item_id}')")
    item = scanner.to_table().to_pylist()[0]

    # Get objects
    objects = []
    for field_name, field_type in fields.items():
        if field_type == "[ObjectAnnotation]" and field_name in item:
            objects.extend(item[field_name])

    # Get item inference objects
    for inf_ds in inf_datasets:
        pa_inf_ds = inf_ds.load()
        inf_scanner = pa_inf_ds.scanner(filter=ds.field("id").isin([item_id]))
        inf_item = inf_scanner.to_table().to_pylist()[0]
        if inf_item is not None:
            for field in pa_inf_ds.schema:
                if field.name == "objects" or is_list_of_object_annotation_type(
                    field.type
                ):
                    objects.extend(inf_item[field.name])

    # Create features
    item_details = {
        "itemData": {
            "id": item["id"],
            "views": defaultdict(dict),
            "features": _create_features(item, selected_ds.schema, fields),
        },
        "itemObjects": defaultdict(lambda: defaultdict(list)),
    }

    # Iterate on view
    for field in selected_ds.schema:
        if is_image_type(field.type) or fields[field.name] == "image":
            image = item[field.name]
            image.uri_prefix = media_dir.absolute().as_uri()
            item_details["itemData"]["views"][field.name] = {
                "id": field.name,
                "url": image.url,
                "height": image.size[1],
                "width": image.size[0],
            }

            for obj in objects:
                # Support for previous ObjectAnnotation type
                if isinstance(obj, dict):
                    # Support for previous BBox type
                    if isinstance(obj["bbox"], list):
                        obj["bbox"] = {"coords": obj["bbox"], "format": "xywh"}
                    obj = ObjectAnnotation.from_dict(obj)
                # If object in view
                if obj.view_id == field.name:
                    # Object ID
                    id = obj.id
                    # Object mask
                    mask = obj.mask.to_urle() if obj.mask is not None else None
                    # Object bounding box
                    bbox = (
                        format_bbox(
                            obj.bbox.coords,
                            obj.bbox_confidence is not None,
                            obj.bbox_confidence,
                        )
                        if obj.bbox is not None
                        and obj.bbox.coords != [0.0, 0.0, 0.0, 0.0]
                        else None
                    )
                    # Object source
                    source = obj.mask_source or obj.bbox_source or "Ground truth"
                    # Object category
                    category = (
                        {"id": obj.category_id, "name": obj.category_name}
                        if obj.category_id is not None and obj.category_name is not None
                        else None
                    )
                    # Add object
                    item_details["itemObjects"][source][field.name].append(
                        {
                            "id": id,
                            "mask": mask,
                            "bbox": bbox,
                            "category": category,
                        }
                    )

    return item_details


def load_item_embeddings(emb_ds: EmbeddingDataset, item_id: str) -> bytes:
    """Get item embedding for a view

    Args:
        emb_ds (EmbeddingDataset): Embedding dataset
        item_id (str): Item ID

    Returns:
        bytes: Embedding in base 64
    """

    # TODO: load embeddings for all views
    view = "image"

    # Load dataset
    pa_emb_ds = emb_ds.load()

    # Get item
    emb_scanner = pa_emb_ds.scanner(filter=ds.field("id").isin([item_id]))
    emb_item = emb_scanner.to_table().to_pylist()[0]
    return emb_item[f"{view}_embedding"]


def save_item_objects(
    dataset: Dataset,
    item_id: str,
    annotations: list[ObjectAnnotation],
):
    """Update dataset annotations

    Args:
        dataset (Dataset): Dataset
        item_id (str): Item ID
        annotations (list[ObjectAnnotation]): Item annotations
    """

    # Convert URLE to RLE and add bounding box
    for ann in annotations:
        ann.mask = CompressedRLE.from_urle(ann.mask.to_dict())
        ann.bbox = (
            ann.bbox
            if ann.bbox.coords != [0.0, 0.0, 0.0, 0.0]
            else BBox.from_mask(ann.mask.to_mask())
        )

    # Load dataset
    selected_ds = dataset.load()
    fields = dataset.info.fields.to_dict()
    schema = pa.schema(dataset.info.fields.to_pyarrow())

    # Get item
    scanner = selected_ds.scanner(filter=f"id in ('{item_id}')")
    item = scanner.to_table().to_pylist()[0]
    objects_field_name = ""

    # Check if ObjectAnnotation field exists
    for field_name, field_type in fields.items():
        if field_type == "[ObjectAnnotation]" and objects_field_name == "":
            # ObjectAnnotation field exists
            objects_field_name = field_name
            # Add new annotations to item
            item[objects_field_name] = annotations

    # If ObjectAnnotation field not in fields
    if objects_field_name == "":
        objects_field_name = "objects"
        # Add new annotations to item
        item[objects_field_name] = annotations
        # Update fields
        fields[objects_field_name] = "[ObjectAnnotation]"
        dataset.info.fields = Fields.from_dict(fields)
        dataset.save_info()

    # If ObjectAnnotation field not in schema
    if objects_field_name not in selected_ds.schema.names:
        # TODO: Add ObjectAnnotation field to schema if missing
        raise Exception("Missing ObjectAnnotation field in dataset schema")

    # Create updated item
    updated_item_arrays = [
        pyarrow_array_from_list([item[field.name]], field.type) for field in schema
    ]
    updated_item = pa.RecordBatchReader.from_batches(
        selected_ds.schema,
        [
            pa.RecordBatch.from_struct_array(
                pa.StructArray.from_arrays(
                    updated_item_arrays,
                    fields=schema,
                )
            )
        ],
    )

    # Replace old item
    selected_ds.delete(f"id in ('{item_id}')")
    lance.write_dataset(updated_item, selected_ds.uri, mode="append")
