# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import shutil
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, cast, overload

import lancedb
import polars as pl
import pyarrow as pa
from lancedb.common import DATA
from lancedb.table import LanceTable
from pydantic import ConfigDict

from pixano.datasets.queries import TableQueryBuilder
from pixano.datasets.utils.errors import DatasetAccessError, DatasetPaginationError
from pixano.datasets.utils.integrity import IntegrityCheck, check_table_integrity, handle_integrity_errors
from pixano.features import SchemaGroup, Source, ViewEmbedding, is_view_embedding
from pixano.features.schemas.base_schema import BaseSchema
from pixano.utils.python import to_sql_list

from .dataset_features_values import DatasetFeaturesValues
from .dataset_info import DatasetInfo
from .dataset_schema import DatasetItem, DatasetSchema, SchemaRelation
from .dataset_stat import DatasetStatistic


if TYPE_CHECKING:
    from ..features import (
        Annotation,
        AnnotationRef,
        BaseSchema,
        Embedding,
        EmbeddingRef,
        Entity,
        EntityRef,
        Item,
        ItemRef,
        SchemaRef,
        SourceRef,
        View,
        ViewRef,
    )


def _validate_ids_and_limit_and_skip(ids: list[str] | None, limit: int | None, skip: int = 0) -> None:
    if ids is None and limit is None:
        raise DatasetPaginationError("limit must be set if ids is None")
    elif ids is not None and limit is not None:
        raise DatasetPaginationError("ids and limit cannot be set at the same time")
    elif ids is not None and (not isinstance(ids, list) or not all(isinstance(i, str) for i in ids)):
        raise DatasetPaginationError("ids must be a list of strings")
    elif limit is not None and (not isinstance(limit, int) or limit < 0) or not isinstance(skip, int) or skip < 0:
        raise DatasetPaginationError("limit and skip must be positive integers")


def _validate_ids_item_ids_and_limit_and_skip(
    ids: list[str] | None, limit: int | None, skip: int = 0, item_ids: list[str] | None = None
) -> None:
    if ids is not None and item_ids is not None:
        raise DatasetPaginationError("ids and item_ids cannot be set at the same time")
    if ids is not None and limit is not None:
        raise DatasetPaginationError("ids and limit cannot be set at the same time")
    elif ids is not None and (not isinstance(ids, list) or not all(isinstance(i, str) for i in ids)):
        raise DatasetPaginationError("ids must be a list of strings")
    elif item_ids is not None and (not isinstance(item_ids, list) or not all(isinstance(i, str) for i in item_ids)):
        raise DatasetPaginationError("item_ids must be a list of strings")
    elif limit is not None and (not isinstance(limit, int) or limit < 1) or not isinstance(skip, int) or skip < 0:
        raise DatasetPaginationError("limit and skip must be positive integers")


def _validate_raise_or_warn(raise_or_warn: Literal["raise", "warn", "none"]):
    if raise_or_warn not in ["raise", "warn", "none"]:
        raise ValueError("raise_or_warn must be 'raise', 'warn' or 'none'")


class Dataset:
    """The Pixano Dataset.

    It is a collection of tables that can be queried and manipulated with LanceDB.

    The tables are defined by the [DatasetSchema][pixano.datasets.DatasetSchema] which allows the dataset to return
    the data in the form of [LanceModel][lancedb.pydantic.LanceModel] instances.

    Attributes:
        path: Path to the dataset.
        info: Dataset info.
        schema: Dataset schema.
        features_values: Dataset features values.
        stats: Dataset statistics.
        thumbnail: Dataset thumbnail base 64 URL.
        media_dir: Path to the media directory.
    """

    # Allow arbitrary types because of S3 Path
    model_config = ConfigDict(arbitrary_types_allowed=True)

    _DB_PATH: str = "db"
    _PREVIEWS_PATH: str = "previews"
    _INFO_FILE: str = "info.json"
    _SCHEMA_FILE: str = "schema.json"
    _FEATURES_VALUES_FILE: str = "features_values.json"
    _STAT_FILE: str = "stats.json"
    _THUMB_FILE: str = "preview.png"

    path: Path
    info: DatasetInfo
    schema: DatasetSchema
    features_values: DatasetFeaturesValues = DatasetFeaturesValues()
    stats: list[DatasetStatistic] = []
    thumbnail: Path
    media_dir: Path

    def __init__(self, path: Path, media_dir: Path | None = None):
        """Initialize the dataset.

        Args:
            path: Path to the dataset.
            media_dir: Path to the media directory.
        """
        self.path = path

        self._info_file = self.path / self._INFO_FILE
        self._schema_file = self.path / self._SCHEMA_FILE
        self._features_values_file = self.path / self._FEATURES_VALUES_FILE
        self._stat_file = self.path / self._STAT_FILE
        self._thumb_file = self.path / self._THUMB_FILE
        self._db_path = self.path / self._DB_PATH

        self.info = DatasetInfo.from_json(self._info_file)
        self.features_values = DatasetFeaturesValues.from_json(self._features_values_file)
        self.stats = DatasetStatistic.from_json(self._stat_file) if self._stat_file.is_file() else []
        self.media_dir = media_dir or self.path / "media"
        self.thumbnail = self._thumb_file
        self.previews_path = self.path / self._PREVIEWS_PATH

        self._db_connection = self._connect()

        self._reload_schema()

    def _move_dataset(self, new_path: Path) -> None:
        """Move dataset to a new path.

        Args:
            new_path: New dataset path.
        """
        if self.media_dir == self.path / "media":
            self.media_dir = new_path / "media"

        self.path.rename(new_path)
        self.path = new_path

        self._db_path = self.path / self._DB_PATH
        self._info_file = self.path / self._INFO_FILE
        self._schema_file = self.path / self._SCHEMA_FILE
        self._features_values_file = self.path / self._FEATURES_VALUES_FILE
        self._stat_file = self.path / self._STAT_FILE
        self._thumb_file = self.path / self._THUMB_FILE
        self._db_connection = self._connect()

    def _copy_dataset(self, new_path: Path) -> None:
        """Copy dataset to a new path.

        Args:
            new_path: New dataset path.
        """
        if self.media_dir == self.path / "media":
            self.media_dir = new_path / "media"

        shutil.copytree(self.path, new_path, dirs_exist_ok=True)  # Fine
        self.path = new_path

        self._db_path = self.path / self._DB_PATH
        self._info_file = self.path / self._INFO_FILE
        self._schema_file = self.path / self._SCHEMA_FILE
        self._features_values_file = self.path / self._FEATURES_VALUES_FILE
        self._stat_file = self.path / self._STAT_FILE
        self._thumb_file = self.path / self._THUMB_FILE
        self._db_connection = self._connect()

    @property
    def id(self) -> str:
        """Return the dataset ID."""
        return self.info.id

    @property
    def num_rows(self) -> int:
        """Return the number of rows in the dataset.

        Returns:
            Number of rows.
        """
        # Return number of rows of item table
        return self.open_table(SchemaGroup.ITEM.value).count_rows()

    def _reload_schema(self) -> None:
        """Reload schema.

        Returns:
            DatasetSchema: Dataset schema.
        """
        self.schema: DatasetSchema = DatasetSchema.from_json(self._schema_file)
        self.dataset_item_model: type[DatasetItem] = DatasetItem.from_dataset_schema(
            self.schema, exclude_embeddings=True
        )

    def _connect(self) -> lancedb.db.DBConnection:
        """Connect to dataset with LanceDB.

        Returns:
            Dataset LanceDB connection.
        """
        return lancedb.connect(self._db_path)

    def create_table(
        self,
        name: str,
        schema: type[BaseSchema],
        relation_item: SchemaRelation,
        data: DATA | None = None,
        mode: str = "create",
        exist_ok: bool = False,
        on_bad_vectors: str = "error",
        fill_value: float = 0.0,
    ) -> LanceTable:
        """Add a table to the dataset.

        Args:
            name: Table name.
            schema: Table schema.
            relation_item: Relation with the `'item'` table (table to item).
            data: Table data.
            mode: Table mode ('create', 'overwrite').
            exist_ok: If True, do not raise an error if the table already exists.
            on_bad_vectors: Raise an error, drop or fill bad vectors ("error", "drop", "fill").
            fill_value: Value to fill bad vectors.

        Returns:
            The table created.
        """
        table = self._db_connection.create_table(
            name=name,
            schema=schema,
            data=data,
            mode=mode,
            exist_ok=exist_ok,
            on_bad_vectors=on_bad_vectors,
            fill_value=fill_value,
            embedding_functions=None,
        )
        self.schema.add_schema(name, schema, relation_item, exist_ok or mode == "overwrite")
        self.schema.to_json(self._schema_file)
        self._reload_schema()
        return table

    def open_tables(self, names: list[str] | None = None, exclude_embeddings: bool = True) -> dict[str, LanceTable]:
        """Open the dataset tables with LanceDB.

        Args:
            names: Table names to open. If None, open all tables.
            exclude_embeddings: Whether to exclude embedding tables from the list.

        Returns:
            Dataset tables.
        """
        tables: dict[str, LanceTable] = defaultdict(dict)

        for name in names if names is not None else self.schema.schemas.keys():
            if exclude_embeddings and name in self.schema.groups[SchemaGroup.EMBEDDING]:
                continue
            tables[name] = self.open_table(name)

        return tables

    def open_table(self, name: str) -> LanceTable:
        """Open a dataset table with LanceDB.

        Args:
            name: Name of the table to open.

        Returns:
            Dataset table.
        """
        if name not in self.schema.schemas.keys() and name != SchemaGroup.SOURCE.value:
            raise DatasetAccessError(f"Table {name} not found in dataset")

        table = self._db_connection.open_table(name)
        if name == SchemaGroup.SOURCE.value:
            return table

        schema_table = self.schema.schemas[name]
        if is_view_embedding(schema_table):
            schema_table = cast(type[ViewEmbedding], schema_table)
            try:
                schema_table.get_embedding_fn_from_table(self, name, table.schema.metadata)
            except TypeError:  # no embedding function
                pass
        return table

    @overload
    def resolve_ref(self, ref: ItemRef) -> Item: ...
    @overload
    def resolve_ref(self, ref: ViewRef) -> View: ...
    @overload
    def resolve_ref(self, ref: EmbeddingRef) -> Embedding: ...
    @overload
    def resolve_ref(self, ref: EntityRef) -> Entity: ...
    @overload
    def resolve_ref(self, ref: AnnotationRef) -> Annotation: ...
    @overload
    def resolve_ref(self, ref: SourceRef) -> Source: ...
    @overload
    def resolve_ref(self, ref: SchemaRef) -> BaseSchema: ...
    def resolve_ref(
        self, ref: SchemaRef | ItemRef | ViewRef | EmbeddingRef | EntityRef | AnnotationRef | SourceRef
    ) -> BaseSchema | Item | View | Embedding | Entity | Annotation | Source:
        """Resolve a [SchemaRef][pixano.features.SchemaRef].

        It fetches the data from the table referenced.

        Args:
            ref: Reference to resolve.

        Returns:
            The resolved reference.
        """
        if ref.id == "" or ref.name == "":
            raise DatasetAccessError("Reference should have a name and an id.")
        return self.get_data(ref.name, ids=[ref.id])[0]

    @overload
    def get_data(
        self,
        table_name: str,
        ids: list[str] | None = None,
        limit: int | None = None,
        skip: int = 0,
        where: str | None = None,
        item_ids: list[str] | None = None,
    ) -> list[BaseSchema]: ...
    @overload
    def get_data(
        self,
        table_name: str,
        ids: str,
        limit: int | None = None,
        skip: int = 0,
        where: str | None = None,
        item_ids: None = None,
    ) -> BaseSchema | None: ...

    def get_data(
        self,
        table_name: str,
        ids: list[str] | str | None = None,
        limit: int | None = None,
        skip: int = 0,
        where: str | None = None,
        item_ids: list[str] | None = None,
    ) -> list[BaseSchema] | BaseSchema | None:
        """Read data from a table.

        Data can be filtered by ids, item ids, where clause, or limit and skip.

        Args:
            table_name: Table name.
            where: Where clause.
            ids: ids to read.
            limit: Amount of items to read. If not set, will default to table size.
            skip: The number of data to skip.
            item_ids: Item ids to read.

        Returns:
            List of values.
        """
        if table_name == SchemaGroup.ITEM.value:
            if item_ids is not None:
                if ids is None:
                    ids = item_ids
                else:
                    raise DatasetAccessError("ids and item_ids cannot be set at the same time")
                item_ids = None

        return_list = not isinstance(ids, str)
        ids = [ids] if isinstance(ids, str) else ids

        _validate_ids_item_ids_and_limit_and_skip(ids, limit, skip, item_ids)

        if item_ids is not None:
            sql_item_ids = to_sql_list(item_ids)
        table = self.open_table(table_name)

        if ids is None and item_ids is None and limit is None:
            limit = table.count_rows()

        if ids is None:
            if item_ids is None:
                if where is not None:
                    query = TableQueryBuilder(table).where(where).limit(limit).offset(skip)
                else:
                    query = TableQueryBuilder(table).limit(limit).offset(skip)
            else:
                sql_item_ids = to_sql_list(item_ids)
                if where is not None:
                    where += f" AND item_ref.id IN {sql_item_ids}"
                else:
                    where = f"item_ref.id IN {sql_item_ids}"
                query = TableQueryBuilder(table).where(where).limit(limit).offset(skip)
        else:
            sql_ids = to_sql_list(ids)
            if where is not None:
                where += f" AND id IN {sql_ids}"
            else:
                where = f"id IN {sql_ids}"
            query = TableQueryBuilder(table).where(where)

        schema = self.schema.schemas[table_name] if table_name != SchemaGroup.SOURCE.value else Source

        query_models: list[BaseSchema] = query.to_pydantic(schema)
        for model in query_models:
            model.dataset = self  # type: ignore[attr-defined]
            model.table_name = table_name

        return query_models if return_list else (query_models[0] if query_models != [] else None)

    @overload
    def get_dataset_items(
        self, ids: list[str] | None = None, limit: int | None = None, skip: int = 0
    ) -> list[DatasetItem]: ...
    @overload
    def get_dataset_items(self, ids: str, limit: int | None = None, skip: int = 0) -> DatasetItem | None: ...
    def get_dataset_items(
        self,
        ids: list[str] | str | None = None,
        limit: int | None = None,
        skip: int = 0,
    ) -> list[DatasetItem] | DatasetItem | None:
        """Read dataset items.

        Filter dataset items by ids, or limit and skip.

        Args:
            ids: Item ids to read.
            limit: Amount of items to read.
            skip: The number of data to skip..

        Returns:
            List of dataset items.
        """
        return_list = not isinstance(ids, str)
        ids = [ids] if isinstance(ids, str) else ids

        _validate_ids_and_limit_and_skip(ids, limit, skip)

        items = self.get_data(table_name=SchemaGroup.ITEM.value, where=None, ids=ids, limit=limit, skip=skip)
        if items == []:
            return [] if return_list else None
        item_ids: list[str] = [item.id for item in items]
        sql_ids = to_sql_list(item_ids)

        # Load tables
        ds_tables = self.open_tables(exclude_embeddings=True)

        # Load items data from the tables
        data_dict: dict[str, dict[str, BaseSchema | list[BaseSchema]]] = {item.id: item.model_dump() for item in items}
        for table_name, table in ds_tables.items():
            if table_name == SchemaGroup.ITEM.value:
                continue
            is_collection = self.schema.relations[SchemaGroup.ITEM.value][table_name] == SchemaRelation.ONE_TO_MANY
            table_schema = self.schema.schemas[table_name]

            rows = TableQueryBuilder(table).where(f"item_ref.id in {sql_ids}").to_pydantic(table_schema)

            for row in rows:
                row.dataset = self
                row.table_name = table_name
                item_id = row.item_ref.id
                if is_collection:
                    if table_name not in data_dict[item_id]:
                        data_dict[item_id][table_name] = []
                    data_dict[item_id][table_name].append(row)
                else:
                    data_dict[item_id][table_name] = row

        dataset_items = [self.dataset_item_model(**data_dict[item_id]) for item_id in item_ids]  # type: ignore[arg-type]

        return dataset_items if return_list else (dataset_items[0] if dataset_items != [] else None)

    def find_ids_in_table(self, table_name: str, ids: set[str]) -> dict[str, bool]:
        """Search ids in a table.

        Args:
            table_name: Table name.
            ids: Ids to find.

        Returns:
            Dictionary of ids found. Keys are the ids and values are `True` if the id is found, `False` otherwise.
        """
        if len(ids) == 0:
            return {}
        table = self.open_table(table_name)
        ids_found = list(TableQueryBuilder(table).select(["id"]).where(f"id in {to_sql_list(ids)}").to_polars()["id"])
        return {id: id in ids_found for id in ids}

    def get_all_ids(self, table_name: str = SchemaGroup.ITEM.value) -> list[str]:
        """Get all the ids from a table.

        Args:
            table_name: table to look for ids.

        Returns:
            list of the ids.
        """
        return [row["id"] for row in TableQueryBuilder(self.open_table(table_name)).select(["id"]).to_list()]

    def compute_view_embeddings(self, table_name: str, data: list[dict]) -> None:
        """Compute the [view embeddings][pixano.features.ViewEmbedding] via the
            [Embedding Function][lancedb.embeddings.base.EmbeddingFunction] stored in the table metadata.

        Args:
            table_name: Table name containing the view embeddings.
            data: Data to compute. Dictionary representing a view embedding without the vector field.
        """
        table_schema = self.schema.schemas[table_name]
        if not issubclass(table_schema, ViewEmbedding):
            raise DatasetAccessError(f"Table {table_name} is not a view embedding table")
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise DatasetAccessError("Data must be a list of dictionaries")
        # TODO: improve how to handle shape, this works but feels hacky
        for item in data:
            if "shape" not in item:
                item["shape"] = []
        table = self.open_table(table_name)
        data = pa.Table.from_pylist(
            data, schema=table_schema.to_arrow_schema(remove_vector=True, remove_metadata=True)
        )
        table.add(data)
        return None

    def add_data(
        self,
        table_name: str,
        data: list[BaseSchema],
        ignore_integrity_checks: list[IntegrityCheck] | None = None,
        raise_or_warn: Literal["raise", "warn", "none"] = "raise",
    ) -> list[BaseSchema]:
        """Add data to a table.

        Args:
            table_name: Table name.
            data: Data to add.
            ignore_integrity_checks: List of integrity checks to ignore.
            raise_or_warn: Whether to raise or warn on integrity errors. Can be 'raise', 'warn' or 'none'.
        """
        if not all((isinstance(item, type(data[0])) for item in data)) or not set(
            type(data[0]).model_fields.keys()
        ) == set(
            self.schema.schemas[table_name].model_fields.keys()
            if table_name != SchemaGroup.SOURCE.value
            else Source.model_fields.keys()
        ):
            raise DatasetAccessError(
                "All data must be instances of the table type "
                f"{self.schema.schemas[table_name] if table_name != SchemaGroup.SOURCE.value else Source}."
            )
        _validate_raise_or_warn(raise_or_warn)

        table = self.open_table(table_name)
        if raise_or_warn != "none":
            handle_integrity_errors(
                check_table_integrity(table_name, self, data, False, ignore_integrity_checks), raise_or_warn
            )
        for d in data:
            d.created_at = datetime.now()
            d.updated_at = d.created_at
        table.add(data)

        return data

    @overload
    def add_dataset_items(self, dataset_items: DatasetItem) -> DatasetItem: ...
    @overload
    def add_dataset_items(self, dataset_items: list[DatasetItem]) -> list[DatasetItem]: ...
    def add_dataset_items(self, dataset_items: list[DatasetItem] | DatasetItem) -> list[DatasetItem] | DatasetItem:
        """Add dataset items to the dataset.

        Warn:
            Does not test for integrity of the data.

        Args:
            dataset_items: Dataset items to add.
        """
        batch = True
        if isinstance(dataset_items, DatasetItem):
            dataset_items = [dataset_items]
            batch = False
        fields = self.dataset_item_model.model_fields.keys()
        if not all(
            isinstance(item, DatasetItem) and set(fields) == set(item.model_fields.keys()) for item in dataset_items
        ):
            raise DatasetAccessError("All data must be instances of the same DatasetItem.")

        schemas_data = [item.to_schemas_data(self.schema) for item in dataset_items]
        tables_data: dict[str, Any] = {}
        for table_name in self.schema.schemas.keys():
            for item in schemas_data:
                if table_name not in tables_data:
                    tables_data[table_name] = []
                if table_name not in item:
                    continue
                if isinstance(item[table_name], list):
                    tables_data[table_name].extend(item[table_name])
                elif item[table_name] is not None:
                    tables_data[table_name].append(item[table_name])
        for table_name, table_data in tables_data.items():
            if table_data != []:
                self.add_data(
                    table_name=table_name,
                    data=table_data,
                    ignore_integrity_checks=[],
                    raise_or_warn="none",
                )
        return dataset_items if batch else dataset_items[0]

    def delete_data(self, table_name: str, ids: list[str]) -> list[str]:
        """Delete data from a table.

        Args:
            table_name: Table name.
            ids: Ids to delete.

        Returns:
            The list of ids not found.
        """
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise DatasetAccessError("ids must be a list of strings")

        set_ids = set(ids)

        table = self.open_table(table_name)
        sql_ids = to_sql_list(set_ids)

        ids_found = {
            row["id"] for row in TableQueryBuilder(table).select(["id"]).where(f"id in {to_sql_list(ids)}").to_list()
        }
        ids_not_found = [id for id in set_ids if id not in ids_found]

        table.delete(where=f"id in {sql_ids}")

        return ids_not_found

    def delete_dataset_items(self, ids: list[str]) -> list[str]:
        """Delete dataset items.

        Args:
            ids: Ids to delete.

        Returns:
            The list of ids not found.
        """
        sql_ids = to_sql_list(ids)

        ids_not_found = []
        for table_name in self.schema.schemas.keys():
            if table_name == SchemaGroup.ITEM.value:
                ids_not_found = self.delete_data(table_name, ids)
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
                table_sql_ids = to_sql_list(table_ids)
                table.delete(where=f"id in {table_sql_ids}")
        return ids_not_found

    @overload
    def update_data(
        self,
        table_name: str,
        data: list[BaseSchema],
        return_separately: Literal[False] = False,
        ignore_integrity_checks: list[IntegrityCheck] | None = None,
        raise_or_warn: Literal["raise", "warn", "none"] = "raise",
    ) -> list[BaseSchema]: ...
    @overload
    def update_data(
        self,
        table_name: str,
        data: list[BaseSchema],
        return_separately: Literal[True],
        ignore_integrity_checks: list[IntegrityCheck] | None = None,
        raise_or_warn: Literal["raise", "warn", "none"] = "raise",
    ) -> tuple[list[BaseSchema], list[BaseSchema]]: ...
    def update_data(
        self,
        table_name: str,
        data: list[BaseSchema],
        return_separately: bool = False,
        ignore_integrity_checks: list[IntegrityCheck] | None = None,
        raise_or_warn: Literal["raise", "warn", "none"] = "raise",
    ) -> list[BaseSchema] | tuple[list[BaseSchema], list[BaseSchema]]:
        """Update data in a table.

        Args:
            table_name: Table name.
            data: Data to update.
            return_separately: Whether to return separately added and updated data.
            ignore_integrity_checks: List of integrity checks to ignore.
            raise_or_warn: Whether to raise or warn on integrity errors. Can be 'raise', 'warn' or 'none'.

        Returns:
            If `return_separately` is `True`, returns a tuple of updated and added data. Otherwise, returns the updated
            data.
        """
        if not all((isinstance(item, type(data[0])) for item in data)) or not set(
            type(data[0]).model_fields.keys()
        ) == set(
            self.schema.schemas[table_name].model_fields.keys()
            if table_name != SchemaGroup.SOURCE.value
            else Source.model_fields.keys()
        ):
            raise DatasetAccessError(
                "All data must be instances of the table type "
                f"{self.schema.schemas[table_name] if table_name != SchemaGroup.SOURCE.value else Source}."
            )
        _validate_raise_or_warn(raise_or_warn)

        table = self.open_table(table_name)
        if raise_or_warn != "none":
            handle_integrity_errors(
                check_table_integrity(table_name, self, data, True, ignore_integrity_checks), raise_or_warn
            )
        set_ids = {item.id for item in data}
        ids_found: dict[str, datetime] = {}

        ids_found = {
            row["id"]: row["created_at"]
            for row in TableQueryBuilder(table)
            .select(["id", "created_at"])
            .where(f"id in {to_sql_list(set_ids)}")
            .to_list()
        }

        for d in data:
            d.updated_at = datetime.now()
            if d.id not in ids_found:
                d.created_at = d.updated_at
        table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(data)

        if not return_separately:
            return data

        updated_data, added_data = [], []
        for d in data:
            if d.id not in ids_found:
                added_data.append(d)
            else:
                updated_data.append(d)

        return updated_data, added_data

    @overload
    def update_dataset_items(
        self,
        dataset_items: list[DatasetItem],
        return_separately: Literal[False] = False,
    ) -> list[DatasetItem]: ...
    @overload
    def update_dataset_items(
        self,
        dataset_items: list[DatasetItem],
        return_separately: Literal[True],
    ) -> tuple[list[DatasetItem], list[DatasetItem]]: ...
    def update_dataset_items(
        self,
        dataset_items: list[DatasetItem],
        return_separately: bool = False,
    ) -> list[DatasetItem] | tuple[list[DatasetItem], list[DatasetItem]]:
        """Update dataset items.

        Warn:
            Does not test for integrity of the data.

        Args:
            dataset_items: Dataset items to update.
            return_separately: Whether to return separately added and updated dataset items.

        Returns:
            If `return_separately` is `True`, returns a tuple of updated and added dataset items. Otherwise, returns
            the updated dataset items.
        """
        fields = self.dataset_item_model.model_fields.keys()
        if not all(
            isinstance(item, DatasetItem) and set(fields) == set(item.model_fields.keys()) for item in dataset_items
        ):
            raise DatasetAccessError("All data must be instances of the same DatasetItem.")

        schemas_data = [item.to_schemas_data(self.schema) for item in dataset_items]
        updated_ids = set()
        tables_data: dict[str, Any] = {}
        for table_name in self.schema.schemas.keys():
            for item in schemas_data:
                if table_name not in tables_data:
                    tables_data[table_name] = []
                if table_name not in item:
                    continue
                if isinstance(item[table_name], list):
                    tables_data[table_name].extend(item[table_name])
                elif item[table_name] is not None:
                    tables_data[table_name].append(item[table_name])
        for table_name, table_data in tables_data.items():
            if table_data != []:
                updated, _ = self.update_data(
                    table_name,
                    table_data,
                    return_separately=True,
                    ignore_integrity_checks=[],
                    raise_or_warn="none",
                )
                for row in updated:
                    updated_ids.add(row.item_ref.id if table_name != SchemaGroup.ITEM.value else row.id)

        dataset_items = self.get_dataset_items([item.id for item in dataset_items])

        if not return_separately:
            return dataset_items

        updated_items, added_items = [], []
        for item in dataset_items:
            if item.id not in updated_ids:
                added_items.append(item)
            else:
                updated_items.append(item)
        return updated_items, added_items

    @staticmethod
    def find(
        id: str,
        directory: Path,
        media_dir: Path | None = None,
    ) -> "Dataset":
        """Find a Dataset in a directory.

        Args:
            id: Dataset ID to find.
            directory: Directory to search in.
            media_dir: Media directory.

        Returns:
            The found dataset.
        """
        # Browse directory
        for json_fp in directory.glob("*/info.json"):
            info = DatasetInfo.from_json(json_fp)
            if info.id == id:
                # Return dataset
                return Dataset(json_fp.parent, media_dir)
        raise FileNotFoundError(f"Dataset {id} not found in {directory}")

    def semantic_search(
        self, query: str, table_name: str, limit: int, skip: int = 0
    ) -> tuple[list[BaseSchema], list[float]]:
        """Perform a semantic search.

        It searches for the closest items to the query in the table embeddings.

        Args:
            query: Text query for semantic search.
            table_name: Table name for embeddings.
            limit: Limit number of items.
            skip: Skip number of items

        Returns:
            Tuple of items and distances.
        """
        if not isinstance(query, str):
            raise DatasetAccessError("query must be a string.")
        elif not isinstance(table_name, str):
            raise DatasetAccessError("table_name must be a string.")
        elif not isinstance(limit, int) or limit < 1:
            raise DatasetAccessError("limit must be a strictly positive integer.")
        elif not isinstance(skip, int) or skip < 0:
            raise DatasetAccessError("skip must be a positive integer.")
        elif table_name not in self.schema.schemas:
            raise DatasetAccessError(f"Table {table_name} not found in dataset {self.id}.")
        elif table_name not in self.schema.groups[SchemaGroup.EMBEDDING] or not is_view_embedding(
            self.schema.schemas[table_name]
        ):
            raise DatasetAccessError(f"Table {table_name} is not a view embedding table.")

        table = self.open_table(table_name)
        semantic_results: pl.DataFrame = (
            table.search(query).select(["item_ref.id"]).limit(1e9).to_polars()
        )  # TODO: change high limit if lancedb supports it
        item_results = semantic_results.group_by("item_ref.id").agg(pl.min("_distance")).sort("_distance")
        item_ids = item_results["item_ref.id"].to_list()[skip : skip + limit]

        item_rows = self.get_data("item", ids=item_ids)
        item_rows = sorted(item_rows, key=lambda x: item_ids.index(x.id))
        distances = [
            item_results.row(by_predicate=(pl.col("item_ref.id") == item.id), named=True)["_distance"]
            for item in item_rows
        ]
        return item_rows, distances

    @staticmethod
    def list(directory: Path) -> list[DatasetInfo]:
        """List the datasets information in directory.

        Args:
            directory: Directory to search in.

        Returns:
            List of dataset infos.
        """
        dataset_infos = []
        for json_fp in directory.glob("*/info.json"):
            dataset_infos.append(DatasetInfo.from_json(json_fp))
        return dataset_infos
