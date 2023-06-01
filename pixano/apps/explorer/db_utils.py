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
    scanner = dataset.scanner(filter=ds.field("id").isin([item_id]))
    item = scanner.to_table().to_pylist()[0]

    # Inference Merge
    for inf_ds in inf_datasets:
        inf_scanner = inf_ds.scanner(filter=ds.field("id").isin([item_id]))
        inf_item = inf_scanner.to_table().to_pylist()[0]
        if inf_item is not None:
            item["objects"].extend(inf_item["objects"])

    # TODO compute statically
    category_ids = [obj["category_id"] for obj in item["objects"]]
    category_names = [obj["category_name"] for obj in item["objects"]]
    cat, index, count = np.unique(category_ids, return_index=True, return_counts=True)
    category_stats = [
        {
            "id": int(cat[i]),
            "name": str(category_names[index[i]]),
            "count": int(count[i]),
        }
        for i in range(len(cat))
    ]

    features = {
        "id": item["id"],
        "filename": None,
        "width": None,
        "height": None,
        "categoryStats": category_stats,
        "views": {},
    }

    def _format_bbox(bbox, is_predicted=False, confidence=None):
        return {
            "x": bbox[0],
            "y": bbox[1],
            "width": bbox[2],
            "height": bbox[3],
            "is_predict": is_predicted,
            "confidence": confidence,
        }

    schema = dataset.schema
    for f in schema:
        if arrow_types.is_image_type(f.type):
            bboxes = [
                _format_bbox(
                    obj["bbox"],
                    obj["bbox_confidence"] is not None,
                    obj["bbox_confidence"],
                )
                for obj in item["objects"]
                if obj["view_id"] == f.name and obj["bbox"] is not None
            ]
            masks = [
                transforms.rle_to_polygons(obj["mask"])
                for obj in item["objects"]
                if obj["view_id"] == f.name
            ]

            im = item[f.name]
            im.uri_prefix = media_dir

            features["views"][f.name] = {
                "image": im.url,
                "objects": {
                    "category": [
                        {"id": id, "name": name}
                        for (id, name) in zip(category_ids, category_names)
                    ],
                    "boundingBox": bboxes,
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

    params = resolve_params(params)
    raw_params = params.to_raw_params()

    total = dataset.count_rows()
    schema = dataset.schema

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
        for field in schema:
            if arrow_types.is_number(field.type):
                features.append(
                    models.Feature(
                        name=field.name, dtype="number", value=row[field.name]
                    )
                )
            elif arrow_types.is_image_type(field.type):
                thumbnail = row[field.name].preview_url
                features.append(
                    models.Feature(name=field.name, dtype="image", value=thumbnail)
                )
            elif pa.types.is_string(field.type):
                features.append(
                    models.Feature(name=field.name, dtype="text", value=row[field.name])
                )

        return features

    items = [_create_features(e) for e in items_table.to_pylist()]

    return create_page(items=items, total=total, params=params)
