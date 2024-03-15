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
from lancedb.pydantic import LanceModel
from lancedb.query import LanceQueryBuilder
from pydantic import BaseModel, ConfigDict
from s3path import S3Path

from pixano.core.types.image import Image
from pixano.core.types.registry import _TABLE_TYPE_REGISTRY
from pixano.data.dataset.dataset_features_values import DatasetFeaturesValues
from pixano.data.dataset.dataset_info import DatasetInfo
from pixano.data.dataset.dataset_item import (
    DatasetItem,
    TableGroup,
    create_custom_dataset_item_class,
)
from pixano.data.dataset.dataset_schema import DatasetSchema
from pixano.data.dataset.dataset_stat import DatasetStat


DEFAULT_DB_PATH = "db"
DEFAULT_PREVIEWS_PATH = "previews"


class Dataset(BaseModel):
    """Dataset.

    Attributes:
        path (Path | S3Path): Dataset path
        info (DatasetInfo, optional): Dataset info
        dataset_schema (DatasetSchema, optional): Dataset schema
        features_values (DatasetFeaturesValues, optional): Dataset features values
        stats (list[DatasetStat], optional): Dataset stats
        thumbnail (str, optional): Dataset thumbnail base 64 URL
    """

    path: Path | S3Path
    info: Optional[DatasetInfo] = None
    dataset_schema: Optional[DatasetSchema] = None
    features_values: Optional[DatasetFeaturesValues] = None
    stats: Optional[list[DatasetStat]] = None
    thumbnail: Optional[str] = None
    # Allow arbitrary types because of S3 Path
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(
        self,
        path: Path | S3Path,
    ):
        """Initialize dataset.

        Args:
            path (Path | S3Path): Dataset path
        """
        info_file = path / "info.json"
        schema_file = path / "schema.json"
        features_values_file = path / "features_values.json"
        stats_file = path / "stats.json"
        thumb_file = path / "preview.png"

        super().__init__(
            path=path,
            info=DatasetInfo.from_json(info_file),
            dataset_schema=DatasetSchema.from_json(schema_file),
            features_values=DatasetFeaturesValues.from_json(features_values_file),
            stats=DatasetStat.from_json(stats_file) if stats_file.is_file() else None,
            thumbnail=(
                Image(uri=thumb_file.absolute().as_uri()).url
                if thumb_file.is_file()
                else None
            ),
        )

        self._custom_dataset_item_class = create_custom_dataset_item_class(
            self.dataset_schema
        )

    @property
    def num_rows(self) -> int:
        """Return number of rows in dataset.

        Returns:
            int: Number of rows
        """
        # Return number of rows of item table
        return len(self.open_table(TableGroup.ITEM.value))

    @property
    def _media_dir(self) -> Path | S3Path:
        """Return dataset media directory.

        Returns:
            Path | S3Path: Dataset media directory
        """
        return self.path / "media"

    @property
    def _db_path(self) -> Path | S3Path:
        """Return dataset db path.

        Returns:
            Path | S3Path: Dataset db path
        """
        if isinstance(self.path, S3Path):
            return self.path.as_uri() + "/" + DEFAULT_DB_PATH

        return self.path / DEFAULT_DB_PATH

    def _reload_schema(self) -> DatasetSchema:
        """Reload schema.

        Returns:
            DatasetSchema: Dataset schema
        """
        self.dataset_schema = DatasetSchema.from_json(self.path / "schema.json")
        self._custom_dataset_item_class = create_custom_dataset_item_class(
            self.dataset_schema
        )

    @property
    def _CustomDatasetItem(self) -> DatasetItem:
        """Return custom dataset item class.

        Returns:
            DatasetItem: Custom dataset item class
        """
        return self._custom_dataset_item_class

    def _connect(self) -> lancedb.db.DBConnection:
        """Connect to dataset with LanceDB.

        Returns:
            lancedb.db.DBConnection: Dataset LanceDB connection
        """
        return lancedb.connect(self._db_path)

    def open_tables(self) -> dict[TableGroup, dict[str, lancedb.db.LanceTable]]:
        """Open dataset tables with LanceDB.

        Returns:
            dict[str, dict[str, lancedb.db.LanceTable]]: Dataset tables
        """
        ds = self._connect()

        ds_tables: dict[str, dict[TableGroup, lancedb.db.LanceTable]] = defaultdict(
            dict
        )

        for table_group, tables in self.dataset_schema.schemas.items():
            for table_name in tables.keys():
                ds_tables[TableGroup(table_group)][table_name] = ds.open_table(
                    table_name
                )

        return ds_tables

    def open_table(self, name) -> lancedb.db.LanceTable:
        """Open dataset table with LanceDB.

        Returns:
            lancedb.db.LanceTable: Dataset table
        """
        ds = self._connect()

        for _, tables in self.dataset_schema.schemas.items():
            for table_name in tables.keys():
                if table_name == name:
                    return ds.open_table(table_name)

        raise ValueError(f"Table {name} not found in dataset")

    def _search_values_by_field_in_table(
        self,
        table: lancedb.db.LanceTable,
        field: str,
        values: str,
        limit: Optional[int] = None,
    ) -> LanceQueryBuilder:
        return (
            table.search()
            .where(
                f"{field} in {values}",
            )
            .limit(limit)
        )

    def _read_items_data(
        self,
        ids: list[str],
        select_table_groups: list[TableGroup] = None,
        select_tables_per_group: Optional[dict[TableGroup, list[str]]] = None,
        remove_table_group_level: bool = True,
    ) -> dict[str, dict[str, dict[str, LanceModel]]]:
        sql_ids = f"('{ids[0]}')" if len(ids) == 1 else tuple(ids)

        # Reload schema
        self._reload_schema()

        # Load tables
        ds_tables = self.open_tables()

        # Load items data from the tables
        data_dict: dict[
            str, dict[str, dict[str, LanceModel]] | dict[str, LanceModel]
        ] = {id: {} for id in ids}
        for table_group in ds_tables.keys():
            item_id_field = "id" if table_group == TableGroup.ITEM else "item_id"

            if (
                select_table_groups
                and select_tables_per_group
                and table_group in select_table_groups
                and table_group in select_tables_per_group
            ):
                raise ValueError(
                    f"Table group {table_group} is in both select_table_groups "
                    "and select_tables_per_group"
                )
            elif (not select_table_groups and not select_tables_per_group) or (
                select_table_groups and table_group in select_table_groups
            ):
                tables_to_read = ds_tables[table_group].keys()
            elif select_tables_per_group and table_group in select_tables_per_group:
                tables_to_read = select_tables_per_group[table_group]
            else:
                tables_to_read = []

            for table_name in tables_to_read:
                if table_name not in ds_tables[table_group]:
                    raise ValueError(
                        f"Table {table_name} not found in {table_group.value} "
                        "table group"
                    )
                table = ds_tables[table_group][table_name]
                table_type = _TABLE_TYPE_REGISTRY[
                    self.dataset_schema.schemas[table_group.value][table_name]
                ]

                lance_query = self._search_values_by_field_in_table(
                    table, item_id_field, sql_ids
                )
                pydantic_table = lance_query.to_pydantic(table_type)

                for row in pydantic_table:
                    id = row.id if table_group == TableGroup.ITEM else row.item_id
                    if not remove_table_group_level:
                        if table_group.value not in data_dict[id].keys():
                            data_dict[id][table_group.value] = {}
                        data_dict[id][table_group.value][table_name] = row
                    else:
                        data_dict[id][table_name] = row

        # Raise error if some ids are not found
        ids_not_found = [id for id in ids if len(data_dict[id]) == 0]
        if len(ids_not_found) > 0:
            raise ValueError(
                f"Ids {ids_not_found} not found in {TableGroup.ITEM.value} table"
            )

        return data_dict

    def _read_data(
        self,
        ids: list[str],
        select_table_groups: Optional[list[TableGroup]] = None,
        select_tables_per_group: Optional[dict[TableGroup, list[str]]] = None,
        remove_table_group_level: bool = True,
    ) -> list[DatasetItem]:  # type: ignore
        if select_table_groups:
            select_table_groups = [
                TableGroup(table_group) if isinstance(table_group, str) else table_group
                for table_group in select_table_groups
            ]

        data_dict = self._read_items_data(
            ids, select_table_groups, select_tables_per_group, remove_table_group_level
        )

        dataset_items = [self._CustomDatasetItem(id=id, **data_dict[id]) for id in ids]

        return dataset_items

    def _read_table_group_data(
        self,
        ids: list[str],
        group: TableGroup,
        select: Optional[list[str]] = None,
        remove_table_group_level: bool = True,
    ) -> list[DatasetItem]:
        if select:
            select_tables_per_group = {
                group: [DatasetSchema.format_table_name(table) for table in select]
            }
            return self._read_data(
                ids, None, select_tables_per_group, remove_table_group_level
            )
        return self._read_data(ids, [group], None, remove_table_group_level)

    def _get_data(
        self,
        offset: int,
        limit: int,
        select_table_groups: Optional[list[TableGroup]] = None,
        select_tables_per_group: Optional[dict[TableGroup, list[str]]] = None,
        remove_table_group_level: bool = True,
    ) -> list[DatasetItem]:
        """Get items from dataset.

        Args:
            offset (int): Offset
            limit (int): Limit
            select_table_groups (list[str], optional): Table groups to read
            select_tables_per_group (list[str], optional): Tables to read per group
            remove_table_group_level (bool, optional): Remove table group level.
                Default is True.

        Returns:
            list[DatasetItem]: Dataset items
        """
        item_table = self.open_table(TableGroup.ITEM.value).to_lance()  # noqa: F841
        select_item = (
            select_table_groups is None
            or (select_table_groups and TableGroup.ITEM in select_table_groups)
            or (select_tables_per_group and TableGroup.ITEM in select_tables_per_group)
        )
        item_columns_selected = "*" if select_item else "id"
        item_rows = (
            duckdb.query(
                f"SELECT {item_columns_selected} FROM item_table ORDER BY len(id),"
                f"id LIMIT {limit} OFFSET {offset}"
            )
            .to_arrow_table()
            .to_pylist()
        )

        if select_item:
            item_models = {}
        ids = []
        for row in item_rows:
            if select_item:
                item_models[row["id"]] = _TABLE_TYPE_REGISTRY[
                    self.dataset_schema.schemas[TableGroup.ITEM.value][
                        TableGroup.ITEM.value
                    ]
                ](**row)
                ids.append(row["id"])
            else:
                ids.append(row["id"])

        if select_table_groups:
            select_table_groups = [
                TableGroup(table_group) if isinstance(table_group, str) else table_group
                for table_group in select_table_groups
                if TableGroup(table_group) != TableGroup.ITEM
            ]

        if select_tables_per_group:
            select_tables_per_group = {
                TableGroup(table_group)
                if isinstance(table_group, str)
                else table_group: select_tables
                for table_group, select_tables in select_tables_per_group.items()
                if TableGroup(table_group) != TableGroup.ITEM
            }

        data_dict = self._read_items_data(
            ids, select_table_groups, select_tables_per_group, remove_table_group_level
        )

        dataset_items = []
        for id in data_dict.keys():
            if select_item:
                if remove_table_group_level:
                    data_dict[id][TableGroup.ITEM.value] = item_models.pop(id)
                else:
                    data_dict[id][TableGroup.ITEM.value] = {}
                    data_dict[id][TableGroup.ITEM.value][TableGroup.ITEM.value] = (
                        item_models.pop(id)
                    )
            dataset_items.append(self._CustomDatasetItem(id=id, **data_dict[id]))

        return dataset_items

    def _get_table_group_data(
        self,
        offset: int,
        limit: int,
        group: TableGroup,
        select: Optional[list[str]] = None,
    ) -> list[DatasetItem]:
        if select:
            select_tables_per_group = {
                group: [DatasetSchema.format_table_name(table) for table in select]
            }
            return self._get_data(offset, limit, None, select_tables_per_group)
        return self._get_data(offset, limit, [group], None)

    def read_items(
        self,
        ids: list[str],
    ) -> list[DatasetItem]:  # type: ignore
        """Read items from dataset.

        Args:
            ids (list[str]): Item ids
            select_table_groups (list[str], optional): Table groups to read
            select_tables_per_group (list[str], optional): Tables to read per group
        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._read_data(ids, None, None)

    def read_item(
        self,
        id: str,
    ) -> DatasetItem:
        """Read item from dataset.

        Args:
            id (str): Item id
        Returns:
            DatasetItem: Dataset item
        """
        return self.read_items([id])[0]

    def get_items(
        self,
        offset: int,
        limit: int,
    ) -> list[DatasetItem]:
        """Get items from dataset.

        Args:
            offset (int): Offset
            limit (int): Limit
        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._get_data(offset, limit)

    def get_item(
        self,
        idx: int,
    ) -> list[DatasetItem]:
        """Get item from dataset.

        Args:
            idx (int): Index

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self.get_items(idx, 1)[0]

    def read_views(
        self, ids: list[str], select: Optional[list[str]] = None
    ) -> list[DatasetItem]:  # type: ignore
        """Read views from dataset.

        Args:
            ids (list[str]): Item ids.
            select (list[str], optional): Views to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._read_table_group_data(ids, TableGroup.VIEW, select)

    def read_view(self, id: str, select: Optional[list[str]] = None) -> DatasetItem:
        """Read view from dataset.

        Args:
            id (str): Item id.
            select (list[str], optional): Views to read. Default is None.

        Returns:
            DatasetItem: Dataset item
        """
        return self.read_views([id], select)[0]

    def get_views(
        self,
        offset: int,
        limit: int,
        select: Optional[list[str]] = None,
    ) -> list[DatasetItem]:
        """Get views from dataset.

        Args:
            offset (int): Offset
            limit (int): Limit
            select (list[str], optional): Views to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._get_table_group_data(offset, limit, TableGroup.VIEW, select)

    def get_view(
        self,
        idx: int,
        select: Optional[list[str]] = None,
    ) -> DatasetItem:
        """Get view from dataset.

        Args:
            idx (int): Index.
            select (list[str], optional): Views to read. Default is None.

        Returns:
            DatasetItem: Dataset items
        """
        return self.get_views(idx, 1, select)[0]

    def read_objects(
        self, ids: list[str], select: Optional[list[str]] = None
    ) -> list[DatasetItem]:  # type: ignore
        """Read objects from dataset.

        Args:
            ids (list[str]): Item ids.
            select (list[str], optional): Objects to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._read_table_group_data(ids, TableGroup.OBJECT, select)

    def read_object(self, id: str, select: Optional[list[str]] = None) -> DatasetItem:
        """Read object from dataset.

        Args:
            id (str): Item id.
            select (list[str], optional): Objects to read. Default is None.

        Returns:
            DatasetItem: Dataset item
        """
        return self.read_objects([id], select)[0]

    def get_objects(
        self,
        offset: int,
        limit: int,
        select: Optional[list[str]] = None,
    ) -> list[DatasetItem]:
        """Get objects from dataset.

        Args:
            offset (int): Offset
            limit (int): Limit
            select (list[str], optional): Objects to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._get_table_group_data(offset, limit, TableGroup.OBJECT, select)

    def get_object(
        self,
        idx: int,
        select: Optional[list[str]] = None,
    ) -> DatasetItem:
        """Get object from dataset.

        Args:
            idx (int): Index.
            select (list[str], optional): Objects to read. Default is None.

        Returns:
            DatasetItem: Dataset items
        """
        return self.get_objects(idx, 1, select)[0]

    def read_embeddings(
        self, ids: list[str], select: Optional[list[str]] = None
    ) -> list[DatasetItem]:  # type: ignore
        """Read embeddings from dataset.

        Args:
            ids (list[str]): Item ids.
            select (list[str], optional): Embeddings to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._read_table_group_data(ids, TableGroup.EMBEDDING, select)

    def read_embedding(
        self, id: str, select: Optional[list[str]] = None
    ) -> DatasetItem:
        """Read embedding from dataset.

        Args:
            id (str): Item id.
            select (list[str], optional): Embeddings to read. Default is None.

        Returns:
            DatasetItem: Dataset item
        """
        return self.read_embeddings([id], select)[0]

    def get_embeddings(
        self,
        offset: int,
        limit: int,
        select: Optional[list[str]] = None,
    ) -> list[DatasetItem]:
        """Get embeddings from dataset.

        Args:
            offset (int): Offset
            limit (int): Limit
            select (list[str], optional): Embeddings to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._get_table_group_data(offset, limit, TableGroup.EMBEDDING, select)

    def get_embedding(
        self,
        idx: int,
        select: Optional[list[str]] = None,
    ) -> DatasetItem:
        """Get embedding from dataset.

        Args:
            idx (int): Index.
            select (list[str], optional): Embeddings to read. Default is None.

        Returns:
            DatasetItem: Dataset items
        """
        return self.get_embedding(idx, 1, select)[0]

    @staticmethod
    def find(
        dataset_id: str,
        directory: Path | S3Path,
    ) -> "Dataset":
        """Find Dataset in directory.

        Args:
            dataset_id (str): Dataset ID
            directory (Path): Directory to search in

        Returns:
            Dataset: Dataset
        """
        # Browse directory
        for json_fp in directory.glob("*/info.json"):
            info = DatasetInfo.from_json(json_fp)
            if info.id == dataset_id:
                # Return dataset
                return Dataset(json_fp.parent)
        return None
