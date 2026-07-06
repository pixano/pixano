# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import io
import json
import logging
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Callable, ClassVar, List, Literal, Sequence, Union, cast, overload

import lancedb
import PIL.Image
import polars as pl
import pyarrow as pa
import shortuuid
from lancedb.common import DATA
from lancedb.pydantic import LanceModel
from lancedb.table import LanceTable

from pixano.datasets.queries import TableQueryBuilder
from pixano.datasets.utils.errors import DatasetAccessError, DatasetPaginationError
from pixano.datasets.utils.integrity import (
    IntegrityCheck,
    check_table_integrity,
    handle_integrity_errors,
    validate_batch,
)
from pixano.features.utils.image import create_mosaic, image_to_base64
from pixano.schemas import (
    Conversation,
    Message,
    Record,
    SchemaGroup,
    ViewEmbedding,
    is_image,
    is_sequence_frame,
    is_video,
    is_view_embedding,
    validate_canonical_table_map,
)
from pixano.utils.python import to_sql_list, unique_list

from .dataset_features_values import Constraint, ConstraintDict, DatasetFeaturesValues, TableName
from .dataset_info import DatasetInfo
from .dataset_stat import DatasetStatistic


if TYPE_CHECKING:
    pass


logger = logging.getLogger(__name__)


def _combine_where_clauses(*clauses: str | None) -> str | None:
    filtered = [clause for clause in clauses if clause]
    return " AND ".join(filtered) if filtered else None


def _validate_ids_record_ids_and_limit_and_skip(
    ids: list[str] | None,
    limit: int | None,
    skip: int,
    record_ids: list[str] | None,
) -> None:
    if ids is not None and (not isinstance(ids, list) or not all(isinstance(item_id, str) for item_id in ids)):
        raise DatasetAccessError("ids must be a list of strings")

    if record_ids is not None and (
        not isinstance(record_ids, list) or not all(isinstance(record_id, str) for record_id in record_ids)
    ):
        raise DatasetAccessError("record_ids must be a list of strings")

    if ids is not None and limit is not None:
        raise DatasetAccessError("ids and limit cannot be set at the same time")

    if not isinstance(skip, int) or skip < 0:
        raise DatasetPaginationError("limit and skip must be non-negative integers")

    if limit is not None and (not isinstance(limit, int) or limit < 1):
        raise DatasetPaginationError("limit and skip must be non-negative integers")


def _validate_raise_or_warn(raise_or_warn: str) -> None:
    """Validate the raise_or_warn argument."""
    if raise_or_warn not in ("raise", "warn", "none"):
        raise ValueError(f"raise_or_warn must be 'raise', 'warn' or 'none', got '{raise_or_warn}'")


class Dataset:
    """The Pixano Dataset.

    It is a collection of tables that can be queried and manipulated with LanceDB.

    Tables are defined by the :class:`DatasetInfo` ``tables`` mapping, which maps
    table names to :class:`LanceModel` schema classes. The main table is always
    named ``"records"`` and its schema must inherit from :class:`Record`.  All
    auxiliary tables must have schemas that inherit from :class:`RecordComponent`.

    Attributes:
        path: Path to the dataset.
        info: Dataset info (including table→schema mapping).
        features_values: Dataset features values.
        stats: Dataset statistics.
        thumbnail: Dataset thumbnail base 64 URL.
    """

    _DB_PATH: str = "db"
    _PREVIEWS_PATH: str = "previews"
    _INFO_FILE: str = "info.json"
    _FEATURES_VALUES_FILE: str = "features_values.json"
    _STAT_FILE: str = "stats.json"
    _THUMB_FILE: str = "preview.png"

    path: Path
    info: DatasetInfo
    stats: list[DatasetStatistic] = []
    thumbnail: Path

    def __init__(self, path: Path):
        """Initialize the dataset.

        Args:
            path: Path to the dataset.
        """
        self.path = path

        self._info_file = self.path / self._INFO_FILE
        self._features_values_file = self.path / self._FEATURES_VALUES_FILE
        self._stat_file = self.path / self._STAT_FILE
        self._thumb_file = self.path / self._THUMB_FILE
        self._db_path = self.path / self._DB_PATH

        self.info = DatasetInfo.from_json(self._info_file)
        validate_canonical_table_map(self.info.tables)
        self.features_values = DatasetFeaturesValues.from_json(self._features_values_file)
        self.stats = DatasetStatistic.from_json(self._stat_file) if self._stat_file.is_file() else []
        self.thumbnail = self._thumb_file
        self.previews_path = self.path / self._PREVIEWS_PATH

        self._db_connection = self._connect()
        if self.info.spec_version < self._CURRENT_SPEC_VERSION:
            try:
                self._migrate_storage_to_spec_version_2()
            except Exception as exc:
                # A read-only dataset stays readable at the old layout; writes will
                # surface the missing columns explicitly.
                logger.warning(
                    "Dataset %s: spec version %d migration failed, continuing unmigrated: %s",
                    self.path,
                    self._CURRENT_SPEC_VERSION,
                    exc,
                )
        self._num_rows_cache: int | None = None

    # ------------------------------------------------------------------
    # Storage-layout migrations
    # ------------------------------------------------------------------

    _CURRENT_SPEC_VERSION: int = 2

    def _migrate_storage_to_spec_version_2(self) -> None:
        """Backfill the ``Video`` time-window columns introduced in spec version 2.

        Concurrency-safe: when several processes open the same pre-migration
        dataset, losers of the ``add_columns`` race converge by re-reading the
        table schema, and the ``info.json`` rewrite is atomic and idempotent
        (all writers produce identical content).
        """
        window_columns = {"from_timestamp": "0.0", "to_timestamp": "-1.0"}
        for table_name, schema_cls in self.info.tables.items():
            if not is_video(schema_cls):
                continue
            table = self.open_table(table_name)
            missing = {column: expr for column, expr in window_columns.items() if column not in table.schema.names}
            if not missing:
                continue
            try:
                table.add_columns(missing)
            except Exception:
                still_missing = [
                    column for column in missing if column not in self.open_table(table_name).schema.names
                ]
                if still_missing:
                    raise

        # Patch the raw JSON rather than re-serializing self.info: from_json drops
        # views it cannot deserialize, and a re-serialization would persist that loss.
        info_json = json.loads(self._info_file.read_text(encoding="utf-8"))
        info_json["spec_version"] = self._CURRENT_SPEC_VERSION
        tmp_file = self._info_file.with_name(self._info_file.name + ".tmp")
        tmp_file.write_text(json.dumps(info_json, indent=4), encoding="utf-8")
        tmp_file.replace(self._info_file)
        self.info.spec_version = self._CURRENT_SPEC_VERSION

    # ------------------------------------------------------------------
    # Factory
    # ------------------------------------------------------------------

    @classmethod
    def create(
        cls,
        path: Path,
        info: DatasetInfo,
    ) -> "Dataset":
        """Create a new dataset on disk.

        This initialises the directory structure, writes ``info.json`` and
        ``features_values.json``, creates the LanceDB database with empty
        tables for every entry in ``info.tables`` and returns the opened
        :class:`Dataset`.

        Args:
            path: Directory where the dataset will be stored.  The directory
                is created (with parents) and **must not already exist**.
            info: Dataset information including the ``tables`` mapping.
                If ``info.id`` is empty, a random ID is generated
                automatically.

        Returns:
            The newly created dataset.

        Raises:
            FileExistsError: If ``path`` already exists.
            ValueError: If ``info.tables`` is empty or invalid.
        """
        path = Path(path)
        if path.exists():
            raise FileExistsError(f"Dataset path already exists: {path}")

        if not info.tables:
            raise ValueError("info.tables must not be empty.")
        validate_canonical_table_map(info.tables)

        # Auto-generate ID if not provided
        if not info.id:
            info.id = shortuuid.uuid()

        # Create directory structure
        path.mkdir(parents=True)

        # Write info.json
        info_file = path / cls._INFO_FILE
        info.to_json(info_file)

        # Write empty features_values.json
        features_values_file = path / cls._FEATURES_VALUES_FILE
        DatasetFeaturesValues().to_json(features_values_file)

        # Create LanceDB database and tables
        db_path = path / cls._DB_PATH
        db = lancedb.connect(db_path)

        for table_name, schema in info.tables.items():
            # Override blob/raw_bytes columns to large_binary
            arrow_schema = schema.to_arrow_schema()
            modified = False
            for i, field in enumerate(arrow_schema):
                if field.name in ("blob", "raw_bytes") and field.type != pa.large_binary():
                    arrow_schema = arrow_schema.set(i, pa.field(field.name, pa.large_binary()))
                    modified = True
            if modified:
                db.create_table(table_name, schema=arrow_schema)
            else:
                db.create_table(table_name, schema=schema)

        return cls(path)

    @property
    def id(self) -> str:
        """Return the dataset ID."""
        return self.info.id

    @property
    def num_rows(self) -> int:
        """Return the number of rows in the record table.

        Returns:
            Number of rows.
        """
        if self._num_rows_cache is None:
            self._num_rows_cache = self.open_table(SchemaGroup.RECORD.value).count_rows()
        return self._num_rows_cache

    def count_rows_where(self, table_name: str = SchemaGroup.RECORD.value, where: str | None = None) -> int:
        """Count rows in a table, optionally filtered by a WHERE clause.

        Uses LanceDB native count_rows() which avoids full table materialization.

        Args:
            table_name: Table name.
            where: Optional WHERE clause to filter rows.

        Returns:
            Number of matching rows.
        """
        table = self.open_table(table_name)
        return table.count_rows(where)

    def generate_preview(self) -> str:
        """Generate a preview for the dataset.

        It samples images from the dataset, creates a mosaic and saves it to the previews directory.
        Only images with embedded blob data are used.

        Returns:
            The preview base64 string.
        """
        # Find an image-like view table
        image_table_name = None
        view_tables = self.info.groups.get(SchemaGroup.VIEW, set())
        for table_name in view_tables:
            schema = self.info.tables[table_name]
            if is_image(schema) or is_sequence_frame(schema):
                image_table_name = table_name
                break

        if image_table_name is None:
            return ""

        # Sample images (up to 4 for a 2x2 grid) — read from embedded blob only
        pil_images = []
        table = self.open_table(image_table_name)
        columns = ["id"]
        if "raw_bytes" in table.schema.names:
            columns.append("raw_bytes")
        rows = TableQueryBuilder(table, self._db_connection).select(columns).limit(4).to_list()
        for row in rows:
            blob = row.get("raw_bytes", b"")
            if blob:
                try:
                    pil_images.append(PIL.Image.open(io.BytesIO(blob)))
                except Exception:
                    continue

        if not pil_images:
            return ""

        try:
            mosaic = create_mosaic(pil_images, (350, 150))

            # Save to disk
            self.previews_path.mkdir(parents=True, exist_ok=True)
            preview_file = self.previews_path / "dataset_preview.jpg"
            mosaic.convert("RGB").save(preview_file, "JPEG")

            return image_to_base64(mosaic, "JPEG")
        except Exception:
            return ""

    def _connect(self) -> lancedb.db.DBConnection:
        """Connect to dataset with LanceDB.

        Returns:
            Dataset LanceDB connection.
        """
        return lancedb.connect(self._db_path)

    def create_table(
        self,
        name: str,
        schema: type[LanceModel],
        data: DATA | None = None,
        mode: str = "create",
        exist_ok: bool = False,
        on_bad_vectors: str = "error",
        fill_value: float = 0.0,
    ) -> LanceTable:
        """Add a table to the dataset.

        Args:
            name: Table name.
            schema: Table schema (must be a LanceModel subclass).
            data: Table data.
            mode: Table mode ('create', 'overwrite').
            exist_ok: If True, do not raise an error if the table already exists.
            on_bad_vectors: Raise an error, drop or fill bad vectors ("error", "drop", "fill").
            fill_value: Value to fill bad vectors.

        Returns:
            The table created.
        """
        # Override blob columns to large_binary for media-type tables
        arrow_schema = self._override_blob_columns_schema(name, schema)

        table = self._db_connection.create_table(
            name=name,
            schema=arrow_schema if arrow_schema is not None else schema,
            data=data,
            mode=mode,
            exist_ok=exist_ok,
            on_bad_vectors=on_bad_vectors,
            fill_value=fill_value,
            embedding_functions=None,
        )

        # Register in info and persist
        self.info.tables[name] = schema
        self.info.to_json(self._info_file)

        return table

    def _override_blob_columns_schema(self, table_name: str, schema: type[LanceModel]) -> pa.Schema | None:
        """Override blob columns to pa.large_binary() in Arrow schema.

        Args:
            table_name: The table name.
            schema: The schema class.

        Returns:
            The modified Arrow schema, or None if no overrides needed.
        """
        blob_cols = self._get_blob_columns(table_name, schema)
        if not blob_cols:
            return None
        arrow_schema = schema.to_arrow_schema()
        modified = False
        for i, field in enumerate(arrow_schema):
            if field.name in blob_cols:
                arrow_schema = arrow_schema.set(i, pa.field(field.name, pa.large_binary()))
                modified = True
        return arrow_schema if modified else None

    def _get_blob_columns(self, table_name: str, schema: type[LanceModel] | None = None) -> set[str]:
        """Get blob column names for a table.

        Args:
            table_name: The table name.
            schema: Optional schema class (looked up from info.tables if not provided).

        Returns:
            Set of blob column names.
        """
        if schema is None:
            schema = self.info.tables.get(table_name)
        if schema is None:
            return set()
        return {column for column in ("blob", "raw_bytes") if column in schema.model_fields}

    def open_tables(self, names: list[str] | None = None, exclude_embeddings: bool = True) -> dict[str, LanceTable]:
        """Open the dataset tables with LanceDB.

        Args:
            names: Table names to open. If None, open all tables.
            exclude_embeddings: Whether to exclude embedding tables from the list.

        Returns:
            Dataset tables.
        """
        tables: dict[str, LanceTable] = defaultdict(dict)
        embedding_tables = self.info.groups.get(SchemaGroup.EMBEDDING, set())

        for name in names if names is not None else self.info.tables.keys():
            if exclude_embeddings and name in embedding_tables:
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
        if name not in self.info.tables:
            raise DatasetAccessError(f"Table {name} not found in dataset")

        table = self._db_connection.open_table(name)

        schema_table = self.info.tables[name]
        if is_view_embedding(schema_table):
            schema_table = cast(type[ViewEmbedding], schema_table)
            try:
                schema_table.get_embedding_fn_from_table(self, name, table.schema.metadata)
            except TypeError:  # no embedding function
                pass
        return table

    @overload
    def get_data(
        self,
        table_name: str,
        ids: list[str] | None = None,
        limit: int | None = None,
        skip: int = 0,
        where: str | None = None,
        record_ids: list[str] | None = None,
        sortcol: str | None = None,
        order: str | None = None,
    ) -> list[LanceModel]: ...
    @overload
    def get_data(
        self,
        table_name: str,
        ids: str,
        limit: int | None = None,
        skip: int = 0,
        where: str | None = None,
        record_ids: None = None,
        sortcol: str | None = None,
        order: str | None = None,
    ) -> LanceModel | None: ...

    def get_data(
        self,
        table_name: str,
        ids: list[str] | str | None = None,
        limit: int | None = None,
        skip: int = 0,
        where: str | None = None,
        record_ids: list[str] | None = None,
        sortcol: str | None = None,
        order: str | None = None,
    ) -> list[LanceModel] | LanceModel | None:
        """Read data from a table.

        Data can be filtered by ids, record ids, where clause, or limit and skip.

        Args:
            table_name: Table name.
            ids: ids to read.
            limit: Amount of rows to read. If not set, will default to table size.
            skip: The number of rows to skip.
            where: Where clause.
            record_ids: Record ids to filter by (filters on ``record_id`` column).
            sortcol: column to order by.
            order: sort order (asc or desc).

        Returns:
            List of values.
        """
        # For the record table, record_ids is equivalent to ids
        if table_name == SchemaGroup.RECORD.value:
            if record_ids is not None:
                if ids is None:
                    ids = record_ids
                else:
                    raise DatasetAccessError("ids and record_ids cannot be set at the same time")
                record_ids = None

        return_list = not isinstance(ids, str)
        ids = [ids] if isinstance(ids, str) else ids

        _validate_ids_record_ids_and_limit_and_skip(ids, limit, skip, record_ids)

        if record_ids is not None:
            sql_record_ids = to_sql_list(record_ids)
        table = self.open_table(table_name)
        blob_cols = self._get_blob_columns(table_name)

        if ids is None and record_ids is None and limit is None:
            limit = table.count_rows()

        if ids is None:
            if record_ids is None:
                if where is not None:
                    query = (
                        TableQueryBuilder(table, self._db_connection, blob_columns=blob_cols)
                        .where(where)
                        .limit(limit)
                        .offset(skip)
                    )
                else:
                    query = (
                        TableQueryBuilder(table, self._db_connection, blob_columns=blob_cols).limit(limit).offset(skip)
                    )
            else:
                sql_record_ids = to_sql_list(record_ids)
                if where is not None:
                    where += f" AND record_id IN {sql_record_ids}"
                else:
                    where = f"record_id IN {sql_record_ids}"
                query = (
                    TableQueryBuilder(table, self._db_connection, blob_columns=blob_cols)
                    .where(where)
                    .limit(limit)
                    .offset(skip)
                )
            if sortcol is not None and order is not None:
                query = query.order_by(sortcol, order == "desc")
        else:
            sql_ids = to_sql_list(ids)
            if where is not None:
                where += f" AND id IN {sql_ids}"
            else:
                where = f"id IN {sql_ids}"
            query = TableQueryBuilder(table, self._db_connection, blob_columns=blob_cols).where(where)

        schema = self.info.tables[table_name]

        query_models: list[LanceModel] = query.to_pydantic(schema)

        return query_models if return_list else (query_models[0] if query_models != [] else None)

    def get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str] | None:
        """Load binary content for a single view row.

        Returns the embedded blob data and inferred format.

        Args:
            table_name: View table name.
            row_id: The row ID.

        Returns:
            Tuple of (blob_bytes, format_string) or None if not found.
        """
        table = self.open_table(table_name)
        columns = ["id"]
        for column_name in ("raw_bytes", "format"):
            if column_name in table.schema.names:
                columns.append(column_name)

        where = f"id IN {to_sql_list(row_id)}"

        rows = TableQueryBuilder(table, self._db_connection).select(columns).where(where).limit(1).to_list()
        if not rows:
            return None

        row = rows[0]
        blob = row.get("raw_bytes", b"")
        if not blob:
            return None
        fmt = row.get("format", "")
        return blob, fmt

    def get_temporal_view_batch(
        self,
        table_name: str,
        record_id: str,
        view_name: str | None = None,
        start_frame: int = 0,
        batch_size: int = 100,
    ) -> list[tuple[int, bytes, str]]:
        """Load one ordered batch of temporal view frames with their binary payloads.

        Returns a list of ``(frame_index, blob_bytes, format_string)`` tuples,
        reading from the embedded ``raw_bytes`` column.

        Args:
            table_name: View table name containing temporal frames.
            record_id: The record ID to filter by.
            view_name: Optional logical view name to filter by.
            start_frame: Starting frame index.
            batch_size: Number of frames to load.

        Returns:
            List of (frame_index, blob_bytes, format) tuples.
        """
        table = self.open_table(table_name)
        if "frame_index" not in table.schema.names:
            raise DatasetAccessError(f"Table '{table_name}' is not a temporal view table.")

        end_frame = start_frame + batch_size
        columns = ["frame_index"]
        for column_name in ("raw_bytes", "format"):
            if column_name in table.schema.names:
                columns.append(column_name)

        where = _combine_where_clauses(
            f"record_id IN {to_sql_list(record_id)}",
            f"logical_name IN {to_sql_list(view_name)}" if view_name is not None else None,
            f"frame_index >= {start_frame}",
            f"frame_index < {end_frame}",
        )
        assert where is not None

        query = table.search(None).select(columns).where(where).limit(batch_size)
        rows = query.to_list()
        rows.sort(key=lambda row: int(row.get("frame_index", -1)))

        result = []
        for row in rows:
            blob = row.get("raw_bytes", b"")
            if blob:
                result.append((int(row["frame_index"]), blob, row.get("format", "")))
        return result

    @overload
    def get_records(self, ids: list[str] | None = None, limit: int | None = None, skip: int = 0) -> list[Record]: ...
    @overload
    def get_records(self, ids: str, limit: int | None = None, skip: int = 0) -> Record | None: ...
    def get_records(
        self,
        ids: list[str] | str | None = None,
        limit: int | None = None,
        skip: int = 0,
    ) -> list[Record] | Record | None:
        """Read records from the record table.

        Args:
            ids: Record ids to read.
            limit: Amount of records to read.
            skip: The number of records to skip.

        Returns:
            List of records, a single record, or None.
        """
        return self.get_data(table_name=SchemaGroup.RECORD.value, ids=ids, limit=limit, skip=skip)

    def get_conversation(self, table_name: str, conversation_id: str) -> Conversation | None:
        """Read one conversation aggregate from a messages table.

        Args:
            table_name: The messages table name.
            conversation_id: The conversation ID.

        Returns:
            The conversation or None if not found.
        """
        where = f"conversation_id IN {to_sql_list(conversation_id)}"
        messages = (
            TableQueryBuilder(
                self.open_table(table_name), self._db_connection, blob_columns=self._get_blob_columns(table_name)
            )
            .where(where)
            .order_by("number")
            .to_pydantic(Message)
        )
        if not messages:
            return None
        return Conversation.from_messages(messages)

    def get_conversations(
        self,
        table_name: str,
        record_id: str | None = None,
        entity_id: str | None = None,
        view_id: str | None = None,
        source_type: str | None = None,
        where: str | None = None,
        limit: int | None = 100,
        skip: int = 0,
    ) -> tuple[list[Conversation], int]:
        """Read paginated conversation aggregates from a messages table.

        Args:
            table_name: The messages table name.
            record_id: Filter by record ID.
            entity_id: Filter by entity ID.
            view_id: Filter by view ID.
            source_type: Filter by source type.
            where: Additional WHERE clause.
            limit: Maximum conversations to return.
            skip: Number of conversations to skip.

        Returns:
            Tuple of (conversations, total_count).
        """
        table = self.open_table(table_name)
        blob_columns = self._get_blob_columns(table_name)
        combined_where = _combine_where_clauses(
            f"record_id = '{record_id}'" if record_id else None,
            f"entity_id = '{entity_id}'" if entity_id else None,
            f"view_id = '{view_id}'" if view_id else None,
            f"source_type = '{source_type}'" if source_type else None,
            f"({where})" if where else None,
        )

        conversation_query = TableQueryBuilder(table, self._db_connection, blob_columns=blob_columns).select(
            ["conversation_id"]
        )
        if combined_where is not None:
            conversation_query = conversation_query.where(combined_where)
        conversation_rows = conversation_query.order_by("conversation_id").to_list()
        conversation_ids = unique_list(
            [
                row["conversation_id"]
                for row in conversation_rows
                if isinstance(row.get("conversation_id"), str) and row["conversation_id"]
            ]
        )

        total = len(conversation_ids)
        page_ids = conversation_ids[skip:] if limit is None else conversation_ids[skip : skip + limit]
        if not page_ids:
            return [], total

        messages_where = _combine_where_clauses(
            combined_where,
            f"conversation_id IN {to_sql_list(page_ids)}",
        )
        assert messages_where is not None

        messages = (
            TableQueryBuilder(table, self._db_connection, blob_columns=blob_columns)
            .where(messages_where)
            .order_by(["conversation_id", "number"])
            .to_pydantic(Message)
        )

        grouped_messages: dict[str, list[Message]] = {conversation_id: [] for conversation_id in page_ids}
        for message in messages:
            grouped_messages.setdefault(message.conversation_id, []).append(message)

        conversations = [
            Conversation.from_messages(grouped_messages[conversation_id])
            for conversation_id in page_ids
            if grouped_messages.get(conversation_id)
        ]
        return conversations, total

    def find_ids_in_table(self, table_name: str, ids: set[str]) -> dict[str, bool]:
        """Search ids in a table.

        Args:
            table_name: Table name.
            ids: Ids to find.

        Returns:
            Dictionary of ids found. Keys are the ids and values are True if found.
        """
        if len(ids) == 0:
            return {}
        table = self.open_table(table_name)
        ids_found = list(
            TableQueryBuilder(table, self._db_connection)
            .select(["id"])
            .where(f"id in {to_sql_list(ids)}")
            .to_polars()["id"]
        )
        return {id: id in ids_found for id in ids}

    def get_all_ids(
        self,
        table_name: str = SchemaGroup.RECORD.value,
        sortcol: str | None = None,
        order: str | None = None,
        where: str | None = None,
    ) -> list[str]:
        """Get all the ids from a table.

        Args:
            table_name: table to look for ids.
            sortcol: column to order by.
            order: sort order (asc or desc).
            where: where clause to filter ids.

        Returns:
            list of the ids.
        """
        query = TableQueryBuilder(self.open_table(table_name), self._db_connection).select(["id"])
        if where is not None:
            query = query.where(where)
        if sortcol is not None and order is not None:
            query = query.order_by(order_by=sortcol, descending=order == "desc")
        return [row["id"] for row in query.to_list()]

    def compute_view_embeddings(self, table_name: str, data: list[dict]) -> None:
        """Compute the view embeddings via the embedding function stored in the table metadata.

        Args:
            table_name: Table name containing the view embeddings.
            data: Data to compute. Dictionary representing a view embedding without the vector field.
        """
        table_schema = self.info.tables[table_name]
        if not issubclass(table_schema, ViewEmbedding):
            raise DatasetAccessError(f"Table {table_name} is not a view embedding table")
        if not isinstance(data, list) or not all(isinstance(item, dict) for item in data):
            raise DatasetAccessError("Data must be a list of dictionaries")
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
        data: list[LanceModel],
        ignore_integrity_checks: list[IntegrityCheck] | None = None,
        raise_or_warn: Literal["raise", "warn", "none"] = "raise",
    ) -> list[LanceModel]:
        """Add data to a table.

        Args:
            table_name: Table name.
            data: Data to add.
            ignore_integrity_checks: List of integrity checks to ignore.
            raise_or_warn: Whether to raise or warn on integrity errors.

        Returns:
            The added data.
        """
        actual_table_name = table_name

        if not all((isinstance(item, type(data[0])) for item in data)) or not set(
            type(data[0]).model_fields.keys()
        ) == set(self.info.tables[actual_table_name].model_fields.keys()):
            raise DatasetAccessError(
                f"All data must be instances of the table type {self.info.tables[actual_table_name]}."
            )
        _validate_raise_or_warn(raise_or_warn)

        table = self.open_table(actual_table_name)
        if raise_or_warn != "none":
            handle_integrity_errors(
                check_table_integrity(actual_table_name, self, data, False, ignore_integrity_checks), raise_or_warn
            )
        for d in data:
            if hasattr(d, "created_at"):
                d.created_at = datetime.now()
            if hasattr(d, "updated_at"):
                d.updated_at = d.created_at if hasattr(d, "created_at") else datetime.now()
        table.add(data)

        if actual_table_name == SchemaGroup.RECORD.value:
            self._num_rows_cache = None

        return data

    # ------------------------------------------------------------------
    # Dependency order for multi-table inserts
    # ------------------------------------------------------------------

    _INSERT_ORDER: list[SchemaGroup] = [
        SchemaGroup.RECORD,
        SchemaGroup.VIEW,
        SchemaGroup.ENTITY,
        SchemaGroup.ENTITY_DYNAMIC_STATE,
        SchemaGroup.ANNOTATION,
        SchemaGroup.EMBEDDING,
    ]

    def _table_insert_order(self, table_names: list[str]) -> list[str]:
        """Return *table_names* sorted by FK dependency (parents first)."""
        group_index = {g: i for i, g in enumerate(self._INSERT_ORDER)}

        def _sort_key(name: str) -> int:
            for group, tables in self.info.groups.items():
                if name in tables:
                    return group_index.get(group, len(self._INSERT_ORDER))
            return len(self._INSERT_ORDER)

        return sorted(table_names, key=_sort_key)

    # ------------------------------------------------------------------
    # Multi-table insert
    # ------------------------------------------------------------------

    def add_records(
        self,
        data: dict[str, LanceModel | list[LanceModel]],
        check_integrity: Literal["raise", "warn", "none"] = "raise",
    ) -> None:
        """Insert rows into multiple tables in a single call.

        Accepts the same ``dict[str, LanceModel | list[LanceModel]]``
        format yielded by :meth:`DatasetBuilder.generate_data`.  Tables
        are flushed in dependency order (source -> record -> view ->
        entity -> entity_dynamic_state -> annotation -> embedding) so
        that foreign-key constraints are satisfied.

        Args:
            data: Mapping of table name to one or more rows to insert.
                ``None`` or empty-list values are silently skipped.
            check_integrity: Integrity-check mode.
                ``"raise"`` (default) aborts on the first error,
                ``"warn"`` emits warnings, ``"none"`` skips validation.
        """
        # Normalize values to lists and filter empties
        normalized: dict[str, list[LanceModel]] = {}
        for table_name, value in data.items():
            if value is None:
                continue
            rows = value if isinstance(value, list) else [value]
            if not rows:
                continue
            normalized[table_name] = rows

        if not normalized:
            return

        # Determine insertion order
        ordered_tables = self._table_insert_order(list(normalized.keys()))

        # Sort temporal batches (sequence frames) by timestamp for
        # storage co-locality
        for table_name, rows in normalized.items():
            schema_type = self.info.tables.get(table_name)
            if schema_type is not None and "timestamp" in schema_type.model_fields:
                normalized[table_name] = sorted(rows, key=lambda s: (getattr(s, "timestamp", 0),))

        # Integrity checks: build pending_ids so that sibling tables in
        # the same batch can resolve each other's FKs
        if check_integrity != "none":
            pending_ids: dict[str, set[str]] = {
                tname: {row.id for row in rows if row.id} for tname, rows in normalized.items() if rows
            }
            known_ids: dict[str, set[str]] = {tname: set() for tname in normalized}

            for table_name in ordered_tables:
                rows = normalized[table_name]
                validate_batch(
                    table_name,
                    rows,
                    known_ids,
                    self,
                    raise_or_warn=check_integrity,
                    pending_ids=pending_ids,
                )
                # After validation, promote to known_ids so downstream
                # tables can reference them
                for row in rows:
                    if row.id:
                        known_ids[table_name].add(row.id)

        # Insert into LanceDB in dependency order
        for table_name in ordered_tables:
            rows = normalized[table_name]
            for row in rows:
                if hasattr(row, "created_at"):
                    row.created_at = datetime.now()
                if hasattr(row, "updated_at"):
                    row.updated_at = row.created_at if hasattr(row, "created_at") else datetime.now()
            table = self.open_table(table_name)
            table.add(rows)

        # Invalidate row-count cache if records were touched
        if SchemaGroup.RECORD.value in normalized:
            self._num_rows_cache = None

    def merge_records(
        self,
        data: dict[str, LanceModel | list[LanceModel] | pa.RecordBatch | pa.Table],
        check_integrity: Literal["raise", "warn", "none"] = "raise",
        known_ids: dict[str, set[str]] | None = None,
    ) -> dict[str, int]:
        """Upsert rows into multiple tables in a single call.

        The multi-table counterpart of :meth:`update_data` and the idempotent
        counterpart of :meth:`add_records`: rows whose ``id`` already exists
        are updated, new ids are inserted, so re-running the same payload
        converges instead of duplicating. Tables are processed in FK
        dependency order (record → view → entity → … → annotation).

        Args:
            data: Mapping of table name to one or more rows, or to an Arrow
                ``RecordBatch``/``Table``. Arrow payloads currently require
                ``check_integrity="none"`` — vectorized Arrow integrity checks
                land with the import engine (spec §8); missing
                ``created_at``/``updated_at`` columns are appended to Arrow
                payloads so the LanceDB schema cast cannot fail on them.
            check_integrity: Integrity-check mode for row payloads. Uniqueness
                against already-stored ids is intentionally not enforced
                (existing ids are updates by design); in-batch duplicates,
                missing ids, and foreign keys are checked.
            known_ids: Optional ``table → ids`` mapping (e.g. an import
                engine's id ledger) used to resolve foreign keys without DB
                lookups.

        Returns:
            Mapping of table name to number of rows upserted.
        """
        row_payloads: dict[str, list[LanceModel]] = {}
        arrow_payloads: dict[str, pa.Table] = {}
        for table_name, value in data.items():
            if value is None:
                continue
            if isinstance(value, pa.RecordBatch):
                value = pa.Table.from_batches([value])
            if isinstance(value, pa.Table):
                if value.num_rows:
                    arrow_payloads[table_name] = value
                continue
            rows = value if isinstance(value, list) else [value]
            if rows:
                row_payloads[table_name] = rows

        if arrow_payloads and check_integrity != "none":
            raise NotImplementedError(
                "merge_records only supports Arrow payloads with check_integrity='none' for now. "
                "Vectorized Arrow integrity checks land with the import engine (spec §8)."
            )
        if not row_payloads and not arrow_payloads:
            return {}

        ordered_tables = self._table_insert_order([*row_payloads.keys(), *arrow_payloads.keys()])

        # Sort temporal row batches by timestamp for storage co-locality.
        for table_name, rows in row_payloads.items():
            schema_type = self.info.tables.get(table_name)
            if schema_type is not None and "timestamp" in schema_type.model_fields:
                row_payloads[table_name] = sorted(rows, key=lambda s: (getattr(s, "timestamp", 0),))

        if check_integrity != "none":
            pending_ids: dict[str, set[str]] = {
                tname: {row.id for row in rows if row.id} for tname, rows in row_payloads.items()
            }
            accumulated: dict[str, set[str]] = {tname: set(ids) for tname, ids in (known_ids or {}).items()}
            for table_name in ordered_tables:
                rows_to_check = row_payloads.get(table_name)
                if rows_to_check is None:
                    continue
                # Upsert semantics: ids already known for the target table are
                # legal (they are updates), so uniqueness applies only inside
                # the batch; other tables' known ids still resolve FKs.
                upsert_known = {tname: ids for tname, ids in accumulated.items() if tname != table_name}
                validate_batch(
                    table_name,
                    rows_to_check,
                    upsert_known,
                    self,
                    raise_or_warn=check_integrity,
                    pending_ids=pending_ids,
                )
                accumulated.setdefault(table_name, set()).update(row.id for row in rows_to_check if row.id)

        counts: dict[str, int] = {}
        for table_name in ordered_tables:
            table = self.open_table(table_name)
            if table_name in row_payloads:
                rows = row_payloads[table_name]
                self._stamp_upsert_timestamps(table, rows)
                table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(rows)
                counts[table_name] = len(rows)
            else:
                arrow_table = self._with_timestamp_columns(table, arrow_payloads[table_name])
                table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(arrow_table)
                counts[table_name] = arrow_table.num_rows

        if SchemaGroup.RECORD.value in counts:
            self._num_rows_cache = None
        return counts

    def _stamp_upsert_timestamps(self, table: LanceTable, rows: list[LanceModel]) -> None:
        """Stamp ``updated_at`` and preserve stored ``created_at`` for existing rows."""
        if not rows or not (hasattr(rows[0], "created_at") or hasattr(rows[0], "updated_at")):
            return

        stored_created_at: dict[str, datetime | None] = {}
        if hasattr(rows[0], "created_at"):
            row_ids = {row.id for row in rows if row.id}
            if row_ids:
                stored_created_at = {
                    stored["id"]: stored["created_at"]
                    for stored in TableQueryBuilder(table, self._db_connection)
                    .select(["id", "created_at"])
                    .where(f"id in {to_sql_list(row_ids)}")
                    .to_list()
                }

        for row in rows:
            now = datetime.now()
            if hasattr(row, "updated_at"):
                row.updated_at = now
            if hasattr(row, "created_at"):
                existing = stored_created_at.get(row.id)
                row.created_at = existing if existing is not None else now

    def _with_timestamp_columns(self, table: LanceTable, arrow_table: pa.Table) -> pa.Table:
        """Append missing ``created_at``/``updated_at`` columns to an Arrow payload."""
        table_schema = table.schema
        present = set(arrow_table.schema.names)
        now = datetime.now()
        for column in ("created_at", "updated_at"):
            if column in table_schema.names and column not in present:
                field = table_schema.field(column)
                arrow_table = arrow_table.append_column(field, pa.array([now] * arrow_table.num_rows, type=field.type))
        return arrow_table

    def create_scalar_indexes(
        self,
        columns: Sequence[str] = ("id", "record_id"),
        tables: Sequence[str] | None = None,
    ) -> None:
        """Create BTree scalar indexes on the given columns of the given tables.

        Idempotent: columns that are already indexed or absent from a table's
        schema are skipped. Indexes make ``merge_insert``, foreign-key lookups,
        export paging, and ``record_id`` filters scale past full-table scans.

        Args:
            columns: Column names to index where present.
            tables: Table names to index. Defaults to every dataset table.
        """
        table_names = list(tables) if tables is not None else list(self.info.tables.keys())
        for table_name in table_names:
            table = self.open_table(table_name)
            indexed_columns: set[str] = set()
            for index in table.list_indices():
                indexed_columns.update(getattr(index, "columns", None) or [])
            schema_names = set(table.schema.names)
            for column in columns:
                if column in schema_names and column not in indexed_columns:
                    table.create_scalar_index(column, index_type="BTREE")

    # ------------------------------------------------------------------
    # Cross-process cache invalidation
    # ------------------------------------------------------------------

    _cache_invalidation_hooks: ClassVar[list[Callable[[str], None]]] = []

    @classmethod
    def register_cache_invalidation_hook(cls, hook: Callable[[str], None]) -> None:
        """Register a callable invoked with a dataset id when its caches must be dropped."""
        if hook not in cls._cache_invalidation_hooks:
            cls._cache_invalidation_hooks.append(hook)

    @classmethod
    def invalidate_caches(cls, dataset_id: str) -> None:
        """Notify registered caches that a dataset changed on disk (e.g. after an import)."""
        for hook in cls._cache_invalidation_hooks:
            try:
                hook(dataset_id)
            except Exception as exc:
                logger.warning("Cache invalidation hook %r failed for dataset %s: %s", hook, dataset_id, exc)

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
            row["id"]
            for row in TableQueryBuilder(table, self._db_connection)
            .select(["id"])
            .where(f"id in {to_sql_list(ids)}")
            .to_list()
        }
        ids_not_found = [id for id in set_ids if id not in ids_found]

        table.delete(where=f"id in {sql_ids}")

        if table_name == SchemaGroup.RECORD.value:
            self._num_rows_cache = None

        return ids_not_found

    def delete_records(self, ids: list[str]) -> list[str]:
        """Delete records and all associated data across all tables.

        Cascading deletion: deletes from the record table first, then from all
        auxiliary tables where ``record_id`` matches the given ids.

        Args:
            ids: Record ids to delete.

        Returns:
            The list of ids not found in the record table.
        """
        sql_ids = to_sql_list(ids)

        ids_not_found = []
        for table_name in self.info.tables.keys():
            if table_name == SchemaGroup.RECORD.value:
                ids_not_found = self.delete_data(table_name, ids)
            else:
                table = self.open_table(table_name)
                table_ids = (
                    table.search()
                    .select(["id"])
                    .where(f"record_id in {sql_ids}")
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
        data: list[LanceModel],
        return_separately: Literal[False] = False,
        ignore_integrity_checks: list[IntegrityCheck] | None = None,
        raise_or_warn: Literal["raise", "warn", "none"] = "raise",
    ) -> list[LanceModel]: ...
    @overload
    def update_data(
        self,
        table_name: str,
        data: list[LanceModel],
        return_separately: Literal[True],
        ignore_integrity_checks: list[IntegrityCheck] | None = None,
        raise_or_warn: Literal["raise", "warn", "none"] = "raise",
    ) -> tuple[list[LanceModel], list[LanceModel]]: ...
    def update_data(
        self,
        table_name: str,
        data: list[LanceModel],
        return_separately: bool = False,
        ignore_integrity_checks: list[IntegrityCheck] | None = None,
        raise_or_warn: Literal["raise", "warn", "none"] = "raise",
    ) -> list[LanceModel] | tuple[list[LanceModel], list[LanceModel]]:
        """Update data in a table (upsert).

        Args:
            table_name: Table name.
            data: Data to update.
            return_separately: Whether to return separately added and updated data.
            ignore_integrity_checks: List of integrity checks to ignore.
            raise_or_warn: Whether to raise or warn on integrity errors.

        Returns:
            If ``return_separately`` is True, returns (updated_data, added_data).
            Otherwise, returns the full data list.
        """
        actual_table_name = table_name

        if not all((isinstance(item, type(data[0])) for item in data)) or not set(
            type(data[0]).model_fields.keys()
        ) == set(self.info.tables[actual_table_name].model_fields.keys()):
            raise DatasetAccessError(
                f"All data must be instances of the table type {self.info.tables[actual_table_name]}."
            )
        _validate_raise_or_warn(raise_or_warn)

        table = self.open_table(actual_table_name)
        if raise_or_warn != "none":
            handle_integrity_errors(
                check_table_integrity(actual_table_name, self, data, True, ignore_integrity_checks), raise_or_warn
            )
        set_ids = {item.id for item in data}
        has_timestamps = hasattr(data[0], "created_at") if data else False

        if has_timestamps:
            ids_found: dict[str, datetime | None] = {
                row["id"]: row["created_at"]
                for row in TableQueryBuilder(table, self._db_connection)
                .select(["id", "created_at"])
                .where(f"id in {to_sql_list(set_ids)}")
                .to_list()
            }
        else:
            ids_found = {
                row["id"]: None
                for row in TableQueryBuilder(table, self._db_connection)
                .select(["id"])
                .where(f"id in {to_sql_list(set_ids)}")
                .to_list()
            }

        for d in data:
            if hasattr(d, "updated_at"):
                d.updated_at = datetime.now()
            if d.id not in ids_found and hasattr(d, "created_at"):
                d.created_at = d.updated_at if hasattr(d, "updated_at") else datetime.now()
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

    @staticmethod
    def find(
        id: str,
        directory: Path,
    ) -> "Dataset":
        """Find a Dataset in a directory.

        Args:
            id: Dataset ID to find.
            directory: Directory to search in.

        Returns:
            The found dataset.
        """
        # Fast path: try direct path first (dataset dir often matches id)
        direct = directory / id / "info.json"
        if direct.exists():
            info = DatasetInfo.from_json(direct)
            if info.id == id:
                return Dataset(direct.parent)

        # Fallback: scan all directories
        for json_fp in directory.glob("*/info.json"):
            info = DatasetInfo.from_json(json_fp)
            if info.id == id:
                return Dataset(json_fp.parent)
        raise FileNotFoundError(f"Dataset {id} not found in {directory}")

    def semantic_search(
        self, query: str, table_name: str, limit: int, skip: int = 0
    ) -> tuple[list[LanceModel], list[float], list[str]]:
        """Perform a semantic search.

        It searches for the closest records to the query in the table embeddings.

        Args:
            query: Text query for semantic search.
            table_name: Table name for embeddings.
            limit: Limit number of records.
            skip: Skip number of records.

        Returns:
            Tuple of records, distances, and full sorted list of record ids.
        """
        if not isinstance(query, str):
            raise DatasetAccessError("query must be a string.")
        elif not isinstance(table_name, str):
            raise DatasetAccessError("table_name must be a string.")
        elif not isinstance(limit, int) or limit < 1:
            raise DatasetAccessError("limit must be a strictly positive integer.")
        elif not isinstance(skip, int) or skip < 0:
            raise DatasetAccessError("skip must be a positive integer.")
        elif table_name not in self.info.tables:
            raise DatasetAccessError(f"Table {table_name} not found in dataset {self.id}.")
        elif table_name not in self.info.groups.get(SchemaGroup.EMBEDDING, set()) or not is_view_embedding(
            self.info.tables[table_name]
        ):
            raise DatasetAccessError(f"Table {table_name} is not a view embedding table.")

        table = self.open_table(table_name)
        semantic_results: pl.DataFrame = (
            table.search(query).select(["record_id"]).limit(table.count_rows()).to_polars()
        )
        record_results = semantic_results.group_by("record_id").agg(pl.min("_distance")).sort("_distance")
        full_record_ids = record_results["record_id"].to_list()
        record_ids = full_record_ids[skip : skip + limit]

        record_rows = self.get_data(SchemaGroup.RECORD.value, ids=record_ids)
        record_rows = sorted(record_rows, key=lambda x: record_ids.index(x.id))
        distances = [
            record_results.row(by_predicate=(pl.col("record_id") == record.id), named=True)["_distance"]
            for record in record_rows
        ]
        return record_rows, distances, full_record_ids

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

    def add_constraint(
        self,
        table: TableName,
        field_name: str,
        values: List[Union[int, float, str, bool]],
        restricted: bool = True,
    ):
        """Add or replace a constraint.

        Args:
            table: Table name.
            field_name: Name of the field to constrain.
            values: List of allowed values.
            restricted: True if no other values are allowed.
        """
        kinds = [group.value for group, tables in self.info.groups.items() if table in tables]
        if len(kinds) != 1:
            raise ValueError(f"Table {table} does not exist in schema")

        constraint_dict: ConstraintDict = getattr(self.features_values, kinds[0])

        # Ensure the list exists for the given table
        if table not in constraint_dict:
            constraint_dict[table] = []

        # Check if the field already has a constraint -> update it if so
        for constraint in constraint_dict[table]:
            if constraint.name == field_name:
                constraint.restricted = restricted
                constraint.values = values
                return

        # Otherwise, add a new constraint
        constraint_dict[table].append(Constraint(name=field_name, restricted=restricted, values=values))

        # Save json
        self.features_values.to_json(self._features_values_file)
