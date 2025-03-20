# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import logging
from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path
from typing import Any, Iterator, Literal

import lancedb
import shortuuid
import tqdm
from lancedb.table import Table

from pixano.datasets import Dataset, DatasetFeaturesValues, DatasetInfo, DatasetItem, DatasetSchema
from pixano.datasets.utils.integrity import check_dataset_integrity, handle_integrity_errors
from pixano.features import BaseSchema, Item, SchemaGroup
from pixano.features.schemas.source import Source, SourceKind


logger = logging.getLogger(__name__)


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

    def build(
        self,
        mode: Literal["add", "create", "overwrite"] = "create",
        flush_every_n_samples: int | None = None,
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
                flushed in tables. The counter is per table. If None, data are inserted at each iteration.
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
        if flush_every_n_samples is not None and flush_every_n_samples <= 0:
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

        # accumulate items to insert in tables
        accumulate_data_tables: dict[str, list] = {table_name: [] for table_name in tables.keys()}
        # count transactions per table
        transactions_per_table: dict[str, int] = dict.fromkeys(tables.keys(), 0)

        logger.info(f"Building dataset {self.info.name}")
        for items in tqdm.tqdm(self.generate_data(), desc=f"Generate data for dataset {self.info.name}"):
            # assert that items have keys that are in tables
            for table_name, item_value in items.items():
                if item_value is None or item_value == []:
                    continue
                if table_name not in tables:
                    raise KeyError(f"Table {table_name} not found in tables")

                accumulate_data_tables[table_name].extend(item_value if isinstance(item_value, list) else [item_value])

                # make transaction every n iterations per table
                if len(accumulate_data_tables[table_name]) > 0 and (
                    flush_every_n_samples is None
                    or len(accumulate_data_tables[table_name]) % flush_every_n_samples == 0
                ):
                    table = tables[table_name]
                    table.add(accumulate_data_tables[table_name])
                    transactions_per_table[table_name] += 1
                    accumulate_data_tables[table_name] = []

                # compact dataset every n transactions per table
                if (
                    compact_every_n_transactions is not None
                    and transactions_per_table[table_name] % compact_every_n_transactions == 0
                    and transactions_per_table[table_name] > 0
                ):
                    self.compact_table(table_name)

        # make transaction for final batch
        for table_name, table in tables.items():
            if len(accumulate_data_tables[table_name]) > 0:
                table.add(accumulate_data_tables[table_name])
        self.compact_dataset()

        logger.info(f"Dataset {self.info.name} built in {self.target_dir} with id {self.info.id}")

        dataset = Dataset(self.target_dir)

        if check_integrity != "none":
            logger.info(f"Checking dataset {dataset.info.name} integrity...")
            handle_integrity_errors(check_dataset_integrity(dataset), raise_or_warn=check_integrity)

        logger.info(f"Dataset {dataset.info.name} built successfully.")
        return dataset

    def compact_table(self, table_name: str) -> None:
        """Compact a table by cleaning up old versions and compacting files.

        Args:
            table_name: The name of the table to compact.
        """
        table = self.db.open_table(table_name)
        table.compact_files(
            target_rows_per_fragment=1048576, max_rows_per_group=1024, materialize_deletions=False, num_threads=None
        )
        table.cleanup_old_versions(older_than=timedelta(days=0), delete_unverified=True)

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

        Returns:
            The tables in the database.
        """
        tables = {}
        for key, schema in self.schemas.items():
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
