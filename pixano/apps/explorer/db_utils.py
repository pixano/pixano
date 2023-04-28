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

import duckdb
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
    item_id: int,
    media_dir: Path,
    infer_datasets: list[ds.Dataset] = [],
) -> dict:
    """Get item details

    Args:
        dataset (ds.Dataset): Dataset
        item_id (int): Selected item ID
        media_dir (Path): Dataset media path
        infer_datasets (list[ds.Dataset], optional): List of inference datasets. Defaults to [].

    Returns:
        dict: ImageDetails features for UI
    """
    schema = dataset.schema
    item = duckdb.query(f"SELECT * FROM dataset WHERE id={item_id}").fetchone()

    field_names = [f.name for f in schema]
    item_dict = dict(zip(field_names, item))

    # TMP info for cat_ids issue
    debug_0 = False
    if debug_0:
        print("GT", item_dict["id"], len(item_dict["objects"]))
        for item in item_dict["objects"]:
            print("---", item["category_name"], item["category_id"])

    # Inference Merge
    for infer_ds in infer_datasets:
        inf_schema = infer_ds.schema
        inf_item = duckdb.query(f"SELECT * FROM infer_ds WHERE id={item_id}").fetchone()
        if inf_item is not None:
            inf_field_names = [f.name for f in inf_schema]
            inf_item_dict = dict(zip(inf_field_names, inf_item))
            item_dict["objects"].extend(inf_item_dict["objects"])
            # TMP info for cat_ids issue
            if debug_0:
                print(
                    "INFER",
                    inf_item_dict["id"],
                    inf_item_dict["objects"][0]["bbox_source"],
                    len(inf_item_dict["objects"]),
                )
                for item in inf_item_dict["objects"]:
                    print("---", item["category_name"], item["category_id"])

    # TODO compute statically
    category_ids = [obj["category_id"] for obj in item_dict["objects"]]
    category_names = [obj["category_name"] for obj in item_dict["objects"]]
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
        "id": item_dict["id"],
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

    for f in schema:
        if arrow_types.is_image_type(f.type):
            bboxes = [
                _format_bbox(
                    obj["bbox"],
                    obj["bbox_confidence"] is not None,
                    obj["bbox_confidence"],
                )
                for obj in item_dict["objects"]
                if obj["view_id"] == f.name and obj["bbox"] is not None
            ]
            masks = [
                transforms.rle_to_polygons(obj["mask"])
                for obj in item_dict["objects"]
                if obj["view_id"] == f.name
            ]

            im = arrow_types.Image(**item_dict[f.name])
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

    items_table = duckdb.query(
        # HACK TO SELECT ONLY VAL FOR COCO
        # f"SELECT * from dataset WHERE split='val2017' OFFSET {raw_params.offset} LIMIT {raw_params.limit}"
        f"SELECT * from dataset OFFSET {raw_params.offset} LIMIT {raw_params.limit}"
    ).arrow()

    def _create_features(row: list) -> list[models.Feature]:
        features = []
        for field in schema:
            if arrow_types.is_number(field.type):
                features.append(
                    models.Feature(
                        name=field.name, dtype="number", value=row[field.name]
                    )
                )
            elif arrow_types.is_image_type(field.type):
                im = arrow_types.Image(**row[field.name])

                features.append(
                    models.Feature(name=field.name, dtype="image", value=im.preview_url)
                )
            # elif types.is_depth_map_type(field.type):
            #     features.append(
            #         models.Feature(
            #             name=field.name,
            #             dtype="image",
            #             value=row[field.name].display(size=128),
            #         )
            #     )
            elif pa.types.is_string(field.type):
                features.append(
                    models.Feature(name=field.name, dtype="text", value=row[field.name])
                )

        return features

    items = [_create_features(el) for el in items_table.to_pylist()]

    return create_page(items=items, total=total, params=params)
