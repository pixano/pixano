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

from pixano.core import Image
from pixano.core.types.registry import _TABLE_TYPE_REGISTRY
from pixano.data.dataset.dataset_features_values import DatasetFeaturesValues
from pixano.data.dataset.dataset_info import DatasetInfo
from pixano.data.dataset.dataset_item import DatasetItem, TableGroup
from pixano.data.dataset.dataset_schema import DatasetSchema
from pixano.data.dataset.dataset_stat import DatasetStat

DEFAULT_DB_PATH = "db"


class Dataset(BaseModel):
    """Dataset

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
        """Initialize dataset

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

    @property
    def _media_dir(self) -> Path | S3Path:
        """Return dataset media directory

        Returns:
            Path | S3Path: Dataset media directory
        """

        return self.path / "media"

    @property
    def _db_path(self) -> Path | S3Path:
        """Return dataset db path

        Returns:
            Path | S3Path: Dataset db path
        """
        if isinstance(self.path, S3Path):
            return self.path.as_uri() + "/" + DEFAULT_DB_PATH

        return self.path / DEFAULT_DB_PATH

    def _connect(self) -> lancedb.db.DBConnection:
        """Connect to dataset with LanceDB

        Returns:
            lancedb.db.DBConnection: Dataset LanceDB connection
        """

        return lancedb.connect(self._db_path)

    def open_tables(self) -> dict[TableGroup, dict[str, lancedb.db.LanceTable]]:
        """Open dataset tables with LanceDB

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
        """Open dataset table with LanceDB

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

    def _get_items_data(
        self,
        ids: list[str],
        select_table_groups: list[TableGroup] = None,
        select_tables_per_group: Optional[dict[TableGroup, list[str]]] = None,
    ) -> dict[str, dict[str, dict[str, LanceModel]]]:
        sql_ids = f"('{ids[0]}')" if len(ids) == 1 else tuple(ids)

        # Reload schema
        self.dataset_schema.load()

        # Load tables
        ds_tables = self.open_tables()

        # Load items data from the tables
        data_dict: dict[str, dict[str, dict[str, LanceModel]]] = {id: {} for id in ids}
        for group_name, table_group in ds_tables.items():
            item_id_field = "id" if group_name == TableGroup.ITEM else "item_id"

            if (
                select_table_groups
                and select_tables_per_group
                and group_name in select_table_groups
                and group_name in select_tables_per_group
            ):
                raise ValueError(
                    f"Table group {group_name} is in both select_table_groups and select_tables_per_group"
                )
            elif (not select_table_groups and not select_tables_per_group) or (
                select_table_groups and group_name in select_table_groups
            ):
                tables_to_read = table_group.keys()
            elif select_tables_per_group and group_name in select_tables_per_group:
                tables_to_read = select_tables_per_group[group_name]
            else:
                tables_to_read = []

            for table_name in tables_to_read:
                if table_name not in table_group:
                    raise ValueError(
                        f"Table {table_name} not found in {group_name.value} table group"
                    )
                table = table_group[table_name]
                table_type = _TABLE_TYPE_REGISTRY[
                    self.dataset_schema.schemas[group_name.value][table_name]
                ]

                lance_query = self._search_values_by_field_in_table(
                    table, item_id_field, sql_ids
                )
                pydantic_table = lance_query.to_pydantic(table_type)

                for row in pydantic_table:
                    row_id = row.id if group_name == TableGroup.ITEM else row.item_id
                    if group_name.value not in data_dict[row_id].keys():
                        data_dict[row_id][group_name.value] = {}
                    data_dict[row_id][group_name.value][table_name] = row

        # Raise error if some ids are not found
        ids_not_found = [id for id in ids if len(data_dict[id]) == 0]
        if len(ids_not_found) > 0:
            raise ValueError(
                f"Ids {ids_not_found} not found in {TableGroup.ITEM.value} table"
            )

        return data_dict

    def read_items(
        self,
        item_ids: list[str],
        select_table_groups: Optional[list[TableGroup | str]] = None,
        select_tables_per_group: Optional[dict[TableGroup | str, list[str]]] = None,
    ) -> list[DatasetItem]:  # type: ignore
        """Read items from dataset.

        Args:
            ids (list[str]): Item ids
            select_table_groups (list[str], optional): Table groups to read
            select_tables_per_group (list[str], optional): Tables to read per group
        Returns:
            list[DatasetItem] | DatasetItem: Dataset items
        """

        if select_table_groups:
            select_table_groups = [
                TableGroup(table_group) if isinstance(table_group, str) else table_group
                for table_group in select_table_groups
            ]
            if TableGroup.ITEM not in select_table_groups:
                select_table_groups.append(TableGroup.ITEM)
        else:
            if select_tables_per_group:
                select_table_groups = [TableGroup.ITEM]

        data_dict = self._get_items_data(
            item_ids, select_table_groups, select_tables_per_group
        )

        dataset_items = [DatasetItem(id=id, **data_dict[id]) for id in item_ids]

        return dataset_items

    def read_item(
        self,
        item_id: str,
        select_table_groups: Optional[list[TableGroup | str]] = None,
        select_tables_per_group: Optional[dict[TableGroup | str, list[str]]] = None,
    ) -> DatasetItem:  # type: ignore
        """Read one item from dataset. Look :func:`read_items` for more details."""

        if not isinstance(item_id, str):
            raise ValueError("id should be a string")

        return self.read_items(
            [item_id],
            select_table_groups,
            select_tables_per_group,
        )[0]

    def get_items(
        self,
        offset: int,
        limit: int,
        select_table_groups: Optional[list[TableGroup | str]] = None,
        select_tables_per_group: Optional[dict[TableGroup | str, list[str]]] = None,
    ) -> list[DatasetItem]:  # type: ignore
        """Get items from dataset

        Args:
            offset (int): Offset
            limit (int): Limit
            select_table_groups (list[str], optional): Table groups to read
            select_tables_per_group (list[str], optional): Tables to read per group
        Returns:
            list[DatasetItem]: Dataset items
        """

        # pylint: disable=unused-variable
        item_table = self.open_table(TableGroup.ITEM.value).to_lance()
        item_rows = (
            duckdb.query(
                f"SELECT * FROM item_table ORDER BY len(id), id LIMIT {limit} OFFSET {offset}"
            )
            .to_arrow_table()
            .to_pylist()
        )

        items_models = [
            _TABLE_TYPE_REGISTRY[
                self.dataset_schema.schemas[TableGroup.ITEM.value][
                    TableGroup.ITEM.value
                ]
            ](**row)
            for row in item_rows
        ]

        if select_table_groups:
            select_table_groups = [
                TableGroup(table_group) if isinstance(table_group, str) else table_group
                for table_group in select_table_groups
                if TableGroup(table_group) != TableGroup.ITEM
            ]
        if select_tables_per_group:
            select_tables_per_group = {
                (
                    TableGroup(table_group)
                    if isinstance(table_group, str)
                    else table_group
                ): select_tables
                for table_group, select_tables in select_tables_per_group.items()
                if TableGroup(table_group) != TableGroup.ITEM
            }

        data_dict = self._get_items_data(
            [item.id for item in items_models],
            select_table_groups,
            select_tables_per_group,
        )

        for item in items_models:
            data_dict[item.id][TableGroup.ITEM.value] = {}
            data_dict[item.id][TableGroup.ITEM.value][TableGroup.ITEM.value] = item

        dataset_items = [DatasetItem(id=id, **data_dict[id]) for id in data_dict.keys()]

        return dataset_items

    def get_item(
        self,
        num_item: int,
        select_table_groups: Optional[list[TableGroup | str]] = None,
        select_tables_per_group: Optional[dict[TableGroup | str, list[str]]] = None,
    ) -> DatasetItem:  # type: ignore
        """Get items from dataset

        Args:
            num_item (int): Offset
            select_table_groups (list[str], optional): Table groups to read
            select_tables_per_group (list[str], optional): Tables to read per group
        Returns:
            list[DatasetItem]: Dataset items
        """

        return self.get_items(
            num_item, 1, select_table_groups, select_tables_per_group
        )[0]
