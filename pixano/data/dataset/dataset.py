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
from typing import Optional

import duckdb
import lancedb
import pyarrow as pa
import pyarrow.dataset as pa_ds
from pydantic import BaseModel

from pixano.core import Image
from pixano.data.dataset.dataset_info import DatasetInfo
from pixano.data.dataset.dataset_item import DatasetItem
from pixano.data.dataset.dataset_stat import DatasetStat
from pixano.data.fields import Fields


class Dataset(BaseModel):
    """Dataset

    Attributes:
        path (Path): Dataset path
        info (DatasetInfo, optional): Dataset info
        stats (list[DatasetStat], optional): Dataset stats
        thumbnail (str, optional): Dataset thumbnail base 64 URL
    """

    path: Path
    info: Optional[DatasetInfo] = None
    stats: Optional[list[DatasetStat]] = None
    thumbnail: Optional[str] = None

    def __init__(
        self,
        path: Path,
    ):
        """Initialize dataset

        Args:
            path (Path): Dataset path
        """

        info_file = path / "db.json"
        stats_file = path / "stats.json"
        thumb_file = path / "preview.png"

        # Define public attributes through Pydantic BaseModel
        super().__init__(
            path=path,
            info=DatasetInfo.from_json(info_file),
            stats=DatasetStat.from_json(stats_file) if stats_file.is_file() else None,
            thumbnail=Image(uri=thumb_file.absolute().as_uri()).url
            if thumb_file.is_file()
            else None,
        )

    @property
    def media_dir(self) -> Path:
        """Return dataset media directory

        Returns:
            Path: Dataset media directory
        """

        return self.path / "media"

    @property
    def num_rows(self) -> int:
        """Return number of rows in dataset

        Returns:
            int: Number of rows
        """

        ds = self.connect()

        # Return number of rows of main table
        return len(ds.open_table("db"))

    def load_info(
        self,
        load_stats: bool = False,
        load_thumbnail: bool = False,
    ) -> DatasetInfo:
        """Return dataset info with thumbnail and stats inside

        Args:
            load_stats (bool, optional): Load dataset stats. Defaults to False.
            load_thumbnail (bool, optional): Load dataset thumbnail. Defaults to False.

        Returns:
            DatasetInfo: Dataset info
        """

        return DatasetInfo.from_json(
            self.path / "db.json",
            load_stats=load_stats,
            load_thumbnail=load_thumbnail,
        )

    def save_info(self):
        """Save updated dataset info"""

        self.info.save(self.path)

    def connect(self) -> lancedb.DBConnection:
        """Connect to dataset with LanceDB

        Returns:
            lancedb.DBConnection: Dataset LanceDB connection
        """

        return lancedb.connect(self.path)

    def open_tables(self) -> dict[str, dict[str, lancedb.db.LanceTable]]:
        """Open dataset tables with LanceDB

        Returns:
            dict[str, dict[str, lancedb.db.LanceTable]]: Dataset tables
        """

        ds = self.connect()

        ds_tables: dict[str, dict[str, lancedb.db.LanceTable]] = defaultdict(dict)

        # Open main table
        ds_tables["main"]["db"] = ds.open_table("db")

        # Open media tables
        if "media" in self.info.tables:
            for table in self.info.tables["media"]:
                ds_tables["media"][table.name] = ds.open_table(table.name)

        # Open objects tables
        if "objects" in self.info.tables:
            for table in self.info.tables["objects"]:
                try:
                    ds_tables["objects"][table.source] = ds.open_table(table.name)
                except FileNotFoundError:
                    # Remove missing objects tables from DatasetInfo
                    self.info.tables["objects"].remove(table)
                    self.save_info()

        # Open active learning tables
        if "active_learning" in self.info.tables:
            for table in self.info.tables["active_learning"]:
                try:
                    ds_tables["active_learning"][table.source] = ds.open_table(
                        table.name
                    )
                except FileNotFoundError:
                    # Remove missing Active Learning tables from DatasetInfo
                    self.info.tables["active_learning"].remove(table)
                    self.save_info()

        # Open embeddings tables
        if "embeddings" in self.info.tables:
            for table in self.info.tables["embeddings"]:
                try:
                    ds_tables["embeddings"][table.source] = ds.open_table(table.name)
                except FileNotFoundError:
                    # Remove missing embeddings tables from DatasetInfo
                    self.info.tables["embeddings"].remove(table)
                    self.save_info()

        return ds_tables

    def load_items(
        self,
        limit: int,
        offset: int,
        load_active_learning: bool = True,
    ) -> list[DatasetItem]:
        """Load dataset items in selected tables

        Args:
            limit (int): Items limit
            offset (int): Items offset
            load_active_learning (bool, optional): Load item active learning info. Defaults to True.
        Returns:
            list[DatasetItem]: List of dataset items
        """

        # Update info in case of change
        self.info = self.load_info()

        # Load tables
        ds_tables = self.open_tables()

        # Load PyArrow items from tables
        pyarrow_items: dict[str, dict[str, pa.Table]] = defaultdict(dict)

        # Load PyArrow items from main table
        lance_table = ds_tables["main"]["db"].to_lance()
        pyarrow_items["main"]["db"] = duckdb.query(
            f"SELECT * FROM lance_table ORDER BY len(id), id LIMIT {limit} OFFSET {offset}"
        ).to_arrow_table()

        # Media tables
        for media_source, media_table in ds_tables["media"].items():
            lance_table = media_table.to_lance()
            pyarrow_items["media"][media_source] = duckdb.query(
                f"SELECT * FROM lance_table ORDER BY len(id), id LIMIT {limit} OFFSET {offset}"
            ).to_arrow_table()

        # Active Learning tables
        if load_active_learning:
            for al_source, al_table in ds_tables["active_learning"].items():
                lance_table = al_table.to_lance()
                pyarrow_items["active_learning"][al_source] = duckdb.query(
                    f"SELECT * FROM lance_table ORDER BY len(id), id LIMIT {limit} OFFSET {offset}"
                ).to_arrow_table()

        if pyarrow_items["main"]["db"].num_rows > 0:
            # Split results
            pyarrow_item_list: list[dict[str, dict[str, pa.Table]]] = []
            for index in range(pyarrow_items["main"]["db"].num_rows):
                pyarrow_item_list.append(defaultdict(dict))
                # Main table
                pyarrow_item_list[index]["main"]["db"] = pyarrow_items["main"][
                    "db"
                ].take([index])
                item_id = pyarrow_item_list[index]["main"]["db"].to_pylist()[0]["id"]
                # Media tables
                for media_source in ds_tables["media"].keys():
                    pyarrow_item_list[index]["media"][media_source] = (
                        pa_ds.dataset(pyarrow_items["media"][media_source])
                        .scanner(filter=pa_ds.field("id") == item_id)
                        .to_table()
                    )
                # Active Learning tables
                if load_active_learning:
                    for al_source in ds_tables["active_learning"].keys():
                        pyarrow_item_list[index]["active_learning"][al_source] = (
                            pa_ds.dataset(pyarrow_items["active_learning"][al_source])
                            .scanner(filter=pa_ds.field("id") == item_id)
                            .to_table()
                        )
            return [
                DatasetItem.from_pyarrow(pyarrow_item, self.info, self.media_dir)
                for pyarrow_item in pyarrow_item_list
            ]
        else:
            return None

    def search_items(
        self,
        limit: int,
        offset: int,
        query: dict[str, str],
        load_active_learning: bool = True,
    ):
        """Search for dataset items in selected tables

        Args:
            limit (int): Items limit
            offset (int): Items offset
            query (dict[str, str]): Search query
            load_active_learning (bool, optional): Load item active learning info. Defaults to True.
        Returns:
            list[DatasetItem]: List of dataset items
        """

        # Update info in case of change
        self.info = self.load_info()

        # Load tables
        ds_tables = self.open_tables()

        # Load PyArrow items from tables
        pyarrow_items: dict[str, dict[str, pa.Table]] = defaultdict(dict)

        if "embeddings" not in self.info.tables:
            return None

        for table in self.info.tables["embeddings"]:
            if table.type == "search" and table.source == query["model"]:
                sem_search_table = ds_tables["embeddings"][table.source]
                sem_search_views = [
                    field_name
                    for field_name, field_type in table.fields.items()
                    if field_type == "vector(512)"
                ]
                # Initialize CLIP model
                try:
                    from pixano_inference.transformers import CLIP
                except ImportError as e:
                    raise ImportError(
                        "Please install the pixano-inference module to perform semantic search with CLIP"
                    ) from e

                model = CLIP()
                model_query = model.semantic_search(query["search"])

                # Perform semantic search
                stop = min(offset + limit, self.num_rows)
                results_table = (
                    sem_search_table.search(model_query, sem_search_views[0])
                    .limit(stop)
                    .to_arrow()
                )

                # If more than one view, search on all views and select the best results based on distance
                if len(sem_search_views) > 1:
                    for view in sem_search_views[1:]:
                        view_results_table = (
                            sem_search_table.search(model_query, view)
                            .limit(stop)
                            .to_arrow()
                        )
                        results_table = duckdb.query(
                            "SELECT id, results_table._distance as distance_1, view_results_table._distance as distance_2 FROM results_table LEFT JOIN view_results_table USING (id)"
                        ).to_arrow_table()

                        results_table = duckdb.query(
                            "SELECT (id), (SELECT Min(v) FROM (VALUES (distance_1), (distance_2)) AS value(v)) as _distance FROM results_table"
                        ).to_arrow_table()

                # Filter results to page
                results_table = duckdb.query(
                    f"SELECT id, _distance as distance FROM results_table ORDER BY _distance ASC LIMIT {limit} OFFSET {offset}"
                ).to_arrow_table()

                # Join with main table
                main_table = ds_tables["main"]["db"].to_lance()
                pyarrow_items["main"]["db"] = duckdb.query(
                    "SELECT * FROM results_table LEFT JOIN main_table USING (id) ORDER BY distance ASC"
                ).to_arrow_table()

                if pyarrow_items["main"]["db"].num_rows > 0:
                    # Split results
                    pyarrow_item_list: list[dict[str, dict[str, pa.Table]]] = []
                    for index in range(pyarrow_items["main"]["db"].num_rows):
                        pyarrow_item_list.append(defaultdict(dict))
                        # Main table
                        pyarrow_item_list[index]["main"]["db"] = pyarrow_items["main"][
                            "db"
                        ].take([index])
                        item_id = pyarrow_item_list[index]["main"]["db"].to_pylist()[0][
                            "id"
                        ]
                        # Media tables
                        for media_source, media_table in ds_tables["media"].items():
                            lance_scanner = media_table.to_lance().scanner(
                                filter=f"id in ('{item_id}')"
                            )
                            pyarrow_item_list[index]["media"][
                                media_source
                            ] = lance_scanner.to_table()

                        # Active learning tables
                        if load_active_learning:
                            for al_source, al_table in ds_tables[
                                "active_learning"
                            ].items():
                                lance_scanner = al_table.to_lance().scanner(
                                    filter=f"id in ('{item_id}')"
                                )
                                pyarrow_item_list[index]["active_learning"][
                                    al_source
                                ] = lance_scanner.to_table()

                    return [
                        DatasetItem.from_pyarrow(
                            pyarrow_item, self.info, self.media_dir
                        )
                        for pyarrow_item in pyarrow_item_list
                    ]
                else:
                    return None

    def load_item(
        self,
        item_id: str,
        load_media: bool = True,
        load_objects: bool = False,
        load_active_learning: bool = True,
        load_embeddings: bool = False,
        model_id: str = None,
    ) -> DatasetItem:
        """Find dataset item in selected tables

        Args:
            item_id (str): Dataset item ID
            load_media (bool, optional): Load item media. Defaults to True.
            load_objects (bool, optional): Load item objects. Defaults to False.
            load_active_learning (bool, optional): Load item active learning info. Defaults to True.
            load_embeddings (bool, optional): Load item embeddings. Defaults to False.
            model_id (str, optional): Model ID (ONNX file path) of embeddings to load. Defaults to None.
        Returns:
            DatasetItem: Dataset item
        """

        # Update info in case of change
        self.info = self.load_info()

        # Load tables
        ds_tables = self.open_tables()

        # Load PyArrow item from tables
        pyarrow_item: dict[str, dict[str, pa.Table]] = defaultdict(dict)

        # Load PyArrow item from main table
        lance_scanner = (
            ds_tables["main"]["db"].to_lance().scanner(filter=f"id in ('{item_id}')")
        )
        pyarrow_item["main"]["db"] = lance_scanner.to_table()

        # Load PyArrow item from media tables
        if load_media:
            for media_source, media_table in ds_tables["media"].items():
                lance_scanner = media_table.to_lance().scanner(
                    filter=f"id in ('{item_id}')"
                )
                pyarrow_item["media"][media_source] = lance_scanner.to_table()

        # Load PyArrow item from objects tables
        if load_objects:
            for obj_source, obj_table in ds_tables["objects"].items():
                lance_scanner = obj_table.to_lance().scanner(
                    filter=f"item_id in ('{item_id}')"
                )
                pyarrow_item["objects"][obj_source] = lance_scanner.to_table()

        # Load PyArrow item from active learning tables
        if load_active_learning:
            for al_source, al_table in ds_tables["active_learning"].items():
                lance_scanner = al_table.to_lance().scanner(
                    filter=f"id in ('{item_id}')"
                )
                pyarrow_item["active_learning"][al_source] = lance_scanner.to_table()

        # Load PyArrow item from segmentation embeddings tables
        found_embeddings = False if load_embeddings else True
        if load_embeddings:
            for emb_source, emb_table in ds_tables["embeddings"].items():
                if emb_source.lower() in model_id.lower():
                    found_embeddings = True
                    lance_scanner = emb_table.to_lance().scanner(
                        filter=f"id in ('{item_id}')"
                    )
                    pyarrow_item["embeddings"][emb_source] = lance_scanner.to_table()

        if pyarrow_item["main"]["db"].num_rows > 0 and found_embeddings:
            return DatasetItem.from_pyarrow(
                pyarrow_item,
                self.info,
                self.media_dir,
                model_id,
            )
        else:
            return None

    def save_item(self, item: DatasetItem):
        """Save dataset item features and objects

        Args:
            item (DatasetItem): Item to save
        """

        # Update info in case of change
        self.info = self.load_info()

        # Load dataset
        ds_tables = self.open_tables()

        # Save item label if it exists
        if "label" in item.features:
            # If label not in main table, add label field
            if "label" not in ds_tables["main"]["db"].schema.names:
                main_table_ds = ds_tables["main"]["db"].to_lance()
                # Create label table
                label_table = main_table_ds.to_table(columns=["id"])
                label_array = pa.array(
                    [""] * len(ds_tables["main"]["db"]), type=pa.string()
                )
                label_table = label_table.append_column(
                    pa.field("label", pa.string()), label_array
                )
                # Merge with main table
                main_table_ds.merge(label_table, "id")
                # Update DatasetInfo
                self.info.tables["main"][0].fields["label"] = "str"
                self.save_info()

            # Get item
            scanner = (
                ds_tables["main"]["db"]
                .to_lance()
                .scanner(filter=f"id in ('{item.id}')")
            )
            pyarrow_item = scanner.to_table().to_pylist()[0]
            # Update item
            pyarrow_item["label"] = item.features["label"].value
            ds_tables["main"]["db"].update(f"id in ('{item.id}')", pyarrow_item)

            # Clear change history to prevent dataset from becoming too large
            ds_tables["main"]["db"].to_lance().cleanup_old_versions()

        # Get current item objects
        current_obj_tables = {}
        for source, table in ds_tables["objects"].items():
            media_scanner = table.to_lance().scanner(filter=f"item_id in ('{item.id}')")
            current_obj_tables[source] = media_scanner.to_table().to_pylist()

        # Save or update new item objects
        for obj in item.objects.values():
            source = obj.source_id

            # If objects table exists
            if source in ds_tables["objects"].keys():
                # Remove keys not in schema
                pyarrow_obj = obj.to_pyarrow()
                for key in list(pyarrow_obj):
                    if key not in ds_tables["objects"][source].schema.names:
                        pyarrow_obj.pop(key)

                # Look for existing object
                scanner = (
                    ds_tables["objects"][source]
                    .to_lance()
                    .scanner(filter=f"id in ('{obj.id}')")
                )
                existing_obj = scanner.to_table()

                # If object exists
                if existing_obj.num_rows > 0:
                    ds_tables["objects"][source].update(
                        f"id in ('{obj.id}')", pyarrow_obj
                    )

                # If object does not exists
                else:
                    table_obj = pa.Table.from_pylist(
                        [pyarrow_obj],
                        schema=ds_tables["objects"][source].schema,
                    )
                    ds_tables["objects"][source].add(table_obj)

                # Clear change history to prevent dataset from becoming too large
                ds_tables["objects"][source].to_lance().cleanup_old_versions()

            # If objects table does not exist
            else:
                if source == "Pixano Annotator":
                    annnotator_fields = {
                        "id": "str",
                        "item_id": "str",
                        "view_id": "str",
                        "bbox": "bbox",
                        "mask": "compressedrle",
                        "category_id": "int",
                        "category_name": "str",
                    }
                    annotator_table = {
                        "name": "obj_annotator",
                        "source": source,
                        "fields": annnotator_fields,
                    }

                    # Create new objects table
                    ds = self.connect()
                    ds_tables["objects"][source] = ds.create_table(
                        "obj_annotator",
                        schema=Fields(annnotator_fields).to_schema(),
                        mode="overwrite",
                    )

                    # Add new objects table to DatasetInfo
                    if "objects" in self.info.tables:
                        self.info.tables["objects"].append(annotator_table)
                    else:
                        self.info.tables["objects"] = [annotator_table]
                    self.save_info()

                    # Remove keys not in schema
                    pyarrow_obj = obj.to_pyarrow()
                    for key in list(pyarrow_obj):
                        if key not in ds_tables["objects"][source].schema.names:
                            pyarrow_obj.pop(key)

                    # Add object
                    table_obj = pa.Table.from_pylist(
                        [pyarrow_obj],
                        schema=ds_tables["objects"][source].schema,
                    )
                    ds_tables["objects"][source].add(table_obj)

                    # Clear change history to prevent dataset from becoming too large
                    ds_tables["objects"][source].to_lance().cleanup_old_versions()

        # Delete removed item objects
        for obj_source, current_obj_table in current_obj_tables.items():
            for current_obj in current_obj_table:
                # If object has been deleted
                if not any(
                    obj_id == current_obj["id"] for obj_id in item.objects.keys()
                ):
                    # Remove object from table
                    ds_tables["objects"][obj_source].delete(
                        f"id in ('{current_obj['id']}')"
                    )

    @staticmethod
    def find(
        id: str,
        directory: Path,
    ) -> "Dataset":
        """Find Dataset in directory

        Args:
            id (str): Dataset ID
            directory (Path): Directory to search in

        Returns:
            Dataset: Dataset
        """

        # Browse directory
        for json_fp in directory.glob("*/db.json"):
            info = DatasetInfo.from_json(json_fp)
            if info.id == id:
                # Return dataset
                return Dataset(json_fp.parent)
