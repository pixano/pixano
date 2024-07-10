# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from collections import defaultdict
from pathlib import Path
from typing import cast

import duckdb
import lancedb
from lancedb.pydantic import LanceModel
from lancedb.query import LanceQueryBuilder
from lancedb.table import LanceTable
from pydantic import ConfigDict
from s3path import S3Path

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


def _validate_ids_and_limit_and_offset(ids: list[str] | None, limit: int | None, offset: int = 0) -> None:
    if ids is None and limit is None:
        raise ValueError("Limit must be set if ids is None")
    elif ids is not None and limit is not None:
        raise ValueError("Ids and limit cannot be set at the same time")
    elif ids is not None  and (not isinstance(ids, list) or not all(isinstance(i, str) for i in ids)):
        raise ValueError("Ids must be a list of strings")
    elif limit is not None and (not isinstance(limit, int) or limit < 0) or not isinstance(offset, int) or offset < 0:
        raise ValueError("Limit and offset must be positive integers")


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
    dataset_schema: DatasetSchema
    features_values: DatasetFeaturesValues | None = None
    stats: list[DatasetStat] | None = None
    thumbnail: str | None = None
    # Allow arbitrary types because of S3 Path
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, path: Path | S3Path):
        """Initialize dataset.

        Args:
            path (Path | S3Path): Dataset path
        """
        info_file = path / self.INFO_FILE
        schema_file = path / self.SCHEMA_FILE
        features_values_file = path / self.FEATURES_VALUES_FILE
        stats_file = path / self.STAT_FILE
        thumb_file = path / self.THUMB_FILE

        self.path = path
        self.info = DatasetInfo.from_json(info_file)
        self.dataset_schema = DatasetSchema.from_json(schema_file)
        self.features_values = DatasetFeaturesValues.from_json(features_values_file)
        self.stats = DatasetStat.from_json(stats_file) if stats_file.is_file() else None
        self.thumbnail = thumb_file

        self._db_connection = self._connect()

        self.dataset_item_model = DatasetItem.from_dataset_schema(self.dataset_schema)

    @property
    def num_rows(self) -> int:
        """Return number of rows in dataset.

        Returns:
            int: Number of rows
        """
        # Return number of rows of item table
        return len(self.open_table(_SchemaGroup.ITEM.value))

    @property
    def media_dir(self) -> Path | S3Path:
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
            return self.path.as_uri() + "/" + self.DB_PATH

        return self.path / self.DB_PATH

    def _reload_schema(self) -> DatasetSchema:
        """Reload schema.

        Returns:
            DatasetSchema: Dataset schema
        """
        self.dataset_schema = DatasetSchema.from_json(self.path / "schema.json")

    def _connect(self) -> lancedb.db.DBConnection:
        """Connect to dataset with LanceDB.

        Returns:
            lancedb.db.DBConnection: Dataset LanceDB connection
        """
        return lancedb.connect(self._db_path)

    def _search_by_field(
        self,
        table: LanceTable,
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

        for name in names if names is not None else self.dataset_schema.schemas.keys():
            tables[name] = self.open_table(name)

        return tables

    def open_table(self, name) -> LanceTable:
        """Open dataset table with LanceDB.

        Returns:
            LanceTable: Dataset table
        """
        for table_name in self.dataset_schema.schemas.keys():
            if table_name == name:
                return self._db_connection.open_table(table_name)

        raise ValueError(f"Table {name} not found in dataset")

    def get_data(
        self,
        table_name: str,
        ids: list[str] | None = None,
        limit: int | None = None,
        offset: int = 0,
    ) -> list[LanceModel]:
        """Read data from a table.

        Args:
            table_name (str): Table name.
            ids (list[str]): ids to read.
            limit (int | None, optional): Limit.
            offset (int, optional): Offset.

        Returns:
            list[LanceModel]: List of values.
        """
        _validate_ids_and_limit_and_offset(ids, limit, offset)

        table = self.open_table(table_name)

        if ids is None:
            lance_table = table.to_lance() # noqa: F841
            item_rows = (
                duckdb.query(f"SELECT * FROM lance_table ORDER BY len(id)," f"id LIMIT {limit} OFFSET {offset}")
                .to_arrow_table()
                .to_pylist()
            )
            model = self.dataset_schema.schemas[table_name]
            return [model(**{k: v for k, v in row.items() if k in model.field_names()}) for row in item_rows]
        return self._search_by_ids(ids, table, limit).to_pydantic(self.dataset_schema.schemas[table_name])

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
        item_ids: list[str] = [item.id for item in items]
        sql_ids = f"('{item_ids[0]}')" if len(item_ids) == 1 else str(tuple(item_ids))

        # Load tables
        ds_tables = self.open_tables()

        # Load items data from the tables
        data_dict: dict[str, dict[str, LanceModel | list[LanceModel]]] = {
            item.id: item.model_dump() for item in items
        }
        for table_name, table in ds_tables.items():
            if table_name == _SchemaGroup.ITEM.value:
                continue
            is_collection = (
                self.dataset_schema.relations[_SchemaGroup.ITEM.value][table_name] == SchemaRelation.ONE_TO_MANY
            )
            table_schema = self.dataset_schema.schemas[table_name]

            lance_query = self._search_by_field(table, "item_ref.id", sql_ids)
            pydantic_table = lance_query.to_pydantic(table_schema)

            for row in pydantic_table:
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

    @staticmethod
    def find(
        id: str,
        directory: Path | S3Path,
        error_if_not_found: bool = True,
    ) -> "Dataset":
        """Find Dataset in directory.

        Args:
            id (str): Dataset ID.
            directory (Path | S3Path): Directory to search in.
            error_if_not_found (bool, optional): Raise error if not found else return None.

        Returns:
            Dataset: The found dataset.
        """
        # Browse directory
        for json_fp in directory.glob("*/info.json"):
            info = DatasetInfo.from_json(json_fp)
            if info.id == id:
                # Return dataset
                return Dataset(json_fp.parent)
        if error_if_not_found:
            raise ValueError(f"Dataset {id} not found in {directory}")
        else:
            return None
