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
import json

import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds
from fastapi_pagination.api import create_page, resolve_params
from fastapi_pagination.bases import AbstractPage, AbstractParams

from pixano import transforms
from pixano.core import arrow_types
from pixano.data import models


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
    cat_ids = [obj["category_id"] for obj in item["objects"]]
    cat_names = [obj["category_name"] for obj in item["objects"]]
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
        AbstractPage: List of models.Feature for UI (DatasetExplorer)
    """

    # Get page parameters
    params = resolve_params(params)
    raw_params = params.to_raw_params()
    total = dataset.count_rows()

    # Get page items
    start = raw_params.offset
    stop = min(raw_params.offset + raw_params.limit, total)
    items_table = dataset.take(range(start, stop))

    def _create_features(row: list) -> list[models.Feature]:
        """Create features based on field types

        Args:
            row (list): Input row

        Returns:
            list[models.Feature]: Row as list of features
        """

        features = []

        # Iterate on fields
        for field in dataset.schema:
            # Number fields
            if arrow_types.is_number(field.type):
                features.append(
                    models.Feature(
                        name=field.name, dtype="number", value=row[field.name]
                    )
                )
            # Image fields
            elif arrow_types.is_image_type(field.type):
                thumbnail = row[field.name].preview_url
                features.append(
                    models.Feature(name=field.name, dtype="image", value=thumbnail)
                )
            # String fields
            elif pa.types.is_string(field.type):
                features.append(
                    models.Feature(name=field.name, dtype="text", value=row[field.name])
                )

        return features

    # Create items features
    items = [_create_features(e) for e in items_table.to_pylist()]

    return create_page(items=items, total=total, params=params)


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


def write_newAnnsJson(
    ds_id: str,
    item_id: str,
    view: str,
    annotations: list[arrow_types.ObjectAnnotation],
    target_dir: Path,
):
    # Build output json object
    # ObjectAnnotation is not (right now) serializable, and we need some more info into output
    output = {"dataset_id": ds_id, "view": view, "item_id": item_id, "objects": []}
    for ann in annotations:
        obj = ann.dict()
        output["objects"].append(obj)

    json_output = json.dumps(output)
    with open(target_dir / f"newAnnotations-{view}-{item_id}.json", "w") as jsonfile:
        jsonfile.write(json_output)


def write_newAnnotations(
    ds_id: str,
    item_id: str,
    view: str,
    annotations: list[arrow_types.ObjectAnnotation],
    target_dir: Path,
):
    # TMP log to ensure we get data
    print("EXPORT (dataset item view):", ds_id, item_id, view)
    for ann in annotations:
        print(
            "ANN (category id mask_counts_length):",
            ann.category_name,
            ann.id,
            len(ann.mask["counts"]),
        )

    # TMP Save as JSON
    write_newAnnsJson(ds_id, item_id, view, annotations, target_dir)

    """  Erreur format Pydantic non reconnu...
    schema = pa.schema([
        pa.field("objects", pa.list_(arrow_types.ObjectAnnotationType()))
    ])
    # Convert annotations field to PyArrow format (objects)
    arrays = [
        arrow_types.convert_field(
            field_name="objects",
            field_type=pa.list_(arrow_types.ObjectAnnotationType()),
            field_data=annotations
        )
    ]
    # Save to file
    ds.write_dataset(
        data=pa.Table.from_arrays(arrays, schema=schema),
        base_dir=target_dir / "db_newAnnotations",
        basename_template=f"newAnns-part-{{i}}.parquet",
        format="parquet",
        existing_data_behavior="overwrite_or_ignore"
    )
    """
