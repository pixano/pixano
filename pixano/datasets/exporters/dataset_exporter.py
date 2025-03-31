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

from pixano.features import (
    SchemaGroup,
    Source,
)

from ..dataset import Dataset
from ..dataset_info import DatasetInfo
from ..dataset_schema import DatasetItem
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
    def initialize_export_data(self, info: DatasetInfo, sources: list[Source]) -> Any:
        """Initialize the data structure to be exported.

        Args:
            info: The dataset information.
            sources: The list of sources.

        Returns:
            The data structure to be exported.
        """
        ...

    @abstractmethod
    def export_dataset_item(self, export_data: Any, dataset_item: DatasetItem) -> Any:
        """Store the dataset item in the data structure to be exported.

        Args:
            export_data: The data structure to be exported.
            dataset_item: The dataset item to be exported.

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

    def export(
        self, file_name: str = "pixano_export", items_per_file: int | None = None, batch_size: int | None = None
    ) -> None:
        """Export the dataset to the specified directory.

        Args:
            file_name: The name of the exported dataset.
            items_per_file: The number of items to export per file. If not specified, all items will be exported in a
                single file.
            batch_size: The size of each batch when exporting data. If not specified, all data will be exported at
                once.
        """
        self.export_dir.mkdir(exist_ok=self._overwrite)

        if items_per_file is not None and (not isinstance(items_per_file, int) or items_per_file <= 0):
            raise ValueError("Items per file must be a positive integer")
        if batch_size is not None and (not isinstance(batch_size, int) or batch_size <= 0):
            raise ValueError("Batch size must be a positive integer")

        info = self.dataset.info
        sources = self.dataset.get_data(SchemaGroup.SOURCE.value)

        item_table = self.dataset.open_table(SchemaGroup.ITEM.value)
        item_table_lance = item_table.to_lance()  # noqa: F841
        SQL_QUERY = "SELECT split, COUNT(*) FROM item_table_lance GROUP BY split"
        arrow_results: pa.Table = duckdb.query(SQL_QUERY).to_arrow_table()
        splits: dict[str, list[Any]] = arrow_results.to_pydict()

        logger.info(f"Exporting dataset {self.dataset.info.name} to {self.export_dir}.")
        for num_split_items, split in zip(splits["count_star()"], splits["split"]):
            if items_per_file is None:
                split_items_per_file = num_split_items
            else:
                split_items_per_file = items_per_file
            if batch_size is None:
                batch_size = num_split_items

            export_data = self.initialize_export_data(info, sources)

            file_num = 0  # Number of files exported so far
            cur_items_exported = 0  # Number of items exported so far
            logger.info(
                f"Exporting split {split} of dataset {self.dataset.info.name}: number of items {num_split_items}"
            )

            for _ in tqdm.tqdm(
                range(0, num_split_items, batch_size),
                desc=f"Exporting data split {split} of dataset {self.dataset.info.name}",
            ):
                item_ids = list(
                    TableQueryBuilder(item_table)
                    .select("id")
                    .where(f"split='{split}'")
                    .limit(batch_size)
                    .offset(cur_items_exported)
                    .to_polars()["id"]
                )
                dataset_items: list[DatasetItem] = self.dataset.get_dataset_items(ids=item_ids)
                for dataset_item in dataset_items:
                    cur_items_exported += 1

                    export_data = self.export_dataset_item(export_data, dataset_item)

                    if (
                        cur_items_exported == num_split_items or cur_items_exported % split_items_per_file == 0
                    ):  # Export every n items
                        self.save_data(export_data, split, file_name, file_num)

                        file_num += 1
                        if cur_items_exported != num_split_items:
                            export_data = self.initialize_export_data(info, sources)

            logger.info(
                f"Completed export split {split} of dataset {self.dataset.info.name} in {file_num} file"
                f"{'s' if file_num > 1 else ''}."
            )
