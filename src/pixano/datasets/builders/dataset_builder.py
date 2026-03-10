# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import logging
import shutil
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterator, Literal

import shortuuid
import tqdm
from lancedb.pydantic import LanceModel

from pixano.datasets import Dataset, DatasetInfo
from pixano.schemas import Record, SchemaGroup


logger = logging.getLogger(__name__)


class DatasetBuilder(ABC):
    """Abstract base class for dataset builders.

    To build a dataset, inherit from this class, implement the ``generate_data``
    method and launch the ``build`` method.

    Attributes:
        target_dir: The target directory for the dataset.
        previews_path: The path to the previews directory.
        info: Dataset information (including table→schema mapping).
        schemas: The schemas of the dataset tables (alias for info.tables).
    """

    def __init__(
        self,
        target_dir: Path | str,
        info: DatasetInfo,
    ):
        """Initialize a DatasetBuilder instance.

        Args:
            target_dir: The target directory for the dataset.
            info: Dataset information including table→schema mapping.
        """
        self.target_dir: Path = Path(target_dir)
        self.previews_path: Path = self.target_dir / Dataset._PREVIEWS_PATH

        self.info: DatasetInfo = info
        self.schemas: dict[str, type[LanceModel]] = self.info.tables
        self._active_dataset: Dataset | None = None

    @property
    def record_schema(self) -> type[Record]:
        """The record schema for the dataset."""
        return self.info.tables[SchemaGroup.RECORD.value]

    @property
    def record_table_name(self) -> str:
        """The record table name for the dataset."""
        return SchemaGroup.RECORD.value

    def build(
        self,
        mode: Literal["add", "create", "overwrite"] = "create",
        flush_every_n_samples: int = 1024,
        compact_every_n_transactions: int | None = None,
        check_integrity: Literal["raise", "warn", "none"] = "raise",
    ) -> Dataset:
        """Build the dataset.

        For ``"create"`` and ``"overwrite"`` modes the dataset is initialised
        via :meth:`Dataset.create`. Data is then inserted in batches via
        :meth:`Dataset.add_records`.

        Args:
            mode: The mode for creating the tables ("create", "overwrite" or "add").
            flush_every_n_samples: Samples accumulated before flushing. Defaults to 1024.
            compact_every_n_transactions: Deprecated and ignored. Dataset storage
                maintenance is delegated to :class:`Dataset`.
            check_integrity: Integrity check mode ("raise", "warn" or "none").

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

        dataset = self._prepare_dataset(mode)
        buffers = self._initialize_buffers()

        logger.info("Building dataset %s", self.info.name)
        self._active_dataset = dataset
        try:
            for items in tqdm.tqdm(self.generate_data(), desc=f"Generate data for dataset {self.info.name}"):
                self._accumulate_records(buffers, items)
                if any(len(rows) >= flush_every_n_samples for rows in buffers.values()):
                    self._flush_accumulated(buffers, dataset, check_integrity)

            self._flush_accumulated(buffers, dataset, check_integrity)
        finally:
            self._active_dataset = None

        logger.info("Dataset %s built in %s with id %s", self.info.name, self.target_dir, self.info.id)
        return dataset

    def _prepare_dataset(self, mode: Literal["add", "create", "overwrite"]) -> Dataset:
        """Open or create the target dataset for the requested build mode."""
        if mode == "add":
            dataset = Dataset(self.target_dir)
            if not self.info.id:
                self.info.id = dataset.info.id
            return dataset

        if mode == "overwrite" and self.target_dir.exists():
            shutil.rmtree(self.target_dir)

        if not self.info.id:
            self.info.id = shortuuid.uuid()
        return Dataset.create(self.target_dir, self.info)

    def _initialize_buffers(self) -> dict[str, list[LanceModel]]:
        """Create one in-memory buffer per known table."""
        return {table_name: [] for table_name in self.schemas.keys()}

    def _accumulate_records(
        self,
        buffers: dict[str, list[LanceModel]],
        items: dict[str, LanceModel | list[LanceModel]],
    ) -> None:
        """Normalize generated rows and append them to the in-memory buffers."""
        for table_name, item_value in items.items():
            if item_value is None or item_value == []:
                continue
            if table_name not in buffers:
                raise KeyError(f"Table {table_name} not found in tables")

            rows = item_value if isinstance(item_value, list) else [item_value]
            buffers[table_name].extend(rows)

    def _flush_accumulated(
        self,
        accumulate_data_tables: dict[str, list[LanceModel]],
        dataset: Dataset,
        check_integrity: Literal["raise", "warn", "none"],
    ) -> None:
        """Flush all non-empty accumulated buffers via ``dataset.add_records()``."""
        batch = {table_name: rows for table_name, rows in accumulate_data_tables.items() if rows}
        if not batch:
            return

        dataset.add_records(batch, check_integrity=check_integrity)

        for table_name in batch:
            accumulate_data_tables[table_name] = []

    @abstractmethod
    def generate_data(self) -> Iterator[dict[str, LanceModel | list[LanceModel]]]:
        """Generate data from the source directory.

        It should yield a dictionary with keys corresponding to the table names
        and values corresponding to the data.

        Returns:
            An iterator over the data following the dataset schemas.
        """
        raise NotImplementedError
