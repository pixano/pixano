# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

import duckdb
import lancedb
from lancedb.query import LanceQueryBuilder
from lancedb.table import LanceTable
from pydantic import ConfigDict

from pixano.datasets.features.schemas.items.item import Item

from .dataset_features_values import DatasetFeaturesValues
from .dataset_info import DatasetInfo
from .dataset_schema import (
    DatasetItem,
    DatasetSchema,
    SchemaRelation,
)
from .dataset_stat import DatasetStat
from .features import _SchemaGroup


if TYPE_CHECKING:
    from .features import BaseSchema


def _validate_ids_and_limit_and_offset(ids: list[str] | None, limit: int | None, offset: int = 0) -> None:
    if ids is None and limit is None:
        raise ValueError("limit must be set if ids is None")
    elif ids is not None and limit is not None:
        raise ValueError("ids and limit cannot be set at the same time")
    elif ids is not None and (not isinstance(ids, list) or not all(isinstance(i, str) for i in ids)):
        raise ValueError("ids must be a list of strings")
    elif limit is not None and (not isinstance(limit, int) or limit < 0) or not isinstance(offset, int) or offset < 0:
        raise ValueError("limit and offset must be positive integers")


def _validate_ids_item_ids_and_limit_and_offset(
    ids: list[str] | None, limit: int | None, offset: int = 0, item_ids: list[str] | None = None
) -> None:
    if ids is not None and item_ids is not None:
        raise ValueError("ids and item_ids cannot be set at the same time")
    if ids is None and item_ids is None and limit is None:
        raise ValueError("limit must be set if ids is None and item_ids is None")
    elif (ids is not None or item_ids is not None) and limit is not None:
        raise ValueError("ids or item_ids and limit cannot be set at the same time")
    elif ids is not None and (not isinstance(ids, list) or not all(isinstance(i, str) for i in ids)):
        raise ValueError("ids must be a list of strings")
    elif item_ids is not None and (not isinstance(item_ids, list) or not all(isinstance(i, str) for i in item_ids)):
        raise ValueError("item_ids must be a list of strings")
    elif limit is not None and (not isinstance(limit, int) or limit < 1) or not isinstance(offset, int) or offset < 0:
        raise ValueError("limit and offset must be positive integers")


class Dataset:
    """Dataset.

    Attributes:
        path (Path): Dataset path
        info (DatasetInfo, optional): Dataset info
        dataset_schema (DatasetSchema, optional): Dataset schema
        features_values (DatasetFeaturesValues, optional): Dataset features values
        stats (list[DatasetStat], optional): Dataset stats
        thumbnail (str, optional): Dataset thumbnail base 64 URL
    """

    DB_PATH: str = "db"
    PREVIEWS_PATH: str = "previews"
    INFO_FILE: str = "info.json"
    SCHEMA_FILE: str = "schema.json"
    FEATURES_VALUES_FILE: str = "features_values.json"
    STAT_FILE: str = "stats.json"
    THUMB_FILE: str = "preview.png"

    path: Path
    info: DatasetInfo
    schema: DatasetSchema
    features_values: DatasetFeaturesValues = DatasetFeaturesValues()
    stats: list[DatasetStat] = []
    thumbnail: Path
    # Allow arbitrary types because of S3 Path
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, path: Path):
        """Initialize dataset.

        Args:
            path (Path): Dataset path
        """
        info_file = path / self.INFO_FILE
        schema_file = path / self.SCHEMA_FILE
        features_values_file = path / self.FEATURES_VALUES_FILE
        stats_file = path / self.STAT_FILE
        thumb_file = path / self.THUMB_FILE

        self.path = path
        self.info = DatasetInfo.from_json(info_file)
        self.schema = DatasetSchema.from_json(schema_file)
        self.features_values = DatasetFeaturesValues.from_json(features_values_file)
        self.stats = DatasetStat.from_json(stats_file) if stats_file.is_file() else []
        self.thumbnail = thumb_file

        self._db_connection = self._connect()

        self.dataset_item_model = DatasetItem.from_dataset_schema(self.schema)

    @property
    def num_rows(self) -> int:
        """Return number of rows in dataset.

        Returns:
            int: Number of rows
        """
        # Return number of rows of item table
        return len(self.open_table(_SchemaGroup.ITEM.value))

    @property
    def media_dir(self) -> Path:
        """Return dataset media directory.

        Returns:
            Path: Dataset media directory
        """
        return self.path / "media"

    @property
    def _db_path(self) -> Path:
        """Return dataset db path.

        Returns:
            Path: Dataset db path
        """
        return self.path / self.DB_PATH

    def _reload_schema(self) -> None:
        """Reload schema.

        Returns:
            DatasetSchema: Dataset schema
        """
        self.schema = DatasetSchema.from_json(self.path / "schema.json")

    def _connect(self) -> lancedb.db.DBConnection:
        """Connect to dataset with LanceDB.

        Returns:
            lancedb.db.DBConnection: Dataset LanceDB connection
        """
        return lancedb.connect(self._db_path)

    def _search_by_field(
        self,
        table: lancedb.db.LanceTable,
        field: str,
        values: str,
        limit: int | None = None,
    ) -> LanceQueryBuilder:
        return (
            table.search()
            .where(
                f"{field} in {values}",
            )
            .limit(limit)
        )

    def _search_by_ids(
        self,
        ids: list[str],
        table: LanceTable,
        limit: int | None = None,
    ) -> LanceQueryBuilder:
        sql_ids = f"('{ids[0]}')" if len(ids) == 1 else str(tuple(ids))
        return self._search_by_field(table, "id", sql_ids, limit)

    def open_tables(self, names: list[str] | None = None) -> dict[str, LanceTable]:
        """Open dataset tables with LanceDB.

        Args:
            names (list[str] | None, optional): Table names to open. If None, open all tables.

        Returns:
            dict[str, LanceTable]: Dataset tables
        """
        tables: dict[str, LanceTable] = defaultdict(dict)

        for name in names if names is not None else self.schema.schemas.keys():
            tables[name] = self.open_table(name)

        return tables

    def open_table(self, name) -> LanceTable:
        """Open dataset table with LanceDB.

        Returns:
            LanceTable: Dataset table
        """
        for table_name in self.schema.schemas.keys():
            if table_name == name:
                return self._db_connection.open_table(table_name)

        raise ValueError(f"Table {name} not found in dataset")

    def get_data(
        self,
        table_name: str,
        ids: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
        item_ids: list[str] | None = None,
    ) -> list[BaseSchema]:
        """Read data from a table.

        Args:
            table_name (str): Table name.
            ids (list[str]): ids to read.
            limit (int | None, optional): Limit.
            offset (int, optional): Offset.
            item_ids (list[str] | None, optional): Item ids to read.

        Returns:
            list[BaseSchema]: List of values.
        """
        if table_name == _SchemaGroup.ITEM.value:
            if item_ids is not None:
                if ids is None:
                    ids = item_ids
                else:
                    raise ValueError("ids and item_ids cannot be set at the same time")
                item_ids = None

        _validate_ids_item_ids_and_limit_and_offset(ids, limit, offset, item_ids)

        if item_ids is not None:
            sql_item_ids = f"('{item_ids[0]}')" if len(item_ids) == 1 else str(tuple(item_ids))

        table = self.open_table(table_name)

        if ids is None:
            if item_ids is None:
                lance_table = table.to_lance()  # noqa: F841
                item_rows = (
                    duckdb.query(f"SELECT * FROM lance_table ORDER BY len(id)," f"id LIMIT {limit} OFFSET {offset}")
                    .to_arrow_table()
                    .to_pylist()
                )
                model = self.schema.schemas[table_name]
                models: list[BaseSchema] = []
                for row in item_rows:
                    models.append(model(**{k: v for k, v in row.items() if k in model.field_names()}))
                    models[-1].dataset = self
                return models

            query = self._search_by_field(table, "item_ref.id", sql_item_ids, None)
        else:
            query = self._search_by_ids(ids, table, None)

        query_models: list[BaseSchema] = query.to_pydantic(self.schema.schemas[table_name])
        for model in query_models:
            model.dataset = self  # type: ignore[attr-defined]

        return query_models

    def get_dataset_items(
        self,
        ids: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[DatasetItem]:
        """Read dataset items.

        Args:
            ids (list[str] | None, optional): Item ids to read.
            limit (int | None, optional): Limit.
            offset (int, optional): Offset.

        Returns:
            list[DatasetItem]: List of dataset items.
        """
        _validate_ids_and_limit_and_offset(ids, limit, offset)

        items = cast(list[Item], self.get_data(_SchemaGroup.ITEM.value, ids, limit, offset))
        if items == []:
            return []
        item_ids: list[str] = [item.id for item in items]
        sql_ids = f"('{item_ids[0]}')" if len(item_ids) == 1 else str(tuple(item_ids))

        # Load tables
        ds_tables = self.open_tables()

        # Load items data from the tables
        data_dict: dict[str, dict[str, BaseSchema | list[BaseSchema]]] = {item.id: item.model_dump() for item in items}
        for table_name, table in ds_tables.items():
            if table_name == _SchemaGroup.ITEM.value:
                continue
            is_collection = self.schema.relations[_SchemaGroup.ITEM.value][table_name] == SchemaRelation.ONE_TO_MANY
            table_schema = self.schema.schemas[table_name]

            lance_query = self._search_by_field(table, "item_ref.id", sql_ids)
            pydantic_table: list[BaseSchema] = lance_query.to_pydantic(table_schema)

            for row in pydantic_table:
                row.dataset = self
                item_id = row.item_ref.id
                if is_collection:
                    if table_name not in data_dict[item_id]:
                        data_dict[item_id][table_name] = []
                    data_dict[item_id][table_name].append(row)
                else:
                    data_dict[item_id][table_name] = row

        dataset_items = [self.dataset_item_model(**data_dict[item_id]) for item_id in item_ids]

        return dataset_items

    def get_all_ids(self, table_name: str = _SchemaGroup.ITEM.value) -> list[str]:
        """Get all ids from a table.

        Args:
            table_name (str, optional): table to look for ids.

        Returns:
            list[str]: list of ids.
        """
        query = self.open_table(table_name).search().select(["id"]).limit(None).to_arrow()
        return sorted(row.as_py() for row in query["id"])

    def add_data(self, table_name: str, data: list[BaseSchema]) -> None:
        """Add data to a table.

        Args:
            table_name (str): Table name.
            data (list[BaseSchema]): Data to add.
        """
        if not all(isinstance(item, type(data[0])) for item in data) or not issubclass(
            type(data[0]), self.schema.schemas[table_name]
        ):
            raise ValueError(f"All data must be instances of the table type {self.schema.schemas[table_name]}")

        table = self.open_table(table_name)
        table.add(data)

    def add_dataset_items(self, data: list[DatasetItem]) -> None:
        """Add dataset items.

        Args:
            data (list[DatasetItem]): Data to add.
        """
        if not all(isinstance(item, type(data[0])) for item in data) or not issubclass(
            type(data[0]), self.dataset_item_model
        ):
            raise ValueError(f"All data must be instances of the dataset item type {self.dataset_item_model}")

        schemas_data = [item.to_schemas_data(self.schema) for item in data]
        tables_data: dict[str, Any] = {}
        for table_name in self.schema.schemas.keys():
            for item in schemas_data:
                if table_name not in tables_data:
                    tables_data[table_name] = []
                if isinstance(item[table_name], list):
                    tables_data[table_name].extend(item[table_name])
                elif item[table_name] is not None:
                    tables_data[table_name].append(item[table_name])
        for table_name, table_data in tables_data.items():
            if table_data != []:
                self.add_data(table_name, table_data)

    def delete_data(self, table_name: str, ids: list[str]) -> None:
        """Delete data from a table.

        Args:
            table_name (str): Table name.
            ids (list[str]): Ids to delete.
        """
        table = self.open_table(table_name)
        sql_ids = f"('{ids[0]}')" if len(ids) == 1 else str(tuple(ids))
        table.delete(where=f"id in {sql_ids}")

    def delete_dataset_items(self, ids: list[str]) -> None:
        """Delete dataset items.

        Args:
            ids (list[str]): Ids to delete.
        """
        sql_ids = f"('{ids[0]}')" if len(ids) == 1 else str(tuple(ids))
        for table_name in self.schema.schemas.keys():
            if table_name == _SchemaGroup.ITEM.value:
                self.delete_data(table_name, ids)
            else:
                table = self.open_table(table_name)
                table_ids = (
                    table.search()
                    .select(["id"])
                    .where(f"item_ref.id in {sql_ids}")
                    .limit(None)
                    .to_arrow()["id"]
                    .to_pylist()
                )
                if table_ids == []:
                    continue
                table_sql_ids = f"('{table_ids[0]}')" if len(table_ids) == 1 else str(tuple(table_ids))
                table.delete(where=f"id in {table_sql_ids}")

    def update_data(self, table_name: str, data: list[BaseSchema]) -> None:
        """Update data in a table.

        Args:
            table_name (str): Table name.
            data (list[BaseSchema]): Data to update.
        """
        if not all(isinstance(item, type(data[0])) for item in data) or not issubclass(
            type(data[0]), self.schema.schemas[table_name]
        ):
            raise ValueError(f"All data must be instances of the table type {self.schema.schemas[table_name]}.")

        table = self.open_table(table_name)
        ids = [item.id for item in data]
        sql_ids = f"('{ids[0]}')" if len(ids) == 1 else str(tuple(ids))
        table.delete(where=f"id in {sql_ids}")
        table.add(data)

    def update_dataset_items(self, data: list[DatasetItem]) -> None:
        """Update dataset items.

        Args:
            data (list[DatasetItem]): Data to update.
        """
        ids = [item.id for item in data]
        self.delete_dataset_items(ids)
        self.add_dataset_items(data)

    @staticmethod
    def find(
        id: str,
        directory: Path,
    ) -> "Dataset":
        """Find Dataset in directory.

        Args:
            id (str): Dataset ID.
            directory (Path): Directory to search in.

        Returns:
            Dataset: The found dataset.
        """
        # Browse directory
        for json_fp in directory.glob("*/info.json"):
            info = DatasetInfo.from_json(json_fp)
            if info.id == id:
                # Return dataset
                return Dataset(json_fp.parent)
        raise FileNotFoundError(f"Dataset {id} not found in {directory}")
