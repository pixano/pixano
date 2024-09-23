# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from abc import ABC, abstractmethod
from datetime import timedelta
from pathlib import Path
from typing import Iterator, Literal

import lancedb
import shortuuid
import tqdm
from lancedb.table import Table

from pixano.datasets import Dataset, DatasetFeaturesValues, DatasetInfo, DatasetItem, DatasetSchema
from pixano.features import BaseSchema, Item, SchemaGroup
from pixano.features.schemas.source import Source


class DatasetBuilder(ABC):
    """Abstract base class for Dataset builders.

    To build a dataset, the easiest is to launch the `build` method which requires to inherit from this class and
    implement `generate_data`.

    Attributes:
        target_dir: The target directory for the dataset.
        previews_path: The path to the previews directory.
        info: Dataset informations (name, description, ...).
        dataset_schema: The dataset schema for the dataset.
        schemas: The schemas for the dataset tables infered from the dataset schema.
        db: The `lancedb.Database` instance for the dataset.
    """

    def __init__(
        self,
        target_dir: Path | str,
        schemas: type[DatasetItem],
        info: DatasetInfo,
    ):
        """Initialize the BaseDatasetBuilder instance.

        Args:
            target_dir: The target directory for the dataset.
            schemas: The schemas for the dataset tables.
            info: Dataset informations (name, description, ...)
                for the dataset.
        """
        self.target_dir: Path = Path(target_dir)
        self.previews_path: Path = self.target_dir / Dataset._PREVIEWS_PATH

        self.info: DatasetInfo = info
        self.dataset_schema: DatasetSchema = schemas.to_dataset_schema()
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

    def build(
        self,
        mode: Literal["add", "create", "overwrite"] = "create",
        flush_every_n_samples: int | None = None,
        compact_every_n_transactions: int | None = None,
    ) -> Dataset:
        """Build the dataset.

        It generates data from the source directory and insert them in the tables of the database.

        Args:
            mode: The mode for creating the tables in the database.
                The mode can be "create", "overwrite" or "add":
                    - "create": Create the tables in the database.
                    - "overwrite": Overwrite the tables in the database.
                    - "add": Append to the tables in the database.
            flush_every_n_samples: The number of samples accumulated from :meth:`generate_data` before
                flush in tables. If None, data are inserted at each iteration.
            compact_every_n_transactions: The number of transactions before compacting the dataset.
                If None, the dataset is compacted only at the end.


        Returns:
            The built dataset.
        """
        if mode == "add":
            tables = self.open_tables()
        else:
            tables = self.create_tables(mode)

        # accumulate items to insert in tables
        accumulate_data_tables: dict[str, list] = {table_name: [] for table_name in tables.keys()}
        # count transactions per table
        transactions_per_table: dict[str, int] = {table_name: 0 for table_name in tables.keys()}

        for items in tqdm.tqdm(self.generate_data(), desc="Generate data"):
            # assert that items have keys that are in tables
            for table_name, item_value in items.items():
                if item_value is None or item_value == []:
                    continue
                if table_name not in tables:
                    raise KeyError(f"Table {table_name} not found in tables")

                for it in item_value if isinstance(item_value, list) else [item_value]:
                    if " " in it.id:
                        raise ValueError(f"ids should not contain spaces (table: {table_name}, " f"id:{it.id})")

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

        return Dataset(self.target_dir)

    def compact_table(self, table_name: str) -> None:
        """Compact a table in the database by cleaning up old versions and compacting files.

        Args:
            table_name: The name of the table to compact.
        """
        table = self.db.open_table(table_name)
        table.compact_files(
            target_rows_per_fragment=1048576, max_rows_per_group=1024, materialize_deletions=False, num_threads=None
        )
        table.cleanup_old_versions(older_than=timedelta(days=0), delete_unverified=True)

    def compact_dataset(self) -> None:
        """Compact the dataset by calling :meth:`compact_table` for each table in the database."""
        for table_name in self.schemas.keys():
            self.compact_table(table_name)

    @abstractmethod
    def generate_data(self) -> Iterator[dict[str, BaseSchema | list[BaseSchema]]]:
        """Generate data from the source directory.

        Returns:
            An iterator over the data following data schema.
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
        """Open tables in the database.

        Returns:
            The tables in the database.
        """
        tables = {}
        for key in self.schemas.keys():
            tables[key] = self.db.open_table(key)
        tables["source"] = self.db.open_table("source")

        return tables
