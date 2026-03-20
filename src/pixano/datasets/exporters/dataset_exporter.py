# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import logging
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

import duckdb
import pyarrow as pa
import tqdm
from lancedb.pydantic import LanceModel

from pixano.schemas import SchemaGroup

from ..dataset import Dataset
from ..dataset_info import DatasetInfo
from ..queries import TableQueryBuilder


logger = logging.getLogger(__name__)


class DatasetExporter(ABC):
    """Abstract base class for dataset exporters.

    To export a dataset, you need to implement this class and provide
    an implementation for the abstract methods.

    Attributes:
        dataset: The dataset to be exported.
        export_dir: The directory where the exported files will be saved.
    """

    def __init__(self, dataset: Dataset, export_dir: str | Path, overwrite: bool = False):
        """Initialize a new instance of the DatasetExporter class.

        Args:
            dataset: The dataset to be exported.
            export_dir: The directory where the exported files will be saved.
            overwrite: Whether to overwrite existing directory.
        """
        self.dataset = dataset
        self.export_dir = Path(export_dir)
        self._overwrite = overwrite

    @abstractmethod
    def initialize_export_data(self, info: DatasetInfo) -> Any:
        """Initialize the data structure to be exported.

        Args:
            info: The dataset information.

        Returns:
            The data structure to be exported.
        """
        ...

    @abstractmethod
    def export_record(self, export_data: Any, record_data: dict[str, LanceModel | list[LanceModel] | None]) -> Any:
        """Store a record's data in the data structure to be exported.

        Args:
            export_data: The data structure to be exported.
            record_data: Dict of table_name → row(s) for this record.

        Returns: The data structure to be exported.
        """
        ...

    @abstractmethod
    def save_data(self, export_data: Any, split: str, file_name: str, file_num: int) -> None:
        """Save data to the specified directory.

        Args:
            export_data: The data structure to be exported.
            split: The split of the dataset item being saved.
            file_name: The name of the file to save the data in.
            file_num: The number of the file to save the data in.
        """
        ...

    def _get_record_data(self, record_id: str) -> dict[str, LanceModel | list[LanceModel] | None]:
        """Fetch all related rows for a single record across all tables.

        Args:
            record_id: The record ID.

        Returns:
            Dict of table_name → row(s).
        """
        data: dict[str, LanceModel | list[LanceModel] | None] = {}
        for table_name, schema_cls in self.dataset.info.tables.items():
            if table_name == SchemaGroup.RECORD.value:
                # Record table — single row
                rows = self.dataset.get_data(table_name, where=f"id = '{record_id}'")
                data[table_name] = rows[0] if rows else None
            else:
                # RecordComponent tables — filter by record_id
                rows = self.dataset.get_data(table_name, where=f"record_id = '{record_id}'")
                data[table_name] = rows if rows else None
        return data

    def export(
        self, file_name: str = "pixano_export", items_per_file: int | None = None, batch_size: int | None = None
    ) -> None:
        """Export the dataset to the specified directory.

        Args:
            file_name: The name of the exported dataset.
            items_per_file: The number of records to export per file. If not specified, all records will be exported
                in a single file.
            batch_size: The size of each batch when exporting data. If not specified, all data will be exported at
                once.
        """
        self.export_dir.mkdir(exist_ok=self._overwrite)

        if items_per_file is not None and (not isinstance(items_per_file, int) or items_per_file <= 0):
            raise ValueError("Items per file must be a positive integer")
        if batch_size is not None and (not isinstance(batch_size, int) or batch_size <= 0):
            raise ValueError("Batch size must be a positive integer")

        info = self.dataset.info

        record_table = self.dataset.open_table(SchemaGroup.RECORD.value)
        record_table_arrow = record_table.to_arrow()  # noqa: F841
        SQL_QUERY = "SELECT split, COUNT(*) FROM record_table_arrow GROUP BY split"
        arrow_results: pa.Table = duckdb.query(SQL_QUERY).to_arrow_table()
        splits: dict[str, list[Any]] = arrow_results.to_pydict()

        logger.info(f"Exporting dataset {self.dataset.info.name} to {self.export_dir}.")
        for num_split_records, split in zip(splits["count_star()"], splits["split"]):
            if items_per_file is None:
                split_items_per_file = num_split_records
            else:
                split_items_per_file = items_per_file
            if batch_size is None:
                batch_size = num_split_records

            export_data = self.initialize_export_data(info)

            file_num = 0  # Number of files exported so far
            cur_records_exported = 0  # Number of records exported so far
            logger.info(
                f"Exporting split {split} of dataset {self.dataset.info.name}: number of records {num_split_records}"
            )

            for _ in tqdm.tqdm(
                range(0, num_split_records, batch_size),
                desc=f"Exporting data split {split} of dataset {self.dataset.info.name}",
            ):
                record_ids = list(
                    TableQueryBuilder(record_table)
                    .select("id")
                    .where(f"split='{split}'")
                    .limit(batch_size)
                    .offset(cur_records_exported)
                    .to_polars()["id"]
                )
                for record_id in record_ids:
                    cur_records_exported += 1
                    record_data = self._get_record_data(record_id)
                    export_data = self.export_record(export_data, record_data)

                    if (
                        cur_records_exported == num_split_records or cur_records_exported % split_items_per_file == 0
                    ):  # Export every n records
                        self.save_data(export_data, split, file_name, file_num)

                        file_num += 1
                        if cur_records_exported != num_split_records:
                            export_data = self.initialize_export_data(info)

            logger.info(
                f"Completed export split {split} of dataset {self.dataset.info.name} in {file_num} file"
                f"{'s' if file_num > 1 else ''}."
            )
