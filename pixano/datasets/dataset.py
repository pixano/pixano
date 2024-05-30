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

import duckdb
import lancedb
from lancedb.pydantic import LanceModel
from lancedb.query import LanceQueryBuilder
import pyarrow as pa
from pydantic import ConfigDict
from s3path import S3Path

from .dataset_features_values import DatasetFeaturesValues
from .dataset_library import DatasetLibrary
from .dataset_table import DatasetTable
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
    FEATURES_VALUES_FILE: str = "features_values.json"
    STAT_FILE: str = "stats.json"
    THUMB_FILE: str = "preview.png"

    path: Path | S3Path
    info: DatasetLibrary | None = None
    dataset_schema: DatasetSchema | None = None
    features_values: DatasetFeaturesValues | None = None
    stats: list[DatasetStat] | None = None
    thumbnail: str | None = None
    # Allow arbitrary types because of S3 Path
    model_config = ConfigDict(arbitrary_types_allowed=True)

    def __init__(self, path: Path | S3Path, info: DatasetLibrary | None = None):
        """Initialize dataset.

        Args:
            path (Path | S3Path): Dataset path
            info (DatasetInfo, optional): Dataset info. Default is None.
        """
        info_file = path / self.INFO_FILE
        schema_file = path / self.SCHEMA_FILE
        features_values_file = path / self.FEATURES_VALUES_FILE
        stats_file = path / self.STAT_FILE
        thumb_file = path / self.THUMB_FILE

        self.path = path
        self.info = DatasetLibrary.from_json(info_file)
        self.dataset_schema = DatasetSchema.from_json(schema_file)
        self.features_values = DatasetFeaturesValues.from_json(features_values_file)
        self.stats = DatasetStat.from_json(stats_file) if stats_file.is_file() else None
        self.thumbnail = thumb_file

        self._custom_dataset_item_class = (
            create_custom_dataset_item_class_from_dataset_schema(self.dataset_schema)
        )
        self._db_connection = self._connect()

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
        self, names: list[str] | None = None
    ) -> dict[str, lancedb.db.LanceTable]:
        """Open dataset tables with LanceDB.

        Args:
            names (list[str] | None, optional): Table names to open. Default is None.

        Returns:
            dict[str, lancedb.db.LanceTable]: Dataset tables
        """
        ds_tables: dict[str, lancedb.db.LanceTable] = defaultdict(dict)

        for table_name in self.dataset_schema.schemas.keys():
            if names is None or table_name in names:
                ds_tables[table_name] = self._db_connection.open_table(table_name)

        return ds_tables

    def open_table(self, name) -> lancedb.db.LanceTable:
        """Open dataset table with LanceDB.

        Returns:
            lancedb.db.LanceTable: Dataset table
        """
        for table_name in self.dataset_schema.schemas.keys():
            if table_name == name:
                return self._db_connection.open_table(table_name)

        raise ValueError(f"Table {name} not found in dataset")

    def _search_values_by_field_in_table(
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

    def _read_items_data(
        self,
        ids: list[str],
        select_schemas: list[str] | None = None,
    ) -> dict[str, dict[str, dict[str, LanceModel]]]:
        sql_ids = f"('{ids[0]}')" if len(ids) == 1 else tuple(ids)

        # Load tables
        ds_tables = self.open_tables(select_schemas)

        # Load items data from the tables
        data_dict: dict[str, dict[str, LanceModel | list[LanceModel]]] = {
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
        select_schema_groups: list[_SchemaGroup] | None = None,
        select_schemas_per_group: dict[_SchemaGroup, list[str]] | None = None,
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
        select_schemas: list[str] | None = None,
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
        select_schema_groups: list[_SchemaGroup] | None = None,
        select_schemas_per_group: dict[_SchemaGroup, list[str]] | None = None,
    ) -> list[DatasetItem]:
        """Get items from dataset.

        Args:
            offset (int): Offset
            limit (int): Limit
            select_schema_groups (list[_SchemaGroup] | None, optional): Schema groups
                to read. Default is None.
            select_schemas_per_group (dict[_SchemaGroup, list[str]] | None, optional):
                Tables to read per group. Default is None.

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
        select: list[str] | None = None,
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

    def get_all_ids(
        self, table_name: str | None = _SchemaGroup.ITEM.value
    ) -> list[str]:
        """Get all ids from a table.

        Args:
            table_name (str | None, optional): table to look for ids.
                Defaults to _SchemaGroup.ITEM.value.

        Returns:
            list[str]: list of ids.
        """
        query = (
            self.open_table(table_name).search().select(["id"]).limit(None).to_arrow()
        )
        return sorted(row.as_py() for row in query["id"])

    def read_views(
        self, ids: list[str], select: list[str] | None = None
    ) -> list[DatasetItem]:  # type: ignore
        """Read views from dataset.

        Args:
            ids (list[str]): Item ids.
            select (list[str] | None, optional): Views to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items.
        """
        return self._read_schema_group_data(ids, _SchemaGroup.VIEW, select)

    def read_view(self, id: str, select: list[str] | None = None) -> DatasetItem:
        """Read view from dataset.

        Args:
            id (str): Item id.
            select (list[str] | None, optional): Views to read. Default is None.

        Returns:
            DatasetItem: Dataset item
        """
        return self.read_views([id], select)[0]

    def get_views(
        self,
        offset: int,
        limit: int,
        select: list[str] | None = None,
    ) -> list[DatasetItem]:
        """Get views from dataset.

        Args:
            offset (int): Offset
            limit (int): Limit
            select (list[str] | None, optional): Views to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._get_schema_group_data(offset, limit, _SchemaGroup.VIEW, select)

    def get_view(
        self,
        idx: int,
        select: list[str] | None = None,
    ) -> DatasetItem:
        """Get view from dataset.

        Args:
            idx (int): Index.
            select (list[str] | None, optional): Views to read. Default is None.

        Returns:
            DatasetItem: Dataset items
        """
        return self.get_views(idx, 1, select)[0]

    def read_objects(
        self, ids: list[str], select: list[str] | None = None
    ) -> list[DatasetItem]:  # type: ignore
        """Read objects from dataset.

        Args:
            ids (list[str]): Item ids.
            select (list[str] | None, optional): Objects to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._read_schema_group_data(ids, _SchemaGroup.OBJECT, select)

    def read_object(self, id: str, select: list[str] | None = None) -> DatasetItem:
        """Read object from dataset.

        Args:
            id (str): Item id.
            select (list[str] | None, optional): Objects to read. Default is None.

        Returns:
            DatasetItem: Dataset item
        """
        return self.read_objects([id], select)[0]

    def get_objects(
        self,
        offset: int,
        limit: int,
        select: list[str] | None = None,
    ) -> list[DatasetItem]:
        """Get objects from dataset.

        Args:
            offset (int): Offset
            limit (int): Limit
            select (list[str]  | None, optional): Objects to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._get_schema_group_data(offset, limit, _SchemaGroup.OBJECT, select)

    def get_object(
        self,
        idx: int,
        select: list[str] | None = None,
    ) -> DatasetItem:
        """Get object from dataset.

        Args:
            idx (int): Index.
            select (list[str] | None, optional): Objects to read. Default is None.

        Returns:
            DatasetItem: Dataset items
        """
        return self.get_objects(idx, 1, select)[0]

    def read_embeddings(
        self, ids: list[str], select: list[str] | None = None
    ) -> list[DatasetItem]:  # type: ignore
        """Read embeddings from dataset.

        Args:
            ids (list[str]): Item ids.
            select (list[str] | None, optional): Embeddings to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._read_schema_group_data(ids, _SchemaGroup.EMBEDDING, select)

    def read_embedding(self, id: str, select: list[str] | None = None) -> DatasetItem:
        """Read embedding from dataset.

        Args:
            id (str): Item id.
            select (list[str] | None, optional): Embeddings to read. Default is None.

        Returns:
            DatasetItem: Dataset item
        """
        ##TMP no embeddings now
        return None  # self.read_embeddings([id], select)[0]

    def get_embeddings(
        self,
        offset: int,
        limit: int,
        select: list[str] | None = None,
    ) -> list[DatasetItem]:
        """Get embeddings from dataset.

        Args:
            offset (int): Offset
            limit (int): Limit
            select (list[str] | None, optional): Embeddings to read. Default is None.

        Returns:
            list[DatasetItem]: Dataset items
        """
        return self._get_schema_group_data(
            offset, limit, _SchemaGroup.EMBEDDING, select
        )

    def get_embedding(
        self,
        idx: int,
        select: list[str] | None = None,
    ) -> DatasetItem:
        """Get embedding from dataset.

        Args:
            idx (int): Index.
            select (list[str] | None, optional): Embeddings to read. Default is None.

        Returns:
            DatasetItem: Dataset items
        """
        return self.get_embedding(idx, 1, select)[0]

    def save_item(
        self,
        item  #TODO it's a FrontDatasetItem, but we don't really need the class here
    ):
        """Save dataset item features and objects

        #TODO Note: for now, we don't manage alteration of table schema
        (anyway front doesn't allow such modification right now)

        Args:
            item (DatasetItem): Item to save
        """
        #TODO convert FrontDatasetItem to DatasetItem (??? really needed ? -> no, or maybe if we use CRUD API finally)
        # we could already use read_objects fct, but here we use scanner directly, which I presume avoid some 
        # ---things that may come handy if we need to alter table schema:
        # print(self._custom_dataset_item_class)
        # print(item)
        # print("------------------------")
        # print(self._read_items_data([item.id]))  # <-- stored item in tables
        # print(self.dataset_schema)

        # Local utility function to convert objects to pyarrow format
        # also adapt features to table format
        def convert_objects_to_pyarrow(table, objs):
            # Convert objects to PyArrow
            # adapt features
            for obj in objs:
                if "features" in obj:
                    for feat in obj['features'].values():
                        # TODO coerce to type feat["dtype"] (need mapping dtype string to type)
                        obj[feat['name']] = feat['value']

            return pa.Table.from_pylist(
                # [obj.to_pyarrow() for obj in objs],
                objs,
                schema=table.schema,
            )

        def convert_item_to_pyarrow(table, item):
            # Convert item to PyArrow
            pyarrow_item = {}

            # ID
            pyarrow_item["id"] = item.id
            pyarrow_item["split"] = item.split

            # Features
            if item.features is not None:
                for feat in item.features.values():
                    # TODO coerce to type feat["dtype"] (need mapping dtype string to type)
                    pyarrow_item[feat['name']] = feat['value']

            return pa.Table.from_pylist(
                [pyarrow_item],
                schema=table.schema,
            )

        # UPDATE items features
        item_table = self.open_table("item")
        item_table.delete(f"id in ('{item.id}')")
        item_table.add(convert_item_to_pyarrow(item_table, item))

        # Objects
        add_ids = []
        update_ids = []

        # TMP: use table "objects"  # TODO : what if not "objects" ?
        obj_table = self.open_table("objects")

        str_obj_ids = [f"'{obj['id']}'" for obj in item.objects]
        if str_obj_ids:
            str_obj_ids = "(" + ", ".join(str_obj_ids) + ")"
            scanner = obj_table.to_lance().scanner(filter=f"id in {str_obj_ids}")
            update_objs = scanner.to_table()
            update_ids = update_objs.to_pydict()["id"]
            add_ids = [obj['id'] for obj in item.objects if obj['id'] not in update_ids]
            scanner = obj_table.to_lance().scanner(filter=f"id not in {str_obj_ids}")
            delete_objs = scanner.to_table()
            delete_ids = delete_objs.to_pydict()["id"]
        else:
            # no objects in item.objects, it means we may have to delete existing objs
            delete_objs = obj_table.to_lance().scanner().to_table()
            delete_ids = delete_objs.to_pydict()["id"]

        if add_ids:
            new_objs = [obj for obj in item.objects if obj.id in add_ids]
            obj_table.add(convert_objects_to_pyarrow(obj_table, new_objs))

        if update_ids:
            update_objs = [obj for obj in item.objects if obj['id'] in update_ids]
            str_obj_ids = [f"'{id}'" for id in update_ids]
            str_obj_ids = "(" + ", ".join(str_obj_ids) + ")"
            obj_table.delete(f"id in {str_obj_ids}")
            obj_table.add(convert_objects_to_pyarrow(obj_table, update_objs))

        if delete_ids:
            str_obj_ids = [f"'{id}'" for id in delete_ids]
            str_obj_ids = "(" + ", ".join(str_obj_ids) + ")"
            obj_table.delete(f"id in {str_obj_ids}")

        # Clear change history to prevent dataset from becoming too large
        obj_table.to_lance().cleanup_old_versions()
        # TODO: ther is a lancedb utility to "reshape" table after updates, to keep it "clean"
        # Maybe we should use it ?

    @staticmethod
    def find(
        dataset_id: str,
        directory: Path | S3Path,
    ) -> "Dataset":
        """Find Dataset in directory.

        Args:
            dataset_id (str): Dataset ID.
            directory (Path | S3Path): Directory to search in.

        Returns:
            Dataset: The found dataset.
        """
        # Browse directory
        for json_fp in directory.glob("*/info.json"):
            info = DatasetLibrary.from_json(json_fp)
            if info.id == dataset_id:
                # Return dataset
                return Dataset(json_fp.parent)
        return None
