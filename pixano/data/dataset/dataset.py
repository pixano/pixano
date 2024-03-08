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

import lancedb
from lancedb.pydantic import LanceModel
from pydantic import BaseModel, ConfigDict
from s3path import S3Path

from pixano.core.types.registry import _TYPE_REGISTRY
from pixano.data.dataset.dataset_item import TableGroup
from pixano.data.dataset.dataset_features_values import DatasetFeaturesValues
from pixano.data.dataset.dataset_item import DatasetItem
from pixano.data.dataset.dataset_schema import DatasetSchema
from pixano.data.dataset.dataset_stat import DatasetStat
from pixano.data.dataset.dataset_summary import DatasetSummary

DEFAULT_DB_PATH = "db"

class Dataset(BaseModel):
    """Dataset

    Attributes:
        path (Path | S3Path): Dataset path
        summary (DatasetSummary, optional): Dataset summary
        dataset_schema (DatasetSchema, optional): Dataset schema
        features_values (DatasetFeaturesValues, optional): Dataset features values
        stats (list[DatasetStat], optional): Dataset stats
        thumbnail (str, optional): Dataset thumbnail base 64 URL
    """
    path: Path | S3Path
    # summary: Optional[DatasetSummary] = None
    dataset_schema: Optional[DatasetSchema] = None
    # features_values: Optional[DatasetFeaturesValues] = None
    # stats: Optional[list[DatasetStat]] = None
    # thumbnail: Optional[str] = None
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

        summary_file = path / "summary.json"
        schema_file = path / "schema.json"
        features_values_file = path / "features_values.json"
        stats_file = path / "stats.json"
        thumb_file = path / "preview.png"

        super().__init__(
            path=path,
            #summary=DatasetSummary.from_json(summary_file),
            dataset_schema=DatasetSchema.from_json(schema_file),
            #features_values=DatasetFeaturesValues.from_json(features_values_file),
            #stats=DatasetStat.from_json(stats_file) if stats_file.is_file() else None,
            # thumbnail=(
            #     Image(uri=thumb_file.absolute().as_uri()).url
            #     if thumb_file.is_file()
            #     else None
            # ),
        )
    
    @property
    def _media_dir(self) -> Path | S3Path:
        """Return dataset media directory

        Returns:
            Path | S3Path: Dataset media directory
        """

        return self.path / "media"
    

    def _connect(self) -> lancedb.db.DBConnection:
        """Connect to dataset with LanceDB

        Returns:
            lancedb.db.DBConnection: Dataset LanceDB connection
        """

        if isinstance(self.path, S3Path):
            return lancedb.connect(self.path.as_uri() + "/" + DEFAULT_DB_PATH)
        return lancedb.connect(self.path / DEFAULT_DB_PATH)


    def open_tables(self) -> dict[TableGroup, dict[str, lancedb.db.LanceTable]]:
        """Open dataset tables with LanceDB

        Returns:
            dict[str, dict[str, lancedb.db.LanceTable]]: Dataset tables
        """

        ds = self._connect()

        ds_tables: dict[str, dict[TableGroup, lancedb.db.LanceTable]] = defaultdict(dict)

        for table_group, tables in self.dataset_schema.schemas.items():
            for table_name in tables.keys():
                ds_tables[TableGroup(table_group)][table_name] = ds.open_table(table_name)

        return ds_tables


    def read_items(
        self,
        ids: list[str],
        select_table_groups: Optional[list[TableGroup | str]] = None,
        select_tables_per_group: Optional[dict[TableGroup | str, list[str]]] = None,
    ) -> list[DatasetItem]: # type: ignore
        """Read items from dataset.

        Args:
            ids (list[str]): Item ids
            select_table_groups (list[str], optional): Table groups to read
            select_tables_per_group (list[str], optional): Tables to read per group
        Returns:
            list[DatasetItem] | DatasetItem: Dataset items
        """

        if select_table_groups:
            select_table_groups = [TableGroup(table_group.lower()) if isinstance(table_group, str) else table_group for table_group in select_table_groups]

        if select_tables_per_group:
            select_tables_per_group = {TableGroup(table_group.lower()) if isinstance(table_group, str) else table_group: [table.lower() for table in tables] for table_group, tables in select_tables_per_group.items()}

        sql_ids = f"('{ids[0]}')" if len(ids) == 1 else tuple(ids)

        # Reload schema
        self.dataset_schema.load()

        # Load tables
        ds_tables = self.open_tables()

        # Load PyArrow item from tables
        pydantic_items: dict[TableGroup, dict[str, list[LanceModel]]] = defaultdict(dict)

        # Load PyArrow item from items table
        lance_query = (
            ds_tables[TableGroup.ITEM][TableGroup.ITEM.value].search().where(
                f"id in {sql_ids}",
            ).limit(None)
        )

        item_type = _TYPE_REGISTRY[self.dataset_schema.schemas[TableGroup.ITEM.value][TableGroup.ITEM.value]]
        pydantic_items[TableGroup.ITEM][TableGroup.ITEM.value] = lance_query.to_pydantic(item_type)

        ids_not_found = []
        for id in ids:
            if all(id != pydantic_item.id for pydantic_item in pydantic_items[TableGroup.ITEM][TableGroup.ITEM.value]):
                ids_not_found.append(id)
        if len(ids_not_found) > 0:
            raise ValueError(f"Ids {ids_not_found} not found in {TableGroup.ITEM.value} table")

        for table_group in ds_tables.keys():
            if table_group == TableGroup.ITEM:
                continue
            
            if (select_table_groups and 
               select_tables_per_group and 
               table_group in select_table_groups and 
               table_group in select_tables_per_group
            ):
                raise ValueError(f"Table group {table_group} is in both select_table_groups and select_tables_per_group")
            elif (not select_table_groups and not select_tables_per_group) or (select_table_groups and table_group in select_table_groups):
                tables_to_read = ds_tables[table_group].keys()
            elif select_tables_per_group and table_group in select_tables_per_group:
                tables_to_read = select_tables_per_group[table_group]
            else:
                tables_to_read = []

            for table_name in tables_to_read:
                if table_name not in ds_tables[table_group]:
                    raise ValueError(f"Table {table_name} not found in {table_group.value} table group")
                table = ds_tables[table_group][table_name]
        
                lance_query = table.search().where(
                    f"item_id in {sql_ids}",
                ).limit(None)
                table_type = _TYPE_REGISTRY[self.dataset_schema.schemas[table_group.value][table_name]]
                pydantic_items[table_group][table_name] = lance_query.to_pydantic(table_type)
        
        data_dict: dict[str, dict[str, dict[str, LanceModel]]] = {}
        for table_group, tables in pydantic_items.items():
            for table_name, table in tables.items():
                for row in table:
                    id = row.id if table_group == TableGroup.ITEM else row.item_id
                    if id not in data_dict:
                        data_dict[id] = {}
                    if table_group.value not in data_dict[id]:
                        data_dict[id][table_group.value] = {}
                    data_dict[id][table_group.value][table_name] = row
        
        dataset_items = [
            DatasetItem(id=id, **data_dict[id])
            for id in ids
        ]
        
        return dataset_items
    
    def read_item(self, id: str, select_table_groups: Optional[list[TableGroup | str]] = None, select_tables_per_group: Optional[dict[TableGroup | str, list[str]]] = None) -> DatasetItem: # type: ignore
        """Read one item from dataset. Look :func:`read_items` for more details."""
        if not isinstance(id, str):
            raise ValueError("id should be a string")

        return self.read_items([id], select_table_groups, select_tables_per_group)[0]
