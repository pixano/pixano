# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import dataclasses
import io
import json
import logging
import os
import stat
from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, ClassVar, List, Literal, Sequence, Union, cast, overload

import lancedb
import numpy as np
import PIL.Image
import polars as pl
import pyarrow as pa
import shortuuid
from lancedb.common import DATA
from lancedb.pydantic import LanceModel
from lancedb.table import LanceTable
from pydantic import create_model
from s3path import S3Path

from pixano.datasets.queries import TableQueryBuilder
from pixano.datasets.utils.errors import DatasetAccessError, DatasetPaginationError, DatasetReplacedError
from pixano.datasets.utils.integrity import (
    IntegrityCheck,
    check_table_integrity,
    handle_integrity_errors,
    validate_arrow_batch,
    validate_batch,
)
from pixano.features.utils.image import create_mosaic, image_to_base64
from pixano.schemas import (
    Conversation,
    Entity,
    Message,
    Record,
    SchemaGroup,
    ViewEmbedding,
    build_record_embedding_schema,
    canonical_table_name_for_slot,
    is_entity_annotation,
    is_image,
    is_sequence_frame,
    is_video,
    is_view_embedding,
    media_type_of,
    validate_canonical_table_map,
)
from pixano.utils.python import to_sql_list, unique_list

from .dataset_features_values import Constraint, ConstraintDict, DatasetFeaturesValues, TableName
from .dataset_info import DatasetInfo
from .dataset_schema import _serialize_table_schema
from .dataset_stat import DatasetStatistic, SplitStatusCount
from .embedding_spaces import (
    DEFAULT_INDEX_TYPE,
    DEFAULT_METRIC,
    DEFAULT_SOURCE_VIEW,
    FIRST_TABLE,
    AmbiguousModelError,
    EmbeddingSpace,
    EmbeddingSpaces,
    is_embeddings_table,
)
from .locking import dataset_mutation_lock, dataset_write


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


#: What a file the dataset writes asks the system for: the process's umask narrows it, as for any new file.
_NEW_FILE_MODE = 0o666
#: The stamp of a file an instance could not read: equal to no file's, so that its holder reads it again.
_UNREAD = object()


def _file_stamp(path: Path) -> object:
    """What tells a file's versions apart — its inode, modification time and size —; None when it does not exist.

    The three together tell apart far more versions than the modification time alone, which a coarse
    clock gives two writes within one tick. A file that cannot be examined stamps `_UNREAD`.
    """
    try:
        status = path.stat()
    except FileNotFoundError:
        return None
    except OSError:
        return _UNREAD
    return (status.st_ino, status.st_mtime_ns, status.st_size)


def _replace_file(path: Path, content: str, permissions: int | None = None) -> None:
    """Write a file of a local disk so that a reader sees its old content or its new one, never half of it.

    The content goes to a temporary file of its own in the same directory — the rename stays within
    one filesystem, so it is atomic — renamed over `path` once on disk. The file gets `permissions`
    when given — those it had —, else those of any new file the process writes: the application and a
    worker may run as two users, and a file narrowed to its owner would be unreadable to the other.
    """
    tmp_path = path.with_name(f"{path.name}.{shortuuid.uuid()}.tmp")
    fd = os.open(tmp_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, _NEW_FILE_MODE)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
            tmp_file.write(content)
            # On disk before the rename: a crash between them leaves the old file, never an empty one.
            tmp_file.flush()
            os.fsync(tmp_file.fileno())
        if permissions is not None:
            tmp_path.chmod(permissions)
        tmp_path.replace(path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def _is_nested(query: Sequence[float] | Sequence[Sequence[float]]) -> bool:
    """Whether a search query is a list of vectors rather than one vector."""
    return len(query) > 0 and isinstance(query[0], (list, tuple, np.ndarray))


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
    _EMBEDDINGS_FILE: str = "embeddings.json"
    # The table of a dataset's first embeddings model (`embedding_spaces.FIRST_TABLE`); the others
    # are named by `embeddings.json`.
    _RECORD_EMBEDDING_TABLE: str = FIRST_TABLE
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
        self._table_handles: dict[str, LanceTable] = {}
        self._features_values_file = self.path / self._FEATURES_VALUES_FILE
        self._embeddings_file = self.path / self._EMBEDDINGS_FILE
        self._embedding_spaces = EmbeddingSpaces()
        # A space's schema, built once per table and dimension rather than at every write's refresh.
        self._embedding_schemas: dict[tuple[str, int], type[LanceModel]] = {}
        # What `embeddings.json` was when this instance last read or wrote it (`_file_stamp`).
        self._embeddings_stamp: object = None
        self._stat_file = self.path / self._STAT_FILE
        self._thumb_file = self.path / self._THUMB_FILE
        self._db_path = self.path / self._DB_PATH

        # Capture identity BEFORE reading metadata: a concurrent promotion during
        # construction must not bless an old schema with the new directory inode.
        self._directory_identity = None
        self._info_mtime_ns = None
        if not isinstance(self.path, S3Path):
            path_stat = self.path.stat()
            self._directory_identity = (path_stat.st_dev, path_stat.st_ino)
            self._info_mtime_ns = self._info_file.stat().st_mtime_ns
        self._write_depth = 0
        self.info = DatasetInfo.from_json(self._info_file)
        validate_canonical_table_map(self.info.tables)
        # The embeddings tables are internal to the search engine (not part of the public dataset
        # schema), so they are described in a sidecar and re-injected here after the canonical
        # check — DatasetInfo does not round-trip them.
        self._load_record_embedding_spaces()
        self.features_values = DatasetFeaturesValues.from_json(self._features_values_file)
        self.stats = DatasetStatistic.from_json(self._stat_file) if self._stat_file.is_file() else []
        self.thumbnail = self._thumb_file
        self.previews_path = self.path / self._PREVIEWS_PATH

        self._db_connection = self._connect()
        if self.info.spec_version < self._CURRENT_SPEC_VERSION:
            try:
                # Concurrent openers should observe the finished upgrade, not
                # fall back to an obsolete schema while another opener writes.
                with dataset_mutation_lock(self.path, timeout=5):
                    with self.write_lock():
                        if self.info.spec_version < self._CURRENT_SPEC_VERSION:
                            self._migrate_storage()
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

    def is_stale(self) -> bool:
        """Whether another process changed this dataset's metadata since it was read here.

        A long-lived holder — the API's cache — asks before serving a request: a job that gives
        the entities a new field rewrites `info.json`, and reading with the schema read before
        would leave that field out; a job that adds a model's embeddings rewrites
        `embeddings.json`. Three `stat` calls; a replaced dataset counts as changed, and so does one
        whose `embeddings.json` this instance could not read.

        A dataset on S3 is never reported changed: there is no `stat` to compare, so its
        holder serves the schema it first read until it drops the dataset — when a job ends,
        for the API (docs/specs/backend-processing.md §20).
        """
        if isinstance(self.path, S3Path):
            return False
        try:
            path_stat = self.path.stat()
            info_mtime = self._info_file.stat().st_mtime_ns
        except FileNotFoundError:
            return True
        return (
            (path_stat.st_dev, path_stat.st_ino) != self._directory_identity
            or info_mtime != self._info_mtime_ns
            or _file_stamp(self._embeddings_file) != self._embeddings_stamp
        )

    @contextmanager
    def write_lock(self):
        """Protect a mutation and refresh cached handles before its integrity reads.

        Callers performing read/modify/write operations may hold this context
        around several Dataset methods; nesting in the same thread is safe.
        """
        if isinstance(self.path, S3Path):
            # Remote Dataset access predates local add/rollback jobs. Keep its
            # existing semantics; a filesystem lock cannot protect S3 writers.
            yield
            return
        with dataset_mutation_lock(self.path):
            if self._write_depth == 0:
                path_stat = self.path.stat()
                identity = (path_stat.st_dev, path_stat.st_ino)
                if identity != self._directory_identity:
                    self.invalidate_caches(self.info.id)
                    raise DatasetReplacedError("Dataset was replaced; reload it before retrying the operation.")
                current_mtime = self._info_file.stat().st_mtime_ns
                current_info = self.info
                if current_mtime != self._info_mtime_ns:
                    current_info = DatasetInfo.from_json(self._info_file)
                    if current_info.id != self.info.id:
                        self.invalidate_caches(self.info.id)
                        raise DatasetReplacedError("Dataset was replaced; reload it before retrying the operation.")
                self._table_handles.clear()
                self._num_rows_cache = None
                self.features_values = DatasetFeaturesValues.from_json(self._features_values_file)
                # The info read replaces the one held only once it declares the embeddings tables: a
                # search on another thread never finds them gone.
                self._load_record_embedding_spaces(into=current_info)
            self._write_depth += 1
            try:
                yield
            finally:
                self._write_depth -= 1
                self._info_mtime_ns = self._info_file.stat().st_mtime_ns

    # ------------------------------------------------------------------
    # Storage-layout migrations
    # ------------------------------------------------------------------

    _CURRENT_SPEC_VERSION: int = 3

    @dataset_write
    def _migrate_storage(self) -> None:
        """Bring an older on-disk layout up to the current spec version.

        Each version adds columns that its schemas expect, backfilled with the value the
        schema defaults to: version 2 the ``Video`` time window, version 3 the
        ``review_status`` of entity annotations. Every step is idempotent, so a dataset opened
        at version 1 goes through both.

        Local openers serialize the upgrade and refresh the metadata before
        calling this method. External ``add_columns`` races converge by
        re-reading the table schema. The ``info.json`` rewrite is atomic and
        idempotent (all writers produce identical content).
        """
        if self.info.spec_version < 2:
            self._backfill_columns(is_video, {"from_timestamp": "0.0", "to_timestamp": "-1.0"})
        if self.info.spec_version < 3:
            self._backfill_columns(is_entity_annotation, {"review_status": "''"})

        self._patch_info_json({"spec_version": self._CURRENT_SPEC_VERSION})
        self.info.spec_version = self._CURRENT_SPEC_VERSION

    @dataset_write
    def ensure_entity_text_field(self, name: str) -> None:
        """Give the dataset's entities a text field, empty for the entities already there.

        For a job that writes a class on the objects it detects, on a dataset whose entities
        have nowhere to hold one — nuScenes as imported, a dataset of plain images. The schema
        class gains the field, the table gains the column, and `info.json` is rewritten, so the
        interface offers the field like any other. Idempotent: a field already declared, with its
        column, is left as it is and nothing is written — a rewrite of `info.json` would make every
        other holder of the dataset stale (`is_stale`), and a job calls this once per chunk.

        Args:
            name: The field to add, typed as text.

        Raises:
            DatasetAccessError: The dataset declares no entities.
        """
        declared = self.info.entity
        if declared is None:
            raise DatasetAccessError(f"Dataset {self.id} declares no entities.")
        schema: type[Entity] = declared
        table_name = canonical_table_name_for_slot("entity")
        if name in schema.model_fields and name in self.open_table(table_name).schema.names:
            return
        if name not in schema.model_fields:
            schema = create_model(schema.__name__, __base__=schema, **{name: (str, "")})  # type: ignore[call-overload]
            self.info.entity = schema
            self.info.tables[table_name] = schema
            self._table_handles.pop(table_name, None)
        self._backfill_columns(lambda candidate: candidate is schema, {name: "''"})
        self._patch_info_json({"entity": _serialize_table_schema(schema)})

    def _patch_info_json(self, fields: dict[str, Any]) -> None:
        """Set top-level fields of `info.json`, leaving the rest of the document as written.

        Re-serializing `self.info` would persist what `DatasetInfo.from_json` dropped: the views
        whose schema this build cannot deserialize. The raw document keeps them. On a local
        disk, the file is replaced whole (`_replace_file`), so a reader never sees a half-written
        file, and keeps its permissions. Callers hold the write lock, since another writer's
        read-modify-write would race this one.

        Args:
            fields: The top-level fields to set, already serialized.
        """
        info_json = json.loads(self._info_file.read_text(encoding="utf-8"))
        info_json.update(fields)
        content = json.dumps(info_json, indent=4)
        if isinstance(self._info_file, S3Path):
            # An object store replaces an object whole, so no reader sees half of it; and it has
            # neither a directory to hold a temporary file nor permissions to keep.
            self._info_file.write_text(content, encoding="utf-8")
            return
        _replace_file(self._info_file, content, stat.S_IMODE(self._info_file.stat().st_mode))

    def _backfill_columns(self, applies_to: Callable[[type], bool], columns: dict[str, str]) -> None:
        """Add the columns missing from every table whose schema ``applies_to`` selects.

        Args:
            applies_to: Which table schemas get the columns.
            columns: Column name to the SQL expression of its backfilled value.
        """
        for table_name, schema_cls in self.info.tables.items():
            if not applies_to(schema_cls):
                continue
            table = self.open_table(table_name)
            missing = {column: expr for column, expr in columns.items() if column not in table.schema.names}
            if not missing:
                continue
            try:
                table.add_columns(missing)
            except Exception:
                self._table_handles.pop(table_name, None)  # re-read the live schema, not a cached handle
                still_missing = [
                    column for column in missing if column not in self.open_table(table_name).schema.names
                ]
                if still_missing:
                    raise
            finally:
                self._table_handles.pop(table_name, None)

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
        with dataset_mutation_lock(path):
            return cls._create_locked(path, info)

    @classmethod
    def _create_locked(cls, path: Path, info: DatasetInfo) -> "Dataset":
        """Create storage while the target path is reserved by the caller."""
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

    def get_splits_count(self) -> list[SplitStatusCount]:
        """Get record counts grouped by split and status.

        Opens the record table as PyArrow, groups by ``["split", "status"]``
        and aggregates counts.  If the ``status`` column does not exist the
        table is old-schema and an empty list is returned for backward
        compatibility.

        Returns:
            List of SplitStatusCount sorted by split asc then status asc.
        """
        try:
            arrow_table = self.open_table(SchemaGroup.RECORD.value).to_arrow()
        except Exception:
            return []

        if "status" not in arrow_table.column_names:
            return []

        grouped = arrow_table.group_by(["split", "status"]).aggregate([("id", "count")])
        grouped = grouped.rename_columns(["split", "status", "count"])
        grouped = grouped.sort_by([("split", "ascending"), ("status", "ascending")])

        result: list[SplitStatusCount] = []
        splits = grouped.column("split").to_pylist()
        statuses = grouped.column("status").to_pylist()
        counts = grouped.column("count").to_pylist()
        for split, status, count in zip(splits, statuses, counts):
            result.append(SplitStatusCount(split=split, status=status, count=count))
        return result

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

    @dataset_write
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

        Hold :meth:`write_lock` when mutating the returned LanceDB handle so
        local imports and rollback cannot run concurrently with that mutation.

        Args:
            name: Name of the table to open.

        Returns:
            Dataset table.
        """
        if name not in self.info.tables:
            raise DatasetAccessError(f"Table {name} not found in dataset")

        cached = self._table_handles.get(name)
        if cached is not None:
            return cached
        table = self._db_connection.open_table(name)

        schema_table = self.info.tables[name]
        if is_view_embedding(schema_table):
            schema_table = cast(type[ViewEmbedding], schema_table)
            try:
                schema_table.get_embedding_fn_from_table(self, name, table.schema.metadata)
            except TypeError:  # no embedding function
                pass
        # A cached handle stays on the table version it opened, since the connection sets no
        # read consistency interval: what another instance or process writes (the worker, the
        # API) is not seen through it. `write_lock` clears the cache, so this instance's own
        # writes and the reads made under the lock see the latest version, and Dataset-level
        # cache invalidation drops the whole instance. Any other read may be stale.
        self._table_handles[name] = table
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
        force_full_scan: bool = False,
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
        force_full_scan: bool = False,
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
        force_full_scan: bool = False,
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
            force_full_scan: Force the safe full-scan-then-slice path (for a
                ``where`` using an operator a scalar index can't serve, e.g. ``!=``
                or ``LIKE``). See `TableQueryBuilder.force_full_scan`.

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
                        .force_full_scan(force_full_scan)
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
                    .force_full_scan(force_full_scan)
                    .limit(limit)
                    .offset(skip)
                )
            if sortcol is not None and order is not None:
                descending = order == "desc"
                # Append `id` as a stable final tie-break so pagination over a
                # non-unique sort column is deterministic — rows that are equal
                # on `sortcol` keep a fixed order across pages. `id` is unique
                # and BTREE-indexed. Skip when already sorting by `id`, or for
                # the `#count-join` ordering (which requires a single order key).
                if sortcol == "id" or sortcol.startswith("#"):
                    query = query.order_by(sortcol, descending)
                else:
                    query = query.order_by([sortcol, "id"], [descending, False])
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

        rows = TableQueryBuilder(table).select(columns).where(where).limit(batch_size).to_list()
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

    def get_neighbors(
        self,
        record_id: str,
        table_name: str = SchemaGroup.RECORD.value,
        where: str | None = None,
        sortcol: str | None = None,
        order: str | None = None,
    ) -> dict[str, Any]:
        """Locate a record within a filtered, sorted result set and its neighbors.

        Powers item-to-item navigation in the explorer: given the same filter and
        sort the table view uses, return the ids immediately before and after
        ``record_id`` and its 1-based position, so previous/next stay inside the
        current result set instead of walking the whole dataset.

        The scan projects only the ``id`` column (ordered with an ``id`` tie-break
        for a stable order) and returns a tiny payload. For a record that is not
        in the filtered set, ``prev``/``next``/``position`` are ``None``.

        Args:
            record_id: The record to locate.
            table_name: Table to navigate (defaults to the record table).
            where: Where clause matching the explorer's active filter.
            sortcol: Column to order by (defaults to ``id``).
            order: Sort order, ``"asc"`` or ``"desc"`` (defaults to ``"asc"``).

        Returns:
            ``{"prev": str | None, "next": str | None, "position": int | None,
            "total": int}``.
        """
        table = self.open_table(table_name)
        total = table.count_rows(where) if where else table.count_rows()

        sortcol = sortcol or "id"
        descending = order == "desc"
        query = TableQueryBuilder(table, self._db_connection).select(["id"])
        if where is not None:
            query = query.where(where)
        if sortcol == "id":
            query = query.order_by("id", descending)
        else:
            query = query.order_by([sortcol, "id"], [descending, False])
        ordered_ids = [row["id"] for row in query.to_list()]

        try:
            index = ordered_ids.index(record_id)
        except ValueError:
            return {"prev": None, "next": None, "position": None, "total": total}

        return {
            "prev": ordered_ids[index - 1] if index > 0 else None,
            "next": ordered_ids[index + 1] if index < len(ordered_ids) - 1 else None,
            "position": index + 1,
            "total": total,
        }

    @dataset_write
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

    @dataset_write
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
        SchemaGroup.TIMESERIES,
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

    @dataset_write
    def add_records(
        self,
        data: dict[str, LanceModel | list[LanceModel]],
        check_integrity: Literal["raise", "warn", "none"] = "raise",
        stamp_timestamps: bool = True,
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
            stamp_timestamps: Overwrite ``created_at``/``updated_at`` with
                now (default). Importers pass ``False`` so explicitly
                provided timestamps (e.g. a re-imported export) survive;
                rows without explicit values keep their construction-time
                defaults, which are equally "now".
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
            if stamp_timestamps:
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

    @dataset_write
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
            for table_name in ordered_tables:
                arrow_batch = arrow_payloads.get(table_name)
                if arrow_batch is None:
                    continue
                upsert_known = {tname: ids for tname, ids in accumulated.items() if tname != table_name}
                validate_arrow_batch(
                    table_name,
                    arrow_batch,
                    upsert_known,
                    self,
                    raise_or_warn=check_integrity,
                    pending_ids=pending_ids,
                )
                if "id" in arrow_batch.schema.names:
                    accumulated.setdefault(table_name, set()).update(
                        value.as_py() for value in arrow_batch.column("id") if value.as_py()
                    )

        counts: dict[str, int] = {}
        for table_name in ordered_tables:
            table = self.open_table(table_name)
            if table_name in row_payloads:
                rows = row_payloads[table_name]
                self._stamp_upsert_timestamps(table, rows)
                table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
                    self._in_table_order(table, rows)
                )
                counts[table_name] = len(rows)
            else:
                arrow_table = self._with_timestamp_columns(table, arrow_payloads[table_name])
                table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
                    self._in_table_order(table, arrow_table)
                )
                counts[table_name] = arrow_table.num_rows

        if SchemaGroup.RECORD.value in counts:
            self._num_rows_cache = None
        return counts

    @staticmethod
    def _in_table_order(table: LanceTable, data: list[LanceModel] | pa.Table) -> list[LanceModel] | pa.Table:
        """Give an upsert its columns in the order the table stores them.

        A column added by a storage migration lands at the end of the Lance schema, while the
        pydantic schema may declare it in the middle — ``review_status`` sits after
        ``view_id``. Lance's ``merge_insert`` does not match columns by name once the ``id``
        index covers fragments written in the other order: the upsert then fails, or corrupts
        the match ("fragment id does not exist", "ambiguous merge insert"). Rows whose schema
        already matches the table are passed through untouched.

        Only data holding exactly the table's columns is reordered. Rebuilding rows against
        the table's schema would drop every field the table lacks and null every column the
        rows lack: on a dataset whose migration failed, a write carrying a review status would
        be answered as stored and lose it. Any other set of columns reaches Lance as it came,
        which refuses a column the table does not store and leaves alone a column the rows do
        not carry.
        """
        names = table.schema.names
        if isinstance(data, pa.Table):
            if data.schema.names == names or set(data.schema.names) != set(names):
                return data
            return data.select(names)
        if not data:
            return data
        fields = list(type(data[0]).model_fields)
        if fields == names or set(fields) != set(names):
            return data
        return pa.Table.from_pylist([row.model_dump() for row in data], schema=table.schema)

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

    # Standard filter columns the REST/query layers put in where clauses, with
    # the index type suited to their cardinality. When EVERY predicate column
    # of a query is index-covered, lancedb applies limit/offset after the
    # filter — TableQueryBuilder's fast path depends on this census.
    FILTER_INDEX_COLUMNS: ClassVar[dict[str, str]] = {
        "id": "BTREE",
        "record_id": "BTREE",
        "entity_id": "BTREE",
        "view_id": "BTREE",
        "frame_id": "BTREE",
        "tracklet_id": "BTREE",
        "frame_index": "BTREE",
        "logical_name": "BITMAP",
        "split": "BITMAP",
        "status": "BITMAP",
        "source_type": "BITMAP",
    }

    @dataset_write
    def create_scalar_indexes(
        self,
        columns: Sequence[str] | None = None,
        tables: Sequence[str] | None = None,
    ) -> None:
        """Create scalar indexes on the given columns of the given tables.

        Idempotent: columns that are already indexed or absent from a table's
        schema are skipped. Indexes make ``merge_insert``, foreign-key lookups,
        export paging, and filtered pagination scale past full-table scans.

        Args:
            columns: Column names to index where present. Defaults to the
                standard filter columns (``FILTER_INDEX_COLUMNS``).
            tables: Table names to index. Defaults to every dataset table.
        """
        wanted = list(columns) if columns is not None else list(self.FILTER_INDEX_COLUMNS)
        table_names = list(tables) if tables is not None else list(self.info.tables.keys())
        for table_name in table_names:
            table = self.open_table(table_name)
            indexed_columns: set[str] = set()
            for index in table.list_indices():
                indexed_columns.update(getattr(index, "columns", None) or [])
            schema_names = set(table.schema.names)
            for column in wanted:
                if column in schema_names and column not in indexed_columns:
                    table.create_scalar_index(column, index_type=self.FILTER_INDEX_COLUMNS.get(column, "BTREE"))

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

    @dataset_write
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

    @dataset_write
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
    @dataset_write
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
        table.merge_insert("id").when_matched_update_all().when_not_matched_insert_all().execute(
            self._in_table_order(table, data)
        )

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

    # ------------------------------------------------------------------
    # Record-level embeddings & semantic search
    # ------------------------------------------------------------------

    def _load_record_embedding_spaces(self, into: DatasetInfo | None = None) -> None:
        """Read the embedding spaces from `embeddings.json`, and declare each space's table in `info.tables`.

        A document that cannot be read — not JSON, no space it can read — degrades to "no embeddings"
        instead of raising: a broken embeddings file must never make the whole dataset unloadable.
        Neither it nor one read in part (`EmbeddingSpaces.fully_read`) is rewritten by any write but the
        deletion of every model's embeddings. A file that cannot be opened — a transient error, its
        permissions — leaves the spaces held as they were, not to be rewritten either, and this instance
        stale (`is_stale`), so that its holder reads it again.

        Args:
            into: The info to declare the tables in and then hold — one `write_lock` just read —;
                the one held when None.
        """
        remote = isinstance(self._embeddings_file, S3Path)
        # Stamped before it is read: a file replaced in between leaves this instance stale, not wrong.
        stamp = None if remote else _file_stamp(self._embeddings_file)
        try:
            content = self._embeddings_file.read_bytes() if self._embeddings_file.is_file() else None
        except OSError as exc:
            logger.warning("Dataset %s: cannot read %s: %s", self.path, self._EMBEDDINGS_FILE, exc)
            self._adopt_embedding_spaces(dataclasses.replace(self._embedding_spaces, fully_read=False), into)
            self._embeddings_stamp = _UNREAD
            return
        spaces = EmbeddingSpaces()
        if content is not None:
            try:
                spaces = EmbeddingSpaces.from_document(json.loads(content.decode("utf-8")))
            except ValueError as exc:  # json.JSONDecodeError and UnicodeDecodeError are ones
                logger.warning("Dataset %s: ignoring unreadable %s: %s", self.path, self._EMBEDDINGS_FILE, exc)
                spaces = EmbeddingSpaces(fully_read=False)
        self._adopt_embedding_spaces(spaces, into)
        self._embeddings_stamp = stamp

    def _adopt_embedding_spaces(self, spaces: EmbeddingSpaces, into: DatasetInfo | None = None) -> None:
        """Hold these spaces, their tables declared in `info.tables` in place of the previous ones'.

        `info.tables` is replaced whole, not changed in place, and an info just read is held only
        once it declares the tables: a request reading them on another thread sees the tables before
        or after, never one gone in between.

        Args:
            spaces: The spaces to hold.
            into: The info to declare the tables in and then hold; the one held when None.
        """
        info = self.info if into is None else into
        held = {space.table for space in self._embedding_spaces.spaces}
        tables = {name: schema for name, schema in info.tables.items() if name not in held}
        for space in spaces.spaces:
            key = (space.table, space.dim)
            if key not in self._embedding_schemas:
                self._embedding_schemas[key] = build_record_embedding_schema(space.dim)
            tables[space.table] = self._embedding_schemas[key]
        for gone in held - {space.table for space in spaces.spaces}:
            self._table_handles.pop(gone, None)
        info.tables = tables
        self.info = info
        self._embedding_spaces = spaces

    def _writable_spaces(self) -> EmbeddingSpaces:
        """The spaces a write of the description starts from: read again on S3, which no lock refreshes.

        Raises:
            DatasetAccessError: `embeddings.json` could not be read entirely: rewritten, it would lose
                the spaces this build left out.
        """
        if isinstance(self._embeddings_file, S3Path):
            self._load_record_embedding_spaces()
        if not self._embedding_spaces.fully_read:
            raise DatasetAccessError(
                f"Dataset {self.id}: {self._EMBEDDINGS_FILE} cannot be read entirely, so it is not rewritten. "
                "Repair it, or delete every model's embeddings to compute them again."
            )
        return self._embedding_spaces

    def _save_embedding_spaces(self, spaces: EmbeddingSpaces) -> None:
        """Write these spaces to `embeddings.json` and hold them; no space left removes the file.

        On a local disk the file is replaced whole (`_replace_file`), so a reader never sees half of
        it, and keeps its permissions; a new one gets those of any file the process writes, as
        `embeddings.json` always did. Callers hold the write lock.
        """
        remote = isinstance(self._embeddings_file, S3Path)
        if not spaces.spaces:
            self._embeddings_file.unlink(missing_ok=True)
        elif remote:
            # An object store replaces an object whole, and has no permissions to keep.
            self._embeddings_file.write_text(json.dumps(spaces.to_document(), indent=4), encoding="utf-8")
        else:
            try:
                permissions: int | None = stat.S_IMODE(self._embeddings_file.stat().st_mode)
            except FileNotFoundError:
                permissions = None
            _replace_file(self._embeddings_file, json.dumps(spaces.to_document(), indent=4), permissions)
        self._adopt_embedding_spaces(spaces)
        self._embeddings_stamp = None if remote else _file_stamp(self._embeddings_file)

    def _embedding_space(self, model: str | None) -> EmbeddingSpace:
        """The space a reader names — its id or its model's name —, the default one when none is named.

        Raises:
            DatasetAccessError: The dataset has no embeddings, or none of that model.
        """
        space = self._embedding_spaces.find(model)
        if space is None:
            if model:
                raise DatasetAccessError(f"Dataset {self.id} has no embeddings of model '{model}'.")
            raise DatasetAccessError(f"Dataset {self.id} has no record embeddings.")
        return space

    def _space_written(self, space_id: str | None) -> EmbeddingSpace:
        """The space a writer names, by its id only — a name two checkpoints share names no single one —;
        the default one when None.

        Raises:
            ValueError: The id is empty: the default one is None, not an empty name.
            DatasetAccessError: The dataset has no space of this id, or none at all.
        """
        if space_id is None:
            return self._embedding_space(None)
        if not space_id:
            raise ValueError("An embedding space is named by its id; None names the default one.")
        space = self._embedding_spaces.get(space_id)
        if space is None:
            raise DatasetAccessError(f"Dataset {self.id} has no embedding space '{space_id}'.")
        return space

    def record_embedding_spaces(self) -> list[dict[str, Any]]:
        """Every embedding space of the dataset, one per model, in the order they were created — a model
        recomputed from nothing last.

        Returns:
            Each space's description (`EmbeddingSpace.as_document`), with `default` saying whether
            a search uses it when no model is named.
        """
        return [
            {**space.as_document(), "default": space.id == self._embedding_spaces.default}
            for space in self._embedding_spaces.spaces
        ]

    def has_record_embeddings(self, model: str | None = None) -> bool:
        """Whether this dataset has embeddings: of the model named — its space's id or its name —, or any."""
        return self._embedding_spaces.find(model) is not None

    def record_embeddings_fully_read(self) -> bool:
        """Whether `embeddings.json` was read entirely; if not, no write but deleting every model's changes it.

        For a caller about to compute embeddings, to refuse before computing what it could not write.
        """
        return self._embedding_spaces.fully_read

    def record_embedding_space(self, model: str | None = None) -> dict[str, Any] | None:
        """One model's embedding space — its id, table, model, checkpoint, dimension, metric —, or None.

        Args:
            model: The model — its space's id or its name —; the default one when None.
        """
        space = self._embedding_spaces.find(model)
        return space.as_document() if space is not None else None

    def matching_record_embedding_space(
        self, model_id: str, checkpoint: str = "", dim: int | None = None
    ) -> dict[str, Any] | None:
        """The space of a model known by its name and checkpoint (`EmbeddingSpace.is_model`), or None.

        For a writer that knows the model it runs rather than its space: the space to index, or to
        empty before computing the model again.

        Args:
            model_id: The model's name.
            checkpoint: The weights loaded under that name; empty when the caller cannot tell.
            dim: The vectors' dimension, when known: it tells apart two checkpoints a space or the
                caller does not name.
        """
        space = self._embedding_spaces.matching(model_id, checkpoint or "", dim)
        return space.as_document() if space is not None else None

    def record_embedding_health(self, model: str | None = None) -> dict[str, Any]:
        """Health check of one model's embedding storage.

        The description alone advertises semantic search; the physical LanceDB table is only
        touched at query time, so a crashed job or external deletion can leave the feature
        advertised but broken. This reads no vector, but it is not metadata only: it reads the
        `view_id` of every row of the space's table to count the media embedded, and counts
        the rows of each image table. Its cost grows with the number of vectors, and it runs
        before every semantic search and every request for the explorer's filter schema;
        keeping it cheap is an open question (`docs/OPEN_QUESTIONS.md`).

        An embedding belongs to a medium, so completeness is counted in media: ``partial``
        means some still image has no vector. Counting records instead said "complete" for a
        record with one camera embedded out of six, and "partial" forever on a dataset whose
        records hold no image at all, such as nuScenes' lidar sweeps.

        Args:
            model: The model — its space's id or its name —; the default one when None.

        Returns:
            ``{"status", "id", "model_id", "checkpoint", "dim", "rows", "records", "media",
            "embedded_media", "detail"}`` where status is one of ``absent`` (no such space),
            ``missing_table``, ``empty``, ``dim_mismatch``, ``corrupt`` (a table, or `embeddings.json`
            when it names no such space, that cannot be read), ``partial`` (fewer media embedded than
            media) or ``ready``.
        """
        space = self._embedding_spaces.find(model)
        base: dict[str, Any] = {
            "status": "absent",
            "id": None,
            "model_id": None,
            "checkpoint": None,
            "dim": None,
            "rows": 0,
            "records": self.num_rows,
            "media": self._still_image_count(),
            "embedded_media": 0,
            "detail": None,
        }
        if space is None:
            if not self._embedding_spaces.fully_read:
                # Broken rather than absent: a computation would be refused, a recomputation from
                # nothing repairs it.
                detail = f"{self._EMBEDDINGS_FILE} cannot be read entirely."
                return {**base, "status": "corrupt", "detail": detail}
            return base
        base.update(id=space.id, model_id=space.model_id, checkpoint=space.checkpoint, dim=space.dim)

        try:
            if space.table not in self._db_connection.list_tables().tables:
                return {**base, "status": "missing_table", "detail": "The embeddings table is missing."}
            table = self.open_table(space.table)
        except Exception as exc:  # noqa: BLE001 - corrupt storage must degrade, not raise
            return {**base, "status": "corrupt", "detail": f"The embeddings table cannot be opened: {exc}"}

        try:
            rows = table.count_rows()
            vector_field = table.schema.field("vector")
            stored_dim = getattr(vector_field.type, "list_size", None)
        except Exception as exc:  # noqa: BLE001
            return {**base, "status": "corrupt", "detail": f"The embeddings table cannot be read: {exc}"}

        base["rows"] = rows
        if rows == 0:
            return {**base, "status": "empty", "detail": "The embeddings table has no vectors."}
        if stored_dim is not None and space.dim != int(stored_dim):
            return {
                **base,
                "status": "dim_mismatch",
                "detail": f"Stored vectors have dim {stored_dim} but the descriptor says {space.dim}.",
            }
        # Counted in distinct media rather than rows: a table can hold rows that name no medium
        # (written per record before embeddings were per medium) or two rows for one medium
        # (the application's in-process path next to the worker's), and neither makes a medium
        # embedded.
        try:
            view_ids = table.search().select(["view_id"]).limit(rows).to_arrow().column("view_id").to_pylist()
        except Exception as exc:  # noqa: BLE001
            return {**base, "status": "corrupt", "detail": f"The embeddings table cannot be read: {exc}"}
        base["embedded_media"] = len({view_id for view_id in view_ids if view_id})
        if base["embedded_media"] < base["media"]:
            return {
                **base,
                "status": "partial",
                "detail": f"{base['embedded_media']} of {base['media']} media embedded.",
            }
        return {**base, "status": "ready"}

    def _still_image_count(self) -> int:
        """How many still images the dataset holds — the media an embedding job covers today.

        Video frames are images to the schemas but belong to their video, which no embedding
        job covers yet.
        """
        total = 0
        for table_name, schema in self.info.tables.items():
            if media_type_of(schema) == "image":
                try:
                    total += self.open_table(table_name).count_rows()
                except Exception:  # noqa: BLE001 - a health check must degrade, not raise
                    continue
        return total

    @dataset_write
    def drop_record_embeddings(self, space_id: str | None = None) -> None:
        """Delete one model's embeddings — its space and its table —, or every model's.

        Safe on missing or corrupt tables: used to recompute a model from nothing, or to escape
        a state where the description advertises embeddings whose table is broken. The description
        is written first, the table dropped next: a drop that fails leaves a table no description
        names — which the deletion of every model's collects —, never a description naming no table.
        When the default model goes, the first one left becomes the default.

        Args:
            space_id: The space's id; every model's when None — the only write a description that
                cannot be read entirely allows, the tables it no longer names included. A space the
                dataset does not hold leaves it as it is.

        Raises:
            ValueError: The id is empty: every model's is None, not an empty name.
            DatasetAccessError: `embeddings.json` cannot be read entirely, and one space is named.
        """
        if space_id is None:
            held = {space.table for space in self._embedding_spaces.spaces}
            # A table `info.json` declares is the dataset's, whatever its name.
            declared = set(self.info.tables) - held
            listed = set(self._db_connection.list_tables().tables)
            self._save_embedding_spaces(EmbeddingSpaces())
            self._drop_embedding_tables({name for name in held | listed if is_embeddings_table(name)} - declared)
            return
        if not space_id:
            raise ValueError("An embedding space is named by its id; every model's is None.")
        spaces = self._writable_spaces()
        space = spaces.get(space_id)
        if space is None:
            return
        self._save_embedding_spaces(spaces.without(space.id))
        self._drop_embedding_tables({space.table})

    @dataset_write
    def empty_model_record_embeddings(
        self, model_id: str, checkpoint: str = "", index_type: str | None = None
    ) -> dict[str, Any] | None:
        """Empty the embeddings of a model known by its name and checkpoint, keeping its space.

        For a writer about to compute its model again from nothing, before it knows its vectors'
        dimension — the model's own, unchanged. The space keeps its id, its place and the default
        a search uses; its table is created again, empty, and the space records the checkpoint and
        the vector index told. It is looked for and emptied under one lock, the description read
        again under it, so that a space another process recorded meanwhile is found. The other
        models' embeddings are left as they are.

        A caller that does not tell its checkpoint empties only a space recorded without one: a
        space of a checkpoint told may hold another weights' vectors than those the caller runs.

        Args:
            model_id: The model's name.
            checkpoint: The weights loaded under that name; empty when the caller cannot tell.
            index_type: The vector index the table is to get once filled; the space's when None.

        Returns:
            The space emptied, or None when the dataset holds none of that model.

        Raises:
            DatasetAccessError: `embeddings.json` cannot be read entirely.
            AmbiguousModelError: No checkpoint told, and a space of that name records one; or several
                spaces match.
        """
        checkpoint = checkpoint or ""
        spaces = self._writable_spaces()
        if not checkpoint:
            told = [space.checkpoint for space in spaces.spaces if space.model_id == model_id and space.checkpoint]
            if told:
                raise AmbiguousModelError(
                    f"model '{model_id}' holds the embeddings of the checkpoints {', '.join(told)}: the weights "
                    "served now must be told, to know whether they are those"
                )
        space = spaces.matching(model_id, checkpoint, strict=True)
        if space is None:
            return None
        emptied = dataclasses.replace(
            space, checkpoint=checkpoint or space.checkpoint, index_type=index_type or space.index_type
        )
        self._create_embedding_table(emptied, mode="overwrite")
        if emptied != space:
            self._save_embedding_spaces(spaces.replacing(emptied))
        return emptied.as_document()

    def _drop_embedding_tables(self, names: set[str]) -> None:
        """Drop these embeddings tables, each as far as it goes: a corrupt one must not block a repair."""
        for table_name in sorted(names):
            try:
                self._db_connection.drop_table(table_name, ignore_missing=True)
            except Exception as exc:  # noqa: BLE001 - dropping a corrupt table must not block repair
                logger.warning("Dataset %s: dropping the embeddings table %s failed: %s", self.path, table_name, exc)
            self._table_handles.pop(table_name, None)

    @dataset_write
    def ensure_record_embedding_space(
        self,
        model_id: str,
        checkpoint: str,
        dim: int,
        metric: str = DEFAULT_METRIC,
        source_view: str = DEFAULT_SOURCE_VIEW,
        index_type: str = DEFAULT_INDEX_TYPE,
    ) -> dict[str, Any]:
        """The space of a model, created with its table when the dataset holds none of it.

        A model is its name and its checkpoint (`EmbeddingSpace.is_model`): another checkpoint is
        another space, and so is a space of that name that does not say its checkpoint at another
        dimension. One that does not say it at this dimension is the model's, and learns it. The
        first space a dataset holds becomes its default. A space whose table went missing gets an
        empty one back. Idempotent: a space there already is left as it is.

        Args:
            model_id: The model's name.
            checkpoint: The weights loaded under that name; empty when the caller cannot tell.
            dim: The vectors' dimension.
            metric: The distance a search ranks them by, for a new space.
            source_view: The views the vectors are computed from, for a new space.
            index_type: The vector index the table gets once filled, for a new space.

        Returns:
            The space's description (`EmbeddingSpace.as_document`).

        Raises:
            DatasetAccessError: The dataset holds that very model — name and checkpoint — at another
                dimension, or its `embeddings.json` cannot be read entirely.
            AmbiguousModelError: No checkpoint told, and several spaces of that name at that dimension.
        """
        checkpoint = checkpoint or ""
        dim = int(dim)
        spaces = self._writable_spaces()
        space = spaces.matching(model_id, checkpoint, dim, strict=True)
        if space is None:
            space = spaces.new_space(model_id, checkpoint, dim, metric, source_view, index_type)
            # A table of that name no description names holds nothing to keep: one a run created before
            # failing to record its space, or one a deletion could not drop.
            self._create_embedding_table(space, mode="overwrite")
            self._save_embedding_spaces(spaces.with_space(space))
            return space.as_document()
        if space.dim != dim:
            raise DatasetAccessError(
                f"Dataset {self.id} holds embeddings of model '{model_id}' ({checkpoint}) of dimension "
                f"{space.dim}, not {dim}."
            )
        if checkpoint and not space.checkpoint:
            spaces = spaces.with_checkpoint(space, checkpoint)
            space = spaces.get(space.id) or space
            self._save_embedding_spaces(spaces)
        if space.table not in self._db_connection.list_tables().tables:
            self._create_embedding_table(space, mode="create")
        return space.as_document()

    def _create_embedding_table(self, space: EmbeddingSpace, mode: str) -> None:
        """Create a space's table, empty, without rewriting `info.json`: `embeddings.json` declares it."""
        self._db_connection.create_table(
            name=space.table, schema=build_record_embedding_schema(space.dim), mode=mode, embedding_functions=None
        )
        self._table_handles.pop(space.table, None)

    @dataset_write
    def set_default_record_embedding_space(self, space_id: str) -> dict[str, Any]:
        """Make a space the one a search uses when none is named.

        Args:
            space_id: The space's id.

        Returns:
            The space's description.

        Raises:
            ValueError: The id is empty.
            DatasetAccessError: The dataset has no space of this id, or its `embeddings.json` cannot be
                read entirely.
        """
        if not space_id:
            raise ValueError("An embedding space is named by its id.")
        spaces = self._writable_spaces()
        space = spaces.get(space_id)
        if space is None:
            raise DatasetAccessError(f"Dataset {self.id} has no embedding space '{space_id}'.")
        if spaces.default != space.id:
            self._save_embedding_spaces(spaces.with_default(space.id))
        return space.as_document()

    @dataset_write
    def create_record_embedding_table(
        self,
        dim: int,
        model_id: str,
        metric: str = DEFAULT_METRIC,
        source_view: str = DEFAULT_SOURCE_VIEW,
        index_type: str = DEFAULT_INDEX_TYPE,
        checkpoint: str = "",
    ) -> dict[str, Any]:
        """Create a model's embeddings anew — its table empty —, in place of the space it had.

        The other models' embeddings are left as they are, and so is the default model: the new
        space is the default if the one it replaces was, or if it is the dataset's first. For a
        caller that recomputes a model from nothing; `ensure_record_embedding_space` keeps what the
        model wrote. The description is written once, the new table created before and the old one
        dropped after.

        Args:
            dim: Embedding dimensionality.
            model_id: Identifier of the model that produced the vectors.
            metric: Distance metric (``cosine``/``l2``/``dot``).
            source_view: Logical view the embeddings were computed from.
            index_type: LanceDB vector index type to build once populated.
            checkpoint: The weights loaded under that name; empty when the caller cannot tell.

        Returns:
            The new space's description: the table to write the vectors to is its own.

        Raises:
            DatasetAccessError: The dataset's `embeddings.json` cannot be read entirely.
            AmbiguousModelError: No checkpoint told, and several spaces of that name at that dimension.
        """
        checkpoint = checkpoint or ""
        dim = int(dim)
        spaces = self._writable_spaces()
        replaced = spaces.matching(model_id, checkpoint, dim, strict=True)
        kept = spaces.without(replaced.id) if replaced is not None else spaces
        # A space of its own, not `ensure_record_embedding_space`'s: a caller that does not tell its
        # checkpoint would be handed the space of another checkpoint of that name, vectors included.
        space = kept.new_space(model_id, checkpoint, dim, metric, source_view, index_type)
        updated = kept.with_space(space)
        if replaced is not None and replaced.id == spaces.default:
            updated = updated.with_default(space.id)
        self._create_embedding_table(space, mode="overwrite")
        self._save_embedding_spaces(updated)
        if replaced is not None and replaced.table != space.table:
            self._drop_embedding_tables({replaced.table})
        return space.as_document()

    @dataset_write
    def upsert_record_embeddings(
        self,
        model_id: str,
        checkpoint: str,
        rows: list[dict[str, Any]],
        metric: str = DEFAULT_METRIC,
        source_view: str = DEFAULT_SOURCE_VIEW,
        index_type: str = DEFAULT_INDEX_TYPE,
    ) -> dict[str, Any]:
        """Write a model's vectors into its space, created when the dataset holds none, replacing rows by id.

        The space is found or created, and the rows written, under one acquisition of the write
        lock, which reads the description again: a space another process created meanwhile is
        found, not created twice, and one it deleted is created again, never written into from
        what this instance last read.

        Args:
            model_id: The model's name.
            checkpoint: The weights loaded under that name; empty when the caller cannot tell.
            rows: Dicts with ``id``, ``record_id``, ``view_id`` and ``vector``, all of one dimension.
            metric: The distance a search ranks them by, for a new space.
            source_view: The views the vectors are computed from, for a new space.
            index_type: The vector index the table gets once filled, for a new space.

        Returns:
            The space's description (`EmbeddingSpace.as_document`).

        Raises:
            ValueError: No row.
            DatasetAccessError: The dataset holds that very model at another dimension, or its
                `embeddings.json` cannot be read entirely.
            AmbiguousModelError: No checkpoint told, and several spaces of that name at that dimension.
        """
        if not rows:
            raise ValueError("No vector to write.")
        space = self.ensure_record_embedding_space(
            model_id, checkpoint, len(rows[0]["vector"]), metric, source_view, index_type
        )
        schema = self.info.tables[space["table"]]
        instances = [
            schema(
                id=row["id"],
                record_id=row["record_id"],
                view_id=row.get("view_id", ""),
                frame_id=row.get("frame_id", ""),
                vector=row["vector"],
            )
            for row in rows
        ]
        self.update_data(space["table"], instances)
        return space

    @dataset_write
    def add_record_embeddings(self, rows: list[dict[str, Any]], space_id: str | None = None) -> None:
        """Append rows to one space's embeddings table (plain float vectors, no model run here).

        Args:
            rows: Dicts with at least ``record_id`` and ``vector``; ``id``/``view_id`` optional.
            space_id: The space's id; the default one when None.

        Raises:
            ValueError: The id is empty.
            DatasetAccessError: The dataset has no such space; `ensure_record_embedding_space` makes one.
        """
        space = self._space_written(space_id)
        schema = self.info.tables[space.table]
        instances = [
            schema(
                id=row.get("id") or shortuuid.uuid(),
                record_id=row["record_id"],
                view_id=row.get("view_id", ""),
                frame_id=row.get("frame_id", ""),
                vector=row["vector"],
            )
            for row in rows
        ]
        self.add_data(space.table, instances, raise_or_warn="none")

    @dataset_write
    def build_record_embedding_index(self, space_id: str | None = None) -> None:
        """Build the vector + record_id indexes on one space's embeddings table.

        The vector (ANN) index needs enough rows to train; when there are too few, it is skipped
        and search falls back to an exact brute-force scan (still correct).

        Args:
            space_id: The space's id; the default one when None.

        Raises:
            ValueError: The id is empty.
            DatasetAccessError: The dataset has no such space.
        """
        space = self._space_written(space_id)
        table = self.open_table(space.table)
        try:
            table.create_scalar_index("record_id", index_type="BTREE")
        except Exception:  # pragma: no cover - already indexed / lancedb quirk
            logger.debug("record_id scalar index already present or unavailable", exc_info=True)
        try:
            table.create_index(metric=space.metric, index_type=space.index_type, vector_column_name="vector")
        except Exception as exc:
            # Typically "not enough rows to train IVF"; brute-force search remains exact.
            logger.info("Skipping record-embedding vector index (%s): %s", space.index_type, exc)

    # How much further a vector search looks when the vectors it found belong to too few
    # records: an embedding belongs to a medium, and a record may hold several — nuScenes has
    # six cameras — so k vectors can cover far fewer than k records.
    _SEARCH_WIDENING_FACTOR = 4

    # Through a vector index, a search reads this many times the candidates it was asked for
    # and ranks them on their full vectors: quantised, an index ranks them only roughly.
    # Measured on 50,000 to 300,000 vectors of 512 dimensions (pixano-worker's
    # scripts/measure_vector_index.py, backend-processing §12): it brings back 99.9% to 100% of
    # the exact nearest records through IVF_SQ, and 97% to 100% through IVF_PQ, where an IVF_PQ
    # index read without it found 32% to 90%, for 4 to 7 ms more. Without an index the search is
    # exact already, and LanceDB ignores it.
    _SEARCH_REFINE_FACTOR = 10

    def search_records(
        self,
        query_vector: Sequence[float] | Sequence[Sequence[float]],
        k: int,
        record_id_filter: list[str] | None = None,
        model: str | None = None,
    ) -> tuple[list[LanceModel], list[float]]:
        """Rank records by similarity of their media's embeddings to a query, in one model's space.

        An embedding belongs to a medium, not to a record: a record's distance is that of its
        closest medium. The query is one vector — a text, an image — or several: the media of
        a record searched "similar to", each searched and the best match kept per record.

        Args:
            query_vector: The query embedding, or a list of them, computed by that model (same
                space and dimension as the stored vectors).
            k: Maximum number of records to return.
            record_id_filter: Optional record-id allowlist applied as a vector-search prefilter.
            model: The model — its space's id or its name —; the default one when None.

        Returns:
            A tuple of ``(records, distances)`` ordered by increasing distance.

        Raises:
            DatasetAccessError: The dataset has no embeddings of that model, or ``k`` is not positive.
        """
        space = self._embedding_space(model)
        if not isinstance(k, int) or k < 1:
            raise DatasetAccessError("k must be a strictly positive integer.")
        if record_id_filter is not None and len(record_id_filter) == 0:
            return [], []

        vectors = cast(list[Sequence[float]], list(query_vector) if _is_nested(query_vector) else [query_vector])
        table = self.open_table(space.table)
        metric = space.metric
        stored = table.count_rows()
        best: dict[str, float] = {}
        for vector in vectors:
            for record_id, distance in self._closest_records(table, vector, metric, k, stored, record_id_filter):
                best[record_id] = min(distance, best.get(record_id, distance))
        if not best:
            return [], []
        ranked = sorted(best.items(), key=lambda item: item[1])[:k]
        record_ids = [record_id for record_id, _ in ranked]

        records = self.get_data(SchemaGroup.RECORD.value, ids=record_ids)
        records = sorted(records, key=lambda record: record_ids.index(record.id))
        return records, [best[record.id] for record in records]

    def _closest_records(
        self,
        table: LanceTable,
        vector: Sequence[float],
        metric: str,
        k: int,
        stored: int,
        record_id_filter: list[str] | None,
    ) -> list[tuple[str, float]]:
        """The closest record of each medium near ``vector``, widening until ``k`` records are found."""
        limit = k
        while True:
            query = (
                table.search(list(vector))
                .metric(metric)
                .refine_factor(self._SEARCH_REFINE_FACTOR)
                # `_distance` named: LanceDB adds it on its own today, and warns it will stop.
                .select(["record_id", "_distance"])
            )
            if record_id_filter is not None:
                query = query.where(f"record_id IN {to_sql_list(record_id_filter)}", prefilter=True)
            results: pl.DataFrame = query.limit(limit).to_polars()
            if results.is_empty():
                return []
            ranked = results.group_by("record_id").agg(pl.min("_distance"))
            # Fewer vectors than asked for means there are no more to find — a prefilter that
            # keeps fewer than k records would otherwise widen up to the whole table.
            if ranked.height >= k or limit >= stored or results.height < limit:
                return list(zip(ranked["record_id"].to_list(), ranked["_distance"].to_list(), strict=True))
            limit *= self._SEARCH_WIDENING_FACTOR

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

    @dataset_write
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
                self.features_values.to_json(self._features_values_file)
                return

        # Otherwise, add a new constraint
        constraint_dict[table].append(Constraint(name=field_name, restricted=restricted, values=values))

        # Save json
        self.features_values.to_json(self._features_values_file)
