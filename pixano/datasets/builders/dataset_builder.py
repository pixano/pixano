# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import logging
from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path
from types import GenericAlias
from typing import Any, Iterator, Literal

import lancedb
import pyarrow as pa
import shortuuid
import tqdm
from lancedb.table import Table

from pixano.datasets import Dataset, DatasetFeaturesValues, DatasetInfo, DatasetItem, DatasetSchema
from pixano.datasets.dataset_schema import _view_instance_to_columns
from pixano.datasets.utils.integrity import validate_batch
from pixano.features import BaseSchema, Item, SchemaGroup
from pixano.features.schemas.source import Source, SourceKind
from pixano.features.schemas.views import View


logger = logging.getLogger(__name__)

_FLUSH_ORDER = [
    SchemaGroup.SOURCE,
    SchemaGroup.ITEM,
    SchemaGroup.VIEW,
    SchemaGroup.ENTITY,
    SchemaGroup.ENTITY_DYNAMIC_STATE,
    SchemaGroup.ANNOTATION,
    SchemaGroup.EMBEDDING,
]


class DatasetBuilder(ABC):
    """Abstract base class for dataset builders.

    To build a dataset, inherit from this class, implement the `generate_data` method and launch the `build` method.

    Attributes:
        target_dir: The target directory for the dataset.
        previews_path: The path to the previews directory.
        info: Dataset information (name, description, ...).
        dataset_schema: The schema of the dataset.
        schemas: The schemas of the dataset tables.
        db: The connection to the `LanceDB` database of the dataset.
    """

    def __init__(
        self,
        target_dir: Path | str,
        dataset_item: type[DatasetItem],
        info: DatasetInfo,
    ):
        """Initialize a DatasetBuilder instance.

        Args:
            target_dir: The target directory for the dataset.
            dataset_item: The dataset item schema.
            info: Dataset information (name, description, ...).
        """
        self.target_dir: Path = Path(target_dir)
        self.previews_path: Path = self.target_dir / Dataset._PREVIEWS_PATH

        self.info: DatasetInfo = info
        self._dataset_item_cls: type[DatasetItem] = dataset_item
        self.dataset_schema: DatasetSchema = dataset_item.to_dataset_schema()
        self.schemas: dict[str, type[BaseSchema]] = self.dataset_schema.schemas

        self.db: lancedb.DBConnection = lancedb.connect(self.target_dir / Dataset._DB_PATH)

    @property
    def item_schema(self) -> type[Item]:
        """The item schema for the dataset."""
        return self.dataset_schema.schemas[SchemaGroup.ITEM.value]

    @property
    def item_schema_name(self) -> str:
        """The item schema name for the dataset."""
        return SchemaGroup.ITEM.value

    @property
    def all_schemas(self) -> dict[str, type]:
        """Returns schemas dict including both table schemas and view field types.

        This is useful for generate_data() implementations that need the original View types
        (e.g., SequenceFrameCategory) accessible by their field names (e.g., "video").
        """
        result = dict(self.schemas)
        for field_name, field in self._dataset_item_cls.model_fields.items():
            if field_name in self.dataset_schema.view_columns:
                if isinstance(field.annotation, GenericAlias):
                    result[field_name] = field.annotation.__args__[0]
                else:
                    result[field_name] = field.annotation
        return result

    def add_source(
        self,
        name: str,
        kind: str | SourceKind,
        metadata: str | dict[str, Any] = {},
        id: str = "",
    ) -> str:
        """Add a source to the dataset.

        Args:
            name: Name of the source.
            kind: Kind of source.
            metadata: Metadata of the source. If a dict is provided, it is converted to a JSON string.
            id: The id of the source. If not provided, a random id is generated.

        Returns:
            The id of the source.
        """
        if id == "":
            id = shortuuid.uuid()
        if isinstance(kind, str):
            kind = SourceKind(kind)
        self.db.open_table("source").add([Source(id=id, name=name, kind=kind.value, metadata=metadata)])
        return id

    def add_ground_truth_source(self, metadata: str | dict[str, Any] = {}) -> str:
        """Add a ground truth source to the dataset.

        Args:
            metadata: Metadata of the ground truth source.

        Returns:
            The id of the ground truth source.
        """
        return self.add_source(
            id=SourceKind.GROUND_TRUTH.value, name="Ground Truth", kind=SourceKind.GROUND_TRUTH, metadata=metadata
        )

    def _table_flush_order(self, table_names: list[str]) -> list[str]:
        """Return table names sorted by FK dependency (parents first)."""
        group_index = {g: i for i, g in enumerate(_FLUSH_ORDER)}

        def _sort_key(name: str) -> int:
            for group, tables in self.dataset_schema.groups.items():
                if name in tables:
                    return group_index.get(group, len(_FLUSH_ORDER))
            # "source" table is not in dataset_schema.groups but is SchemaGroup.SOURCE
            if name == SchemaGroup.SOURCE.value:
                return group_index[SchemaGroup.SOURCE]
            return len(_FLUSH_ORDER)

        return sorted(table_names, key=_sort_key)

    def _sort_temporal_batch(self, table_name: str, batch: list) -> list:
        """Sort a view-table batch by (timestamp, view_name) for storage colocality.

        If the table's schema has a ``timestamp`` field, sort so that all camera views
        at the same timestamp are stored adjacently. Otherwise return unchanged.
        """
        schema_type = self.dataset_schema.schemas.get(table_name)
        if schema_type is None or "timestamp" not in schema_type.model_fields:
            return batch
        return sorted(batch, key=lambda s: (getattr(s, "timestamp", 0), getattr(s, "view_name", "")))

    def _flush_table(
        self,
        table_name: str,
        batch: list,
        table: Table,
        known_ids: dict[str, set[str]],
        dataset: Dataset,
        check_integrity: Literal["raise", "warn", "none"],
        pending_ids: dict[str, set[str]] | None = None,
    ) -> None:
        """Validate a batch and insert it into the table.

        1. Sort temporal data for colocality.
        2. Validate before inserting (if check_integrity != "none").
        3. Bulk insert.
        """
        batch = self._sort_temporal_batch(table_name, batch)
        if check_integrity != "none":
            validate_batch(
                table_name, batch, known_ids, dataset,
                raise_or_warn=check_integrity, pending_ids=pending_ids,
            )
        table.add(batch)
        # Update known_ids AFTER successful validation and insertion
        for row in batch:
            if row.id:
                known_ids[table_name].add(row.id)

    def _flush_tables(
        self,
        accumulate_data_tables: dict[str, list],
        tables: dict[str, Table],
        known_ids: dict[str, set[str]],
        dataset: Dataset,
        check_integrity: Literal["raise", "warn", "none"],
        flush_order: list[str],
    ) -> list[str]:
        """Flush all non-empty accumulated buffers in dependency order.

        Pre-computes pending IDs so FK validation can see sibling tables
        that will be inserted in the same cycle.

        Returns:
            Names of tables that were flushed.
        """
        pending_ids: dict[str, set[str]] | None = None
        if check_integrity != "none":
            pending_ids = {
                tname: {row.id for row in rows if row.id}
                for tname, rows in accumulate_data_tables.items()
                if rows
            }

        flushed: list[str] = []
        for table_name in flush_order:
            batch = accumulate_data_tables[table_name]
            if not batch:
                continue
            self._flush_table(
                table_name, batch, tables[table_name],
                known_ids, dataset, check_integrity, pending_ids,
            )
            accumulate_data_tables[table_name] = []
            flushed.append(table_name)
        return flushed

    def build(
        self,
        mode: Literal["add", "create", "overwrite"] = "create",
        flush_every_n_samples: int = 1024,
        compact_every_n_transactions: int | None = None,
        check_integrity: Literal["raise", "warn", "none"] = "raise",
    ) -> Dataset:
        """Build the dataset.

        It generates data from the source directory and insert them in the tables of the database.

        Args:
            mode: The mode for creating the tables in the database.
                The mode can be "create", "overwrite" or "add":
                    - "create": Create the tables in the database. If the tables already exist, an error is raised.
                    - "overwrite": Overwrite the tables in the database.
                    - "add": Append to the tables in the database.
            flush_every_n_samples: The number of samples accumulated from `generate_data` before they are
                flushed in tables. The counter is per table. Defaults to 1024.
            compact_every_n_transactions: The number of transactions before compacting each table.
                If None, the dataset is compacted only at the end.
            check_integrity: The integrity check to perform after building the dataset. It can be "raise",
                "warn" or "none":
                    - "raise": Raise an error if integrity errors are found.
                    - "warn": Print a warning if integrity errors are found.
                    - "none": Do not check integrity.

        Returns:
            The built dataset.
        """
        if mode not in ["add", "create", "overwrite"]:
            raise ValueError(f"mode should be 'add', 'create' or 'overwrite' but got {mode}")
        if check_integrity not in ["raise", "warn", "none"]:
            raise ValueError(f"check_integrity should be 'raise', 'warn' or 'none' but got {check_integrity}")
        if flush_every_n_samples <= 0:
            raise ValueError(f"flush_every_n_samples should be greater than 0 but got {flush_every_n_samples}")
        if compact_every_n_transactions is not None and compact_every_n_transactions <= 0:
            raise ValueError(
                f"compact_every_n_transactions should be greater than 0 but got {compact_every_n_transactions}"
            )

        # save info.json
        self.info.id = shortuuid.uuid() if self.info.id == "" else self.info.id
        self.info.to_json(self.target_dir / Dataset._INFO_FILE)

        # save features_values.json
        # TMP: empty now
        DatasetFeaturesValues().to_json(self.target_dir / Dataset._FEATURES_VALUES_FILE)

        # remove previous schema.json if any
        if (self.target_dir / Dataset._SCHEMA_FILE).exists():
            (self.target_dir / Dataset._SCHEMA_FILE).unlink()
        # save schema.json
        self.dataset_schema.to_json(self.target_dir / Dataset._SCHEMA_FILE)

        if mode == "add":
            tables = self.open_tables()
        else:
            tables = self.create_tables(mode)

        # Create Dataset instance early for pre-insertion validation.
        # This is safe because info.json, schema.json and the DB already exist.
        dataset = Dataset(self.target_dir)

        # accumulate items to insert in tables
        accumulate_data_tables: dict[str, list] = {table_name: [] for table_name in tables.keys()}
        # track all known IDs across flushes for in-memory validation
        known_ids: dict[str, set[str]] = {table_name: set() for table_name in tables.keys()}
        # count transactions per table
        transactions_per_table: dict[str, int] = dict.fromkeys(tables.keys(), 0)
        # pre-compute flush ordering
        flush_order = self._table_flush_order(list(tables.keys()))

        logger.info(f"Building dataset {self.info.name}")
        for items in tqdm.tqdm(self.generate_data(), desc=f"Generate data for dataset {self.info.name}"):
            # Translate view field names to media table data
            translated = self._translate_view_fields(items)

            for table_name, item_value in translated.items():
                if item_value is None or item_value == []:
                    continue
                if table_name not in tables:
                    raise KeyError(f"Table {table_name} not found in tables")

                rows = item_value if isinstance(item_value, list) else [item_value]
                accumulate_data_tables[table_name].extend(rows)

            # Flush ALL tables together when any buffer exceeds threshold
            if any(len(buf) >= flush_every_n_samples for buf in accumulate_data_tables.values()):
                flushed = self._flush_tables(
                    accumulate_data_tables, tables, known_ids, dataset, check_integrity, flush_order,
                )
                for tname in flushed:
                    transactions_per_table[tname] += 1
                if compact_every_n_transactions is not None:
                    for tname in flushed:
                        if (
                            transactions_per_table[tname] % compact_every_n_transactions == 0
                            and transactions_per_table[tname] > 0
                        ):
                            self.compact_table(tname)

        # Final flush
        self._flush_tables(
            accumulate_data_tables, tables, known_ids, dataset, check_integrity, flush_order,
        )
        self.compact_dataset()

        logger.info(f"Dataset {self.info.name} built in {self.target_dir} with id {self.info.id}")
        logger.info(f"Dataset {dataset.info.name} built successfully.")
        return dataset

    def compact_table(self, table_name: str) -> None:
        """Compact a table by cleaning up old versions and compacting files.

        Args:
            table_name: The name of the table to compact.
        """
        table = self.db.open_table(table_name)
        table.optimize(cleanup_older_than=timedelta(days=0), delete_unverified=True)

    def compact_dataset(self) -> None:
        """Compact the dataset by calling `compact_table` for each table in the database."""
        for table_name in self.schemas.keys():
            self.compact_table(table_name)

    @abstractmethod
    def generate_data(self) -> Iterator[dict[str, BaseSchema | list[BaseSchema]]]:
        """Generate data from the source directory.

        It should yield a dictionary with keys corresponding to the table names and values corresponding to the data.

        It must be implemented in the subclass.

        Returns:
            An iterator over the data following the dataset schemas.
        """
        raise NotImplementedError

    def create_tables(
        self,
        mode: Literal["create", "overwrite"] = "create",
    ) -> dict[str, Table]:
        """Create tables in the database.

        For media-type tables, blob columns are overridden to pa.large_binary().

        Returns:
            The tables in the database.
        """
        tables = {}
        for key, schema in self.schemas.items():
            # Override blob columns to large_binary for media-type tables
            arrow_schema = self._override_blob_columns(key, schema)
            if arrow_schema is not None:
                self.db.create_table(key, schema=arrow_schema, mode=mode)
            else:
                self.db.create_table(key, schema=schema, mode=mode)

            tables[key] = self.db.open_table(key)
        self.db.create_table("source", schema=Source, mode=mode)
        tables["source"] = self.db.open_table("source")

        return tables

    def open_tables(self) -> dict[str, Table]:
        """Open the tables in the database.

        Returns:
            The tables in the database.
        """
        tables = {}
        for key in self.schemas.keys():
            tables[key] = self.db.open_table(key)
        tables["source"] = self.db.open_table("source")

        return tables

    def _override_blob_columns(
        self, table_name: str, schema: type[BaseSchema]
    ) -> pa.Schema | None:
        """Override blob columns to pa.large_binary() in Arrow schema.

        Args:
            table_name: The table name.
            schema: The schema class.

        Returns:
            The modified Arrow schema, or None if no overrides needed.
        """
        if "blob" not in schema.model_fields:
            return None
        arrow_schema = schema.to_arrow_schema()
        modified = False
        for i, field in enumerate(arrow_schema):
            if field.name == "blob":
                arrow_schema = arrow_schema.set(i, pa.field(field.name, pa.large_binary()))
                modified = True
        return arrow_schema if modified else None

    def _translate_view_fields(self, items: dict[str, Any]) -> dict[str, Any]:
        """Translate view field names to media table rows.

        When generate_data() yields {"image": image_instance, ...}, this translates
        it to {"images": [Image(...)], ...} where each media row keeps `view_name`.

        Args:
            items: The raw items dict from generate_data().

        Returns:
            Translated items dict with media table names as keys.
        """
        if not self.dataset_schema.view_columns:
            return items

        translated: dict[str, Any] = {}

        for key, value in items.items():
            if key not in self.dataset_schema.view_columns:
                translated[key] = value
                continue

            vc = self.dataset_schema.view_columns[key]
            media_table = vc.media_table
            schema = self.schemas[media_table]
            values = value if isinstance(value, list) else [value]

            rows = translated.setdefault(media_table, [])
            if not isinstance(rows, list):
                rows = [rows]

            for view_instance in values:
                if view_instance is None:
                    continue
                row_dict = _view_instance_to_columns(key, view_instance)
                row = schema.model_validate(row_dict)
                rows.append(row)

            translated[media_table] = rows

        return translated
