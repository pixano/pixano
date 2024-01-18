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
from pydantic import BaseModel, ConfigDict
from s3path import S3Path

from pixano.core import Image
from pixano.data.dataset.dataset_info import DatasetInfo
from pixano.data.dataset.dataset_item import DatasetItem
from pixano.data.dataset.dataset_stat import DatasetStat
from pixano.data.dataset.dataset_table import DatasetTable
from pixano.data.fields import Fields, field_to_pyarrow
from pixano.data.item.item_feature import ItemFeature


class Dataset(BaseModel):
    """Dataset

    Attributes:
        path (Path | S3Path): Dataset path
        info (DatasetInfo, optional): Dataset info
        stats (list[DatasetStat], optional): Dataset stats
        thumbnail (str, optional): Dataset thumbnail base 64 URL
    """

    path: Path | S3Path
    info: Optional[DatasetInfo] = None
    stats: Optional[list[DatasetStat]] = None
    thumbnail: Optional[str] = None
    # Allow arbitrary types because of S3 Path
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(
        self,
        path: Path | S3Path,
    ):
        """Initialize dataset

        Args:
            path (Path | S3Path): Dataset path
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
    def media_dir(self) -> Path | S3Path:
        """Return dataset media directory

        Returns:
            Path | S3Path: Dataset media directory
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

    @staticmethod
    def create(path: Path | S3Path, info: DatasetInfo) -> "Dataset":
        """Create dataset

        Args:
            path (Path | S3Path): Path to create dataset in
            info (DatasetInfo): Dataset info

        Returns:
            Dataset: Created dataset
        """

        # Create DatasetInfo file
        path.mkdir(parents=True, exist_ok=True)
        info.save(path)

        # Load dataset
        dataset = Dataset(path)

        # Create dataset tables
        for group_name, table_group in dataset.info.tables.items():
            for table in table_group:
                dataset.create_table(table, group_name, add_to_info=False)

        return dataset

    def connect(self) -> lancedb.db.DBConnection:
        """Connect to dataset with LanceDB

        Returns:
            lancedb.db.DBConnection: Dataset LanceDB connection
        """

        if isinstance(self.path, S3Path):
            return lancedb.connect(self.path.as_uri())
        return lancedb.connect(self.path)

    def open_tables(self) -> dict[str, dict[str, lancedb.db.LanceTable]]:
        """Open dataset tables with LanceDB

        Returns:
            dict[str, dict[str, lancedb.db.LanceTable]]: Dataset tables
        """

        ds = self.connect()

        ds_tables: dict[str, dict[str, lancedb.db.LanceTable]] = defaultdict(dict)

        for group_name, table_group in self.info.tables.items():
            for table in table_group:
                try:
                    ds_tables[group_name][table.name] = ds.open_table(table.name)
                except FileNotFoundError as e:
                    # If optional table, remove from DatasetInfo
                    if group_name in ["objects", "embeddings", "active_learning"]:
                        self.info.tables[group_name].remove(table)
                        self.save_info()
                    else:
                        raise FileNotFoundError from e

        return ds_tables

    def create_table(
        self,
        table: DatasetTable,
        table_group: str,
        add_to_info: bool = True,
    ):
        """Create a new table in the dataset

        Args:
            table (DatasetTable): Table to create
            table_group (str): Table group
            add_to_info (bool, optional): Add table to DatasetInfo. Defaults to True.
        """

        # Create Lance table
        ds = self.connect()
        # pylint: disable=unexpected-keyword-arg
        ds.create_table(
            table.name,
            schema=Fields(table.fields).to_schema(),
            mode="overwrite",
        )

        # Save table to DatasetInfo
        if add_to_info:
            if table_group in self.info.tables:
                self.info.tables[table_group].append(table)
            else:
                self.info.tables[table_group] = [table]
            self.save_info()

    def update_table(
        self,
        features: dict[str, ItemFeature],
        table: lancedb.db.LanceTable,
        table_group: str,
        table_name: str,
    ):
        """Update a table with new features

        Args:
            table (lancedb.db.LanceTable): Table to update
            features (dict[str, ItemFeature]): Features
            table_group (str): Table group
            table_name (str): Table name
        """

        if features is not None:
            new_feats = [
                feat
                for feat in features.values()
                if feat.name not in table.schema.names
            ]
            if len(new_feats) > 0:
                new_feats_table = table.to_lance().to_table(columns=["id"])
                # Create new feature columns
                for feat in new_feats:
                    # None is not supported for booleans yet (should be fixed in pylance 0.9.1)
                    feat_array = pa.array(
                        [False] * len(table)
                        if feat.dtype == "bool"
                        else [None] * len(table),
                        type=field_to_pyarrow(feat.dtype),
                    )
                    new_feats_table = new_feats_table.append_column(
                        pa.field(feat.name, field_to_pyarrow(feat.dtype)), feat_array
                    )
                    # Update DatasetInfo
                    for info_table in self.info.tables[table_group]:
                        if info_table.name == table_name:
                            info_table.fields[feat.name] = feat.dtype

                # Merge with main table
                table.to_lance().merge(new_feats_table, "id")
                self.save_info()

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
            load_active_learning (bool, optional): Load items active learning info. Defaults to True.
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
        # pylint: disable=unused-variable
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
            pyarrow_item_list = self._split_items(pyarrow_items, load_active_learning)

            return [
                DatasetItem.from_pyarrow(pyarrow_item, self.info, self.media_dir)
                for pyarrow_item in pyarrow_item_list
            ]
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
            load_active_learning (bool, optional): Load items active learning info. Defaults to True.
        Returns:
            list[DatasetItem]: List of dataset items
        """

        # Update info in case of change
        self.info = self.load_info()

        # Load PyArrow items from tables
        pyarrow_items: dict[str, dict[str, pa.Table]] = defaultdict(dict)

        # Search items with selected method
        if query["model"] in ["CLIP"]:
            pyarrow_items = self._embeddings_search(limit, offset, query)
        # NOTE: metadata search could go here

        if pyarrow_items is not None and pyarrow_items["main"]["db"].num_rows > 0:
            # Split results
            pyarrow_item_list = self._split_items(pyarrow_items, load_active_learning)

            return [
                DatasetItem.from_pyarrow(pyarrow_item, self.info, self.media_dir)
                for pyarrow_item in pyarrow_item_list
            ]
        return None

    def _embeddings_search(
        self,
        limit: int,
        offset: int,
        query: dict[str, str],
    ) -> dict[str, dict[str, pa.Table]]:
        """Perform item semantic search with embeddings

        Args:
            limit (int): Items limit
            offset (int): Items offset
            query (dict[str, str]): Search query

        Raises:
            ImportError: Required pixano-inference module could not be imported

        Returns:
            dict[str, dict[str, pa.Table]]: Search results
        """

        # Load tables
        ds_tables = self.open_tables()

        # Create PyArrow items
        pyarrow_items: dict[str, dict[str, pa.Table]] = defaultdict(dict)

        # Find CLIP embeddings
        if "embeddings" not in self.info.tables:
            return None
        for table in self.info.tables["embeddings"]:
            if table.type == "search" and table.source == query["model"]:
                sem_search_table = ds_tables["embeddings"][table.name]
                sem_search_views = [
                    field_name
                    for field_name, field_type in table.fields.items()
                    if field_type == "vector(512)"
                ]

        if query["model"] == "CLIP":
            # Initialize CLIP model
            try:
                # pylint: disable=import-outside-toplevel
                from pixano_inference.transformers import CLIP
            except ImportError as e:
                raise ImportError(
                    "Please install the pixano-inference module to perform semantic search with CLIP"
                ) from e

            model = CLIP()

        model_query = model.semantic_search(query["search"])

        # Perform semantic search
        # pylint: disable=unused-variable
        results_table = (
            sem_search_table.search(model_query, sem_search_views[0])
            .limit(min(offset + limit, self.num_rows))
            .to_arrow()
        )

        # If more than one view, search on all views and select the best results based on distance
        if len(sem_search_views) > 1:
            for view in sem_search_views[1:]:
                view_results_table = (
                    sem_search_table.search(model_query, view)
                    .limit(min(offset + limit, self.num_rows))
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

        return pyarrow_items

    def _split_items(
        self,
        pyarrow_items: dict[str, dict[str, pa.Table]],
        load_active_learning: bool,
    ) -> list[dict[str, dict[str, pa.Table]]]:
        """Split PyArrow tables into list of PyArrow tables

        Args:
            pyarrow_items (dict[str, dict[str, pa.Table]]): PyArrow tables
            load_active_learning (bool): Load items active learning info

        Returns:
            list[dict[str, dict[str, pa.Table]]]: List of PyArrow tables
        """

        # Load tables
        ds_tables = self.open_tables()

        # Create list of PyArrow tables
        pyarrow_item_list: list[dict[str, dict[str, pa.Table]]] = []

        for index in range(pyarrow_items["main"]["db"].num_rows):
            pyarrow_item_list.append(defaultdict(dict))
            # Main table
            pyarrow_item_list[index]["main"]["db"] = pyarrow_items["main"]["db"].take(
                [index]
            )
            item_id = pyarrow_item_list[index]["main"]["db"].to_pylist()[0]["id"]

            # Media tables
            for media_source, media_table in ds_tables["media"].items():
                # If media table already created
                if "media" in pyarrow_items:
                    pyarrow_item_list[index]["media"][media_source] = (
                        pa_ds.dataset(pyarrow_items["media"][media_source])
                        .scanner(filter=pa_ds.field("id") == item_id)
                        .to_table()
                    )
                # Else, retrieve media items individually
                else:
                    lance_scanner = media_table.to_lance().scanner(
                        filter=f"id in ('{item_id}')"
                    )
                    pyarrow_item_list[index]["media"][
                        media_source
                    ] = lance_scanner.to_table()

            # Active learning tables
            if load_active_learning:
                # If active learning table already created
                if "active_learning" in pyarrow_items:
                    for al_source in ds_tables["active_learning"].keys():
                        pyarrow_item_list[index]["active_learning"][al_source] = (
                            pa_ds.dataset(pyarrow_items["active_learning"][al_source])
                            .scanner(filter=pa_ds.field("id") == item_id)
                            .to_table()
                        )
                # Else, retrieve active learning items individually
                else:
                    for al_source, al_table in ds_tables["active_learning"].items():
                        lance_scanner = al_table.to_lance().scanner(
                            filter=f"id in ('{item_id}')"
                        )
                        pyarrow_item_list[index]["active_learning"][
                            al_source
                        ] = lance_scanner.to_table()

        return pyarrow_item_list

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
            for table_name, media_table in ds_tables["media"].items():
                lance_scanner = media_table.to_lance().scanner(
                    filter=f"id in ('{item_id}')"
                )
                pyarrow_item["media"][table_name] = lance_scanner.to_table()

        # Load PyArrow item from objects tables
        if load_objects:
            for table_name, obj_table in ds_tables["objects"].items():
                lance_scanner = obj_table.to_lance().scanner(
                    filter=f"item_id in ('{item_id}')"
                )
                pyarrow_item["objects"][table_name] = lance_scanner.to_table()

        # Load PyArrow item from active learning tables
        if load_active_learning:
            for table_name, al_table in ds_tables["active_learning"].items():
                lance_scanner = al_table.to_lance().scanner(
                    filter=f"id in ('{item_id}')"
                )
                pyarrow_item["active_learning"][table_name] = lance_scanner.to_table()

        # Load PyArrow item from segmentation embeddings tables
        found_embeddings = not load_embeddings
        if load_embeddings and "embeddings" in self.info.tables:
            for table in self.info.tables["embeddings"]:
                if table.source.lower() in model_id.lower():
                    found_embeddings = True
                    emb_table = ds_tables["embeddings"][table.name]
                    lance_scanner = emb_table.to_lance().scanner(
                        filter=f"id in ('{item_id}')"
                    )
                    pyarrow_item["embeddings"][table.name] = lance_scanner.to_table()

        if pyarrow_item["main"]["db"].num_rows > 0 and found_embeddings:
            return DatasetItem.from_pyarrow(
                pyarrow_item,
                self.info,
                self.media_dir,
                media_features=True,
                model_id=model_id,
            )
        return None

    def save_item(self, item: DatasetItem):
        """Save dataset item features and objects

        Args:
            item (DatasetItem): Item to save
        """

        # Update info in case of change
        self.info = self.load_info()

        # Load dataset tables
        ds_tables = self.open_tables()
        main_table = ds_tables["main"]["db"]

        # Add new item features
        self.update_table(item.features, main_table, "main", "db")

        # Reload dataset tables
        ds_tables = self.open_tables()
        main_table = ds_tables["main"]["db"]

        # Update item
        item.update(main_table)

        # Add or update item objects
        for obj in item.objects.values():
            table_found = False
            if "objects" in self.info.tables:
                for table in self.info.tables["objects"]:
                    if table.source == obj.source_id:
                        # Load object table
                        table_found = True
                        obj_table = ds_tables["objects"][table.name]

                        # Add new object features
                        self.update_table(
                            obj.features, obj_table, "objects", table.name
                        )

                        # Reload dataset tables
                        ds_tables = self.open_tables()
                        main_table = ds_tables["objects"][table.name]

                        # Add or update object
                        obj.add_or_update(obj_table)
            # If first object
            if not table_found and obj.source_id == "Ground Truth":
                # Create table
                table = DatasetTable(
                    name="objects",
                    source="Ground Truth",
                    fields={
                        "id": "str",
                        "item_id": "str",
                        "view_id": "str",
                        "bbox": "bbox",
                        "mask": "compressedrle",
                    },
                )
                for feat in obj.features.values():
                    table.fields[feat.name] = feat.dtype
                self.create_table(table, "objects")

                # Reload dataset tables
                ds_tables = self.open_tables()
                obj_table = ds_tables["objects"][table.name]

                # Add object
                obj.add_or_update(obj_table)

        # Delete removed item objects
        item.delete_objects(ds_tables)

    @staticmethod
    def find(
        dataset_id: str,
        directory: Path | S3Path,
    ) -> "Dataset":
        """Find Dataset in directory

        Args:
            dataset_id (str): Dataset ID
            directory (Path): Directory to search in

        Returns:
            Dataset: Dataset
        """

        # Browse directory
        for json_fp in directory.glob("*/db.json"):
            info = DatasetInfo.from_json(json_fp)
            if info.id == dataset_id:
                # Return dataset
                return Dataset(json_fp.parent)
        return None
