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
from typing import Any

import duckdb
import lance
import lancedb
import pyarrow as pa
from fastapi_pagination.api import create_page, resolve_params
from fastapi_pagination.bases import AbstractPage, AbstractParams
from pydantic import BaseModel

from pixano.core import (
    BBox,
    CompressedRLE,
    Image,
    is_number,
    is_string,
)
from pixano.data import Dataset
from pixano.utils import format_bbox, rle_to_mask


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


def _create_features(item: dict, schema: pa.schema) -> list[ItemFeature]:
    """Create features based on field types

    Args:
        item (dict): Dataset item
        schema (pa.schema): Dataset schema

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
        elif field.name in item["views"]:
            if isinstance(item[field.name], dict):
                item[field.name] = Image.from_dict(item[field.name])
            thumbnail = item[field.name].preview_url
            features.append(
                ItemFeature(name=field.name, dtype="image", value=thumbnail)
            )
        # String fields
        elif is_string(field.type):
            features.append(
                ItemFeature(name=field.name, dtype="text", value=item[field.name])
            )

    return features


def load_items(dataset: Dataset, params: AbstractParams = None) -> AbstractPage:
    """Load dataset items

    Args:
        dataset (Dataset): Dataset
        params (AbstractParams, optional): FastAPI params for pagination. Defaults to None.

    Returns:
        AbstractPage: List of ItemFeatures for UI (DatasetExplorer)
    """

    # Load dataset
    ds = dataset.connect()
    main_table: lancedb.db.LanceTable = ds.open_table("db")

    media_tables: dict[str, lancedb.db.LanceTable] = {}
    if "media" in dataset.info.tables:
        for md_info in dataset.info.tables["media"]:
            media_tables[md_info["name"]] = ds.open_table(md_info["name"])

    al_tables: list[lancedb.db.LanceTable] = []
    if "active_learning" in dataset.info.tables:
        for al_info in dataset.info.tables["active_learning"]:
            al_tables.append(ds.open_table(al_info["name"]))

    # Get page parameters
    params = resolve_params(params)
    raw_params = params.to_raw_params()
    total = main_table.to_lance().count_rows()

    # Get page items
    start = raw_params.offset
    stop = min(raw_params.offset + raw_params.limit, total)
    if start >= stop:
        return None

    ## For Active Learning
    if len(al_tables) > 0:
        # Selecting first active learning table
        al_table = al_tables[0].to_lance()
        pyarrow_table = duckdb.query(
            f"SELECT * FROM al_table ORDER BY round DESC LIMIT {raw_params.limit} OFFSET {raw_params.offset}"
        ).to_arrow_table()
        table_id_list = pyarrow_table["id"].to_pylist()
        table_ids = "'" + "', '".join(table_id_list) + "'"

        # Main table
        pyarrow_main_table = (
            main_table.to_lance().scanner(filter=f"id in ({table_ids})").to_table()
        )
        pyarrow_table = duckdb.query(
            "SELECT * FROM pyarrow_table LEFT JOIN pyarrow_main_table USING (id) ORDER BY round DESC"
        ).to_arrow_table()

        # Media tables
        for media_table in media_tables.values():
            pyarrow_media_table = (
                media_table.to_lance().scanner(filter=f"id in ({table_ids})").to_table()
            )
            pyarrow_table = duckdb.query(
                "SELECT * FROM pyarrow_table LEFT JOIN pyarrow_media_table USING (id) ORDER BY round DESC"
            ).to_arrow_table()

    ## Else
    else:
        # Main table
        pyarrow_table = main_table.to_lance().to_table(
            limit=raw_params.limit, offset=raw_params.offset
        )

        # Media tables
        for media_table in media_tables.values():
            pyarrow_media_table = media_table.to_lance().to_table(
                limit=raw_params.limit, offset=raw_params.offset
            )
            pyarrow_table = duckdb.query(
                "SELECT * FROM pyarrow_table LEFT JOIN pyarrow_media_table USING (id) ORDER BY id"
            ).to_arrow_table()

        # Active Learning tables
        for al_table in al_tables:
            pyarrow_al_table = al_table.to_lance().to_table(
                limit=raw_params.limit, offset=raw_params.offset
            )
            pyarrow_table = duckdb.query(
                "SELECT * FROM pyarrow_table LEFT JOIN pyarrow_al_table USING (id) ORDER BY id"
            ).to_arrow_table()

    # Create items features
    items = [
        _create_features(item, pyarrow_table.schema)
        for item in pyarrow_table.to_pylist()
    ]

    return create_page(items, total=total, params=params)


def load_item_details(dataset: Dataset, item_id: str) -> dict:
    """Load dataset item details

    Args:
        dataset (Dataset): Dataset
        item_id (str): Selected item ID

    Returns:
        dict: ImageDetails features for UI
    """

    # Load dataset
    ds = dataset.connect()
    main_table: lancedb.db.LanceTable = ds.open_table("db")

    media_tables: dict[str, lancedb.db.LanceTable] = {}
    if "media" in dataset.info.tables:
        for md_info in dataset.info.tables["media"]:
            media_tables[md_info["name"]] = ds.open_table(md_info["name"])

    obj_tables: dict[str, lancedb.db.LanceTable] = {}
    if "objects" in dataset.info.tables:
        for obj_info in dataset.info.tables["objects"]:
            obj_tables[obj_info["source"]] = ds.open_table(obj_info["name"])

    al_tables: dict[str, lancedb.db.LanceTable] = {}
    if "active_learning" in dataset.info.tables:
        for al_info in dataset.info.tables["active_learning"]:
            al_tables[al_info["source"]] = ds.open_table(al_info["name"])

    # Get item
    main_scanner = main_table.to_lance().scanner(filter=f"id in ('{item_id}')")
    pyarrow_item = main_scanner.to_table()

    for media_table in media_tables.values():
        media_scanner = media_table.to_lance().scanner(filter=f"id in ('{item_id}')")
        media_pyarrow_item = media_scanner.to_table()
        pyarrow_item = duckdb.query(
            "SELECT * FROM pyarrow_item LEFT JOIN media_pyarrow_item USING (id)"
        ).to_arrow_table()

    for al_table in al_tables.values():
        al_scanner = al_table.to_lance().scanner(filter=f"id in ('{item_id}')")
        al_pyarrow_item = al_scanner.to_table()
        pyarrow_item = duckdb.query(
            "SELECT * FROM pyarrow_item LEFT JOIN al_pyarrow_item USING (id)"
        ).to_arrow_table()

    item = pyarrow_item.to_pylist()[0]

    # Get item objects
    objects = {}
    for obj_source, obj_table in obj_tables.items():
        media_scanner = obj_table.to_lance().scanner(filter=f"item_id in ('{item_id}')")
        objects[obj_source] = media_scanner.to_table().to_pylist()

    # Create features
    item_details = {
        "itemData": {
            "id": item["id"],
            "views": defaultdict(dict),
            "features": _create_features(item, pyarrow_item.schema),
        },
        "itemObjects": defaultdict(lambda: defaultdict(list)),
    }

    # Iterate on view
    for field in pyarrow_item.schema:
        if field.name in item["views"]:
            if isinstance(item[field.name], dict):
                item[field.name] = Image.from_dict(item[field.name])
            image = item[field.name]
            image.uri_prefix = dataset.media_dir.absolute().as_uri()
            item_details["itemData"]["views"][field.name] = {
                "id": field.name,
                "url": image.url,
                "height": image.size[1],
                "width": image.size[0],
            }

            for obj_source, obj_list in objects.items():
                for obj in obj_list:
                    # If object in view
                    if obj["view_id"] == field.name:
                        # Object ID
                        id = obj["id"]
                        # Object mask
                        mask = obj["mask"].to_urle() if "mask" in obj else None
                        # Object bounding box
                        bbox = (
                            format_bbox(
                                obj["bbox"].coords,
                                obj["bbox"].confidence,
                            )
                            if "bbox" in obj
                            else None
                        )
                        # Object category
                        category = (
                            {"id": obj["category_id"], "name": obj["category_name"]}
                            if "category_id" in obj and "category_name" in obj
                            else None
                        )
                        # Add object
                        item_details["itemObjects"][obj_source][field.name].append(
                            {
                                "id": id,
                                "mask": mask,
                                "bbox": bbox,
                                "category": category,
                            }
                        )

    return item_details


def load_item_embeddings(dataset: Dataset, item_id: str) -> dict:
    """Load dataset item embeddings

    Args:
        dataset (Dataset): Dataset
        item_id (str): Selected item ID

    Returns:
        dict: Item embeddings
    """

    # Load dataset
    ds = dataset.connect()
    main_table: lance.LanceDataset = ds.open_table("db").to_lance()

    # TODO: load item embeddings for all views


def save_item_details(
    dataset: Dataset,
    item_id: str,
    item_details: dict[str, list],
):
    """Save dataset item objects

    Args:
        dataset (Dataset): Dataset
        item_id (str): Selected item ID
        item_details (dict[str, list]): Item details
    """

    # Load dataset
    ds = dataset.connect()

    main_table: lancedb.db.LanceTable = ds.open_table("db")

    obj_tables: dict[str, lancedb.db.LanceTable] = {}
    if "objects" in dataset.info.tables:
        for obj_info in dataset.info.tables["objects"]:
            obj_tables[obj_info["source"]] = ds.open_table(obj_info["name"])

    al_tables: dict[str, lancedb.db.LanceTable] = {}
    if "active_learning" in dataset.info.tables:
        for al_info in dataset.info.tables["active_learning"]:
            al_tables[al_info["source"]] = ds.open_table(al_info["name"])

    ### Save item features (classification)

    features = item_details["itemData"]

    # Classification
    for feature in features:
        if feature["name"] == "label":
            # If classification label in main table
            if "label" in main_table.schema.names:
                scanner = main_table.to_lance().scanner(filter=f"id in ('{item_id}')")
                item = scanner.to_table().to_pylist()[0]
                item["label"] = feature["value"]
                main_table.update(f"id in ('{item_id}')", item)
            # If classification label in active learning table
            else:
                for al_table in al_tables.values():
                    if "label" in al_table.schema.names:
                        scanner = al_table.to_lance().scanner(
                            filter=f"id in ('{item_id}')"
                        )
                        item = scanner.to_table().to_pylist()[0]
                        item["label"] = feature["value"]
                        al_table.update(f"id in ('{item_id}')", item)

    ### Save item objects

    # Convert objects
    for obj in item_details["itemObjects"]:
        # Convert mask from URLE to RLE
        if "mask" in obj:
            obj["mask"] = CompressedRLE.from_urle(obj["mask"]).to_dict()
            # If empty bounding box, convert from mask
            if "bbox" in obj and obj["bbox"]["coords"] == [0.0, 0.0, 0.0, 0.0]:
                obj["bbox"] = BBox.from_mask(rle_to_mask(obj["mask"])).to_dict()

    # Get current item objects
    current_objects = {}
    for obj_source, obj_table in obj_tables.items():
        media_scanner = obj_table.to_lance().scanner(filter=f"item_id in ('{item_id}')")
        current_objects[obj_source] = media_scanner.to_table().to_pylist()

    # Save or update new item objects
    for obj in item_details["itemObjects"]:
        source = obj["source_id"]
        # If objects table exists
        if source in obj_tables:
            # Remove keys not in schema (mostly for removing source_id for now)
            for key in list(obj):
                if key not in obj_tables[source].schema.names:
                    obj.pop(key)
            # Look for existing object
            scanner = (
                obj_tables[source].to_lance().scanner(filter=f"id in ('{obj['id']}')")
            )
            pyarrow_obj = scanner.to_table()
            # If object exists
            if pyarrow_obj.num_rows > 0:
                obj_tables[source].update(f"id in ('{obj['id']}')", obj)
            # If object does not exists
            else:
                obj_tables[source].add(obj)

            # Clear change history to prevent dataset from becoming too large
            obj_tables[source].to_lance().cleanup_old_versions()

        # If objects table does not exist
        else:
            # TODO: create objects table for new source
            pass

    # Delete removed item objects
    for obj_source, cur_objects in current_objects.items():
        for cur_obj in cur_objects:
            # If object has been deleted
            if not any(
                obj["id"] == cur_obj["id"] for obj in item_details["itemObjects"]
            ):
                # Remove object from table
                obj_tables[obj_source].delete(f"id in ('{cur_obj['id']}')")
