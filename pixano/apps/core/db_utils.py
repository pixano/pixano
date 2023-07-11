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

from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from fastapi_pagination.api import create_page, resolve_params
from fastapi_pagination.bases import AbstractPage, AbstractParams
from pydantic import BaseModel

from pixano import transforms
from pixano.core import arrow_types
from pixano.transforms import natural_key, urle_to_bbox, urle_to_rle


class Feature(BaseModel):
    """Feature

    Attributes:
        name (str): Feature name
        dtype (str): Feature dtype
        value (Any): Feature value
    """

    name: str
    dtype: str
    value: Any


Features = list[Feature]


def get_item_details(
    dataset: ds.Dataset,
    item_id: str,
    media_dir: Path,
    inf_datasets: list[ds.Dataset] = [],
) -> dict:
    """Get item details

    Args:
        dataset (ds.Dataset): Dataset
        item_id (str): Selected item ID
        media_dir (Path): Dataset media directory
        inf_datasets (list[ds.Dataset], optional): List of inference datasets. Defaults to [].

    Returns:
        dict: ImageDetails features for UI
    """

    # Get item
    scanner = dataset.scanner(filter=ds.field("id").isin([item_id]))
    item = scanner.to_table().to_pylist()[0]

    # Get item inference objects
    for inf_ds in inf_datasets:
        inf_scanner = inf_ds.scanner(filter=ds.field("id").isin([item_id]))
        inf_item = inf_scanner.to_table().to_pylist()[0]
        if inf_item is not None:
            item["objects"].extend(inf_item["objects"])

    # Create features
    features = {
        "id": item["id"],
        "filename": None,
        "width": None,
        "height": None,
        "categoryStats": [],
        "views": {},
    }

    # Category statistics
    cat_ids = [obj["category_id"] for obj in item["objects"] if obj["category_id"]]
    cat_names = [obj["category_name"] for obj in item["objects"] if obj["category_id"]]
    cat, index, count = np.unique(cat_ids, return_index=True, return_counts=True)
    # Add to features
    features["categoryStats"] = [
        {
            "id": int(cat[i]),
            "name": str(cat_names[index[i]]),
            "count": int(count[i]),
        }
        for i in range(len(cat))
        if cat[i] is not None
    ]

    # Views
    for field in dataset.schema:
        if arrow_types.is_image_type(field.type):
            # Image
            image = item[field.name]
            image.uri_prefix = media_dir.absolute().as_uri()

            # Objects IDs
            ids = [obj["id"] for obj in item["objects"] if obj["view_id"] == field.name]
            # Categories
            cats = [
                {"id": obj["category_id"], "name": obj["category_name"]}
                for obj in item["objects"]
                if obj["view_id"] == field.name
                and obj["category_id"] is not None
                and obj["category_name"] is not None
            ]
            # Bounding boxes
            boxes = [
                transforms.format_bbox(
                    obj["bbox"],
                    obj["bbox_confidence"] is not None,
                    obj["bbox_confidence"],
                )
                for obj in item["objects"]
                if obj["view_id"] == field.name and obj["bbox"] is not None
            ]
            # Masks
            masks = [
                transforms.rle_to_urle(obj["mask"])
                for obj in item["objects"]
                if obj["view_id"] == field.name and obj["mask"] is not None
            ]
            # Add to features
            features["views"][field.name] = {
                "image": image.url,
                "objects": {
                    "id": ids,
                    "category": cats,
                    "boundingBox": boxes,
                    "segmentation": masks,
                },
            }

    return features


def get_items(dataset: ds.Dataset, params: AbstractParams = None) -> AbstractPage:
    """Get items

    Args:
        dataset (pa.Dataset): Dataset
        params (AbstractParams, optional): FastAPI params for pagination. Defaults to None.

    Returns:
        AbstractPage: List of Features for UI (DatasetExplorer)
    """

    # Get page parameters
    params = resolve_params(params)
    raw_params = params.to_raw_params()
    total = dataset.count_rows()

    # Get page items
    start = raw_params.offset
    stop = min(raw_params.offset + raw_params.limit, total)
    if start >= stop:
        return None
    items_table = dataset.take(range(start, stop))

    def _create_features(row: list) -> list[Feature]:
        """Create features based on field types

        Args:
            row (list): Input row

        Returns:
            list[Feature]: Row as list of features
        """

        features = []

        # Iterate on fields
        for field in dataset.schema:
            # Number fields
            if arrow_types.is_number(field.type):
                features.append(
                    Feature(name=field.name, dtype="number", value=row[field.name])
                )
            # Image fields
            elif arrow_types.is_image_type(field.type):
                thumbnail = row[field.name].preview_url
                features.append(
                    Feature(name=field.name, dtype="image", value=thumbnail)
                )
            # String fields
            elif pa.types.is_string(field.type):
                features.append(
                    Feature(name=field.name, dtype="text", value=row[field.name])
                )

        return features

    # Create items features
    items = [_create_features(e) for e in items_table.to_pylist()]

    return create_page(items, total=total, params=params)


def get_item_view_embedding(emb_ds: ds.Dataset, item_id: str, view: str) -> bytes:
    """Get item embedding for a view

    Args:
        emb_ds (ds.Dataset): Embedding dataset
        item_id (str): Item ID
        view (str): Item embedding view

    Returns:
        bytes: Embedding in base 64
    """

    # Get item
    emb_scanner = emb_ds.scanner(filter=ds.field("id").isin([item_id]))
    emb_item = emb_scanner.to_table().to_pylist()[0]
    return emb_item[f"{view}_embedding"]


def update_annotations(
    dataset_dir: Path,
    item_id: str,
    annotations: list[arrow_types.ObjectAnnotation],
):
    """Update dataset annotations

    Args:
        dataset_dir (Path): Dataset directory
        item_id (str): Item ID
        annotations (list[arrow_types.ObjectAnnotation]): Item annotations
    """

    # Convert URLE to RLE and add bounding box
    # TODO: Find a fix for image datasets
    item_anns = [o.dict() for o in annotations]
    for ann in item_anns:
        ann["bbox"] = urle_to_bbox(ann["mask"])
        ann["bbox_source"] = ann["mask_source"]
        ann["mask"] = urle_to_rle(ann["mask"])

    # Dataset files
    files = (dataset_dir / "db").glob("**/*.parquet")
    files = sorted(files, key=lambda x: natural_key(x.name))

    # Iterate on dataset files
    for file in files:
        # Look for updated item
        table = pq.read_table(file)
        filter = table.filter(pc.field("id").isin([item_id]))
        item = filter.to_pylist()

        # If item found
        if item != []:
            # Read table without item
            updated_table = table.filter(~pc.field("id").isin([item_id])).to_pydict()

            # Add item with updated annotations
            item[0]["objects"] = item_anns
            for field in table.schema:
                updated_table[field.name].append(item[0][field.name])

            # Sort table fields according to IDs
            for field in table.schema:
                if field.name != "id":
                    updated_table[field.name] = [
                        x
                        for _, x in sorted(
                            zip(updated_table["id"], updated_table[field.name]),
                            key=lambda pair: natural_key(pair[0]),
                        )
                    ]
            # Sort table IDs
            updated_table["id"] = sorted(updated_table["id"], key=natural_key)

            # Convert ExtensionTypes
            arrays = []
            for field in table.schema:
                # Convert image types to dict before PyArrow conversion
                # TODO: find a better way
                if arrow_types.is_image_type(field.type):
                    updated_table[field.name] = [
                        i.to_dict() for i in updated_table[field.name]
                    ]
                arrays.append(
                    arrow_types.convert_field(
                        field_name=field.name,
                        field_type=field.type,
                        field_data=updated_table[field.name],
                    )
                )

            # Save updated table
            pq.write_table(
                pa.Table.from_arrays(arrays, schema=table.schema),
                file,
            )
            return
