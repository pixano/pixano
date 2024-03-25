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
from typing import Optional, Union

import duckdb
import lancedb
from lancedb.pydantic import LanceModel
from lancedb.query import LanceQueryBuilder
from pydantic import ConfigDict
from s3path import S3Path

from .dataset_features_values import DatasetFeaturesValues
from .dataset_info import DatasetInfo
from .dataset_schema import (
    DatasetItem,
    DatasetSchema,
    SchemaRelation,
    create_custom_dataset_item_class_from_dataset_schema,
    create_sub_dataset_item,
)
from .dataset_stat import DatasetStat
from .features.schemas.group import _SchemaGroup


def _lance_query_to_pydantic(
    lance_query: LanceQueryBuilder,
    model: type[LanceModel],
    allow_extra_fields: bool = False,
):
    return [
        model(
            **{
                k: v
                for k, v in row.items()
                if allow_extra_fields or k in model.field_names()
            }
        )
        for row in lance_query.to_arrow().to_pylist()
    ]


class Dataset:
    """Dataset.

    Attributes:
        path (Path | S3Path): Dataset path
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
    FEATURES_VALUES: str = "features_values.json"
    STAT_FILE: str = "stats.json"
    THUMB_FILE: str = "preview.png"

    path: Path | S3Path
    info: Optional[DatasetInfo] = None
    dataset_schema: Optional[DatasetSchema] = None
    features_values: Optional[DatasetFeaturesValues] = None
    stats: Optional[list[DatasetStat]] = None
    thumbnail: Optional[str] = None
    # Allow arbitrary types because of S3 Path
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, path: Path | S3Path, info: Optional[DatasetInfo] = None):
        """Initialize dataset.

        Args:
            path (Path | S3Path): Dataset path
            info (DatasetInfo, optional): Dataset info. Default is None.
        """
        info_file = path / self.INFO_FILE
        schema_file = path / self.SCHEMA_FILE
        features_values_file = path / self.FEATURES_VALUES
        stats_file = path / self.STAT_FILE
        thumb_file = path / self.THUMB_FILE

        self.path = path
        self.info = DatasetInfo.from_json(info_file)
        self.dataset_schema = DatasetSchema.from_json(schema_file)
        self.features_values = DatasetFeaturesValues.from_json(features_values_file)
        self.stats = DatasetStat.from_json(stats_file) if stats_file.is_file() else None
        self.thumbnail = thumb_file

        self._custom_dataset_item_class = (
            create_custom_dataset_item_class_from_dataset_schema(self.dataset_schema)
        )

    @property
    def num_rows(self) -> int:
        """Return number of rows in dataset.

        Returns:
            int: Number of rows
        """
        # Return number of rows of item table
        return len(self.open_table(_SchemaGroup.ITEM.value))

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
            return self.path.as_uri() + "/" + self.DB_PATH

        return self.path / self.DB_PATH

    def _reload_schema(self) -> DatasetSchema:
        """Reload schema.

        Returns:
            DatasetSchema: Dataset schema
        """
        self.dataset_schema = DatasetSchema.from_json(self.path / "schema.json")
        self._custom_dataset_item_class = (
            create_custom_dataset_item_class_from_dataset_schema(self.dataset_schema)
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

    def open_tables(
        self, names: Optional[list[str]] = None
    ) -> dict[str, lancedb.db.LanceTable]:
        """Open dataset tables with LanceDB.

        Args:
            names (list[str], optional): Table names to open. Default is None.

        Returns:
            dict[str, lancedb.db.LanceTable]: Dataset tables
        """
        ds = self._connect()

        ds_tables: dict[str, lancedb.db.LanceTable] = defaultdict(dict)

        for table_name in self.dataset_schema.schemas.keys():
            if names is None or table_name in names:
                ds_tables[table_name] = ds.open_table(table_name)

        return ds_tables

    def open_table(self, name) -> lancedb.db.LanceTable:
        """Open dataset table with LanceDB.

        Returns:
            lancedb.db.LanceTable: Dataset table
        """
        ds = self._connect()

        for table_name in self.dataset_schema.schemas.keys():
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
        select_schemas: Optional[list[str]] = None,
    ) -> dict[str, dict[str, dict[str, LanceModel]]]:
        sql_ids = f"('{ids[0]}')" if len(ids) == 1 else tuple(ids)

        # Load tables
        ds_tables = self.open_tables(select_schemas)

        # Load items data from the tables
        data_dict: dict[str, dict[str, Union[LanceModel, list[LanceModel]]]] = {
            id: {} for id in ids
        }
        for table_name, table in ds_tables.items():
            is_item_table = table_name == _SchemaGroup.ITEM.value
            item_id_field = "id" if is_item_table else "item_id"
            if not is_item_table:
                is_collection = (
                    self.dataset_schema.relations[_SchemaGroup.ITEM.value][table_name]
                    == SchemaRelation.ONE_TO_MANY
                )
            table_schema = self.dataset_schema.schemas[table_name]

            lance_query = self._search_values_by_field_in_table(
                table, item_id_field, sql_ids
            )
            pydantic_table = _lance_query_to_pydantic(lance_query, table_schema)

            for row in pydantic_table:
                id = row.id if is_item_table else row.item_id
                if is_item_table:
                    data_dict[id].update(row)
                elif is_collection:
                    if table_name not in data_dict[id]:
                        data_dict[id][table_name] = []
                    data_dict[id][table_name].append(row)
                else:
                    data_dict[id][table_name] = row

        # Raise error if some ids are not found
        ids_not_found = [id for id in ids if len(data_dict[id]) == 0]
        if len(ids_not_found) > 0:
            raise ValueError(
                f"Ids {ids_not_found} not found in {_SchemaGroup.ITEM.value} table"
            )

        return data_dict

    def _read_data(
        self,
        ids: list[str],
        select_schema_groups: Optional[list[_SchemaGroup]] = None,
        select_schemas_per_group: Optional[dict[_SchemaGroup, list[str]]] = None,
    ) -> list[DatasetItem]:  # type: ignore
        if select_schema_groups or select_schemas_per_group:
            select_schemas = []
        else:
            select_schemas = None

        if select_schema_groups:
            for schema_group in select_schema_groups:
                if schema_group not in _SchemaGroup:
                    raise ValueError(f"Schema group {schema_group} not found")
                else:
                    select_schemas.extend(self.dataset_schema._groups[schema_group])
        if select_schemas_per_group:
            for schema_group, schemas in select_schemas_per_group.items():
                if schema_group not in _SchemaGroup:
                    raise ValueError(f"Schema group {schema_group} not found")
                elif select_schema_groups and schema_group in select_schema_groups:
                    raise ValueError(
                        f"Schema group {schema_group} is in both select_schema_groups "
                        "and select_schemas_per_group"
                    )
                else:
                    select_schemas.extend(schemas)

        data_dict = self._read_items_data(ids, select_schemas)

        if select_schemas is not None and _SchemaGroup.ITEM.value not in select_schemas:
            for id in ids:
                data_dict[id].update({"id": id})

        if select_schemas is not None:
            custom_dataset_item = create_sub_dataset_item(
                self._CustomDatasetItem, select_schemas
            )
        else:
            custom_dataset_item = self._CustomDatasetItem

        dataset_items = [custom_dataset_item(**data_dict[id]) for id in ids]

        return dataset_items

    def _read_schema_group_data(
        self,
        ids: list[str],
        group: _SchemaGroup,
        select_schemas: Optional[list[str]] = None,
    ) -> list[DatasetItem]:
        if select_schemas:
            select_schemas_per_group = {
                group: [
                    DatasetSchema.format_table_name(schema) for schema in select_schemas
                ]
            }
            return self._read_data(ids, None, select_schemas_per_group)
        return self._read_data(ids, [group], None)

    def _get_data(
        self,
        offset: int,
        limit: int,
        select_schema_groups: Optional[list[_SchemaGroup]] = None,
        select_schemas_per_group: Optional[dict[_SchemaGroup, list[str]]] = None,
    ) -> list[DatasetItem]:
        """Get items from dataset.

        Args:
            offset (int): Offset
            limit (int): Limit
            select_schema_groups (list[str], optional): Schema groups to read
            select_schemas_per_group (list[str], optional): Tables to read per group

        Returns:
            list[DatasetItem]: Dataset items
        """
        if select_schema_groups or select_schemas_per_group:
            select_schemas = []
        else:
            select_schemas = None

        if select_schema_groups:
            for schema_group in select_schema_groups:
                if schema_group not in _SchemaGroup:
                    raise ValueError(f"Schema group {schema_group} not found")
                else:
                    select_schemas.extend(self.dataset_schema._groups[schema_group])
        if select_schemas_per_group:
            for schema_group, schemas in select_schemas_per_group.items():
                if schema_group not in _SchemaGroup:
                    raise ValueError(f"Schema group {schema_group} not found")
                elif select_schema_groups and schema_group in select_schema_groups:
                    raise ValueError(
                        f"Schema group {schema_group} is in both select_schema_groups "
                        "and select_schemas_per_group"
                    )
                else:
                    select_schemas.extend(schemas)

        item_table = self.open_table(_SchemaGroup.ITEM.value).to_lance()  # noqa: F841
        select_item = (
            select_schemas is None or _SchemaGroup.ITEM.value in select_schemas
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
                item_models[row["id"]] = self.dataset_schema.schemas[
                    _SchemaGroup.ITEM.value
                ](**row)
                ids.append(row["id"])
            else:
                ids.append(row["id"])

        data_dict = self._read_items_data(
            ids,
            [
                schema
                for schema in self.dataset_schema.schemas
                if schema != _SchemaGroup.ITEM.value
                and (select_schemas is None or schema in select_schemas)
            ],
        )

        if select_schemas is not None:
            custom_dataset_item = create_sub_dataset_item(
                self._CustomDatasetItem, select_schemas
            )
        else:
            custom_dataset_item = self._CustomDatasetItem

        dataset_items = []
        for id in data_dict.keys():
            if select_item:
                data_dict[id].update(item_models.pop(id))
                dataset_items.append(custom_dataset_item(**data_dict[id]))
            else:
                data_dict[id].update({"id": id})
                dataset_items.append(custom_dataset_item(**data_dict[id]))

        return dataset_items

    def _get_schema_group_data(
        self,
        offset: int,
        limit: int,
        group: _SchemaGroup,
        select: Optional[list[str]] = None,
    ) -> list[DatasetItem]:
        if select:
            select_schemas_per_group = {
                group: [DatasetSchema.format_table_name(table) for table in select]
            }
            return self._get_data(offset, limit, None, select_schemas_per_group)
        return self._get_data(offset, limit, [group], None)

    def read_items(
        self,
        ids: list[str],
    ) -> list[DatasetItem]:  # type: ignore
        """Read items from dataset.

        Args:
            ids (list[str]): Item ids
            select_schema_groups (list[str], optional): Schema groups to read
            select_schemas_per_group (list[str], optional): Tables to read per group
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
        return self._read_schema_group_data(ids, _SchemaGroup.VIEW, select)

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
        return self._get_schema_group_data(offset, limit, _SchemaGroup.VIEW, select)

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
        return self._read_schema_group_data(ids, _SchemaGroup.OBJECT, select)

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
        return self._get_schema_group_data(offset, limit, _SchemaGroup.OBJECT, select)

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
        return self._read_schema_group_data(ids, _SchemaGroup.EMBEDDING, select)

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
        return self._get_schema_group_data(
            offset, limit, _SchemaGroup.EMBEDDING, select
        )

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
