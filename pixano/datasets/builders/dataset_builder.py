# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import timedelta
from pathlib import Path
from typing import Iterator, Literal

import duckdb
import lancedb
import shortuuid
import tqdm
from lancedb.table import Table

from pixano.datasets.dataset_schema import DatasetItem, DatasetSchema

from .. import Dataset, DatasetInfo
from ..dataset_features_values import DatasetFeaturesValues
from ..features import BaseSchema, Item, _SchemaGroup
from ..features.schemas.views import image as image_schema
from ..features.schemas.views import sequence_frame as sequence_frame_schema
from ..utils import video as video_utils


class DatasetBuilder(ABC):
    """Abstract base class for Dataset builders.

    To build a dataset, the easiest is to launch the :meth:`build` method which requires to inherit from this class and
    implement :meth:`generate_data`.

    Attributes:
        target_dir (Path): The target directory for the dataset.
        source_dir (Path): The source directory for the dataset.
        previews_path (Path): The path to the previews directory.
        info (DatasetInfo): Dataset informations (name, description, ...).
        dataset_schema (DatasetSchema): The dataset schema for the dataset.
        schemas (dict[str, BaseSchema]): The schemas for the dataset tables infered from the dataset schema.
        db (lancedb.Database): The lancedb.Database instance for the dataset.
    """

    def __init__(
        self,
        source_dir: Path | str,
        target_dir: Path | str,
        schemas: type[DatasetItem],
        info: DatasetInfo,
    ):
        """Initialize the BaseDatasetBuilder instance.

        Args:
            source_dir (Path | str): The source directory for the dataset.
            target_dir (Path | str): The target directory for the dataset.
            schemas (type[DatasetItem]): The schemas for the dataset tables.
            info (DatasetInfo): Dataset informations (name, description, ...)
                for the dataset.
        """
        self.target_dir = Path(target_dir)
        self.source_dir = Path(source_dir)
        self.previews_path = self.target_dir / Dataset.PREVIEWS_PATH

        self.info = info
        self.dataset_schema: DatasetSchema = schemas.to_dataset_schema()
        self.schemas = self.dataset_schema.schemas

        self.db = lancedb.connect(self.target_dir / Dataset.DB_PATH)

    @property
    def item_schema(self) -> type[Item]:
        """The item schema for the dataset."""
        return self.dataset_schema.schemas[_SchemaGroup.ITEM.value]

    @property
    def item_schema_name(self) -> str:
        """The item schema name for the dataset."""
        return _SchemaGroup.ITEM.value

    def build(
        self,
        mode: Literal["add", "create", "overwrite"] = "create",
        flush_every_n_samples: int | None = None,
        compact_every_n_transactions: int | None = None,
    ) -> Dataset:
        """Build the dataset.

        It generates data from the source directory and insert them in the tables of the database.

        Args:
            mode (Literal["add", "create", "overwrite"]): The mode for creating the tables in the database.
                The mode can be "create", "overwrite" or "add":
                - "create": Create the tables in the database.
                - "overwrite": Overwrite the tables in the database.
                - "add": Append to the tables in the database.
            flush_every_n_samples (int | None): The number of samples accumulated from :meth:`generate_data` before
                flush in tables. If None, data are inserted at each iteration.
            compact_every_n_transactions (int | None): The number of transactions before compacting the dataset.
                If None, the dataset is compacted only at the end.


        Returns:
            Dataset: The built dataset.
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
                assert table_name in tables, f"Table {table_name} not found in tables"

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
        self.info.id = shortuuid.uuid()
        self.info.num_elements = tables[_SchemaGroup.ITEM.value].count_rows()
        self.info.to_json(self.target_dir / Dataset.INFO_FILE)

        # save features_values.json
        # TMP: empty now
        DatasetFeaturesValues().to_json(self.target_dir / Dataset.FEATURES_VALUES_FILE)

        # remove previous schema.json if any
        if (self.target_dir / Dataset.SCHEMA_FILE).exists():
            (self.target_dir / Dataset.SCHEMA_FILE).unlink()
        # save schema.json
        self.dataset_schema.to_json(self.target_dir / Dataset.SCHEMA_FILE)

        return Dataset(self.target_dir)

    def compact_table(self, table_name: str) -> None:
        """Compact a table in the database by cleaning up old versions and compacting files.

        Args:
            table_name (str): The name of the table to compact.
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
            Iterator[dict[str, Any]]: An iterator over the data following data schema.
        """
        raise NotImplementedError

    def generate_media_previews(self, **kwargs) -> None:
        """Generate media previews for the dataset."""
        for table_name, schema in self.schemas.items():
            print(f"Will generate previews for {table_name}")
            if image_schema.is_image(schema):
                self.generate_image_previews(table_name)
            elif sequence_frame_schema.is_sequence_frame(schema):
                fps = kwargs.get("fps", 25)
                scale = kwargs.get("scale", 0.5)
                self.generate_sequence_frame_previews(table_name, fps, scale)
            else:
                continue

    def create_tables(
        self,
        mode: Literal["create", "overwrite"] = "create",
    ) -> dict[str, Table]:
        """Create tables in the database.

        Returns:
            dict[str, Table]: The tables in the database.

        """
        tables = {}
        for key, schema in self.schemas.items():
            self.db.create_table(key, schema=schema, mode=mode)

            tables[key] = self.db.open_table(key)

        return tables

    def open_tables(self) -> dict[str, Table]:
        """Open tables in the database.

        Returns:
            dict[str, Table]: The tables in the database.

        """
        tables = {}
        for key in self.schemas.keys():
            tables[key] = self.db.open_table(key)

        return tables

    def generate_image_previews(self, table_name: str) -> None:
        """Generate image previews for the dataset."""
        pass

    def generate_sequence_frame_previews(self, table_name: str, fps: int, scale: float):
        """Generate video (sequence frames) previews for the dataset."""
        sequence_table = self.db.open_table(table_name).to_lance()  # noqa: F841

        frames = (
            duckdb.query(
                "SELECT sequence_id, LIST(url) as url, LIST(timestamp) as timestamp "
                "FROM sequence_table GROUP BY sequence_id"
            )
            .to_df()
            .to_dict(orient="records")
        )

        # store previews in the previews directory
        # {previews_path}/{table_name}/{item_id}.mp4
        previews_path = self.previews_path / table_name
        if not previews_path.exists():
            previews_path.mkdir(parents=True)

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = []
            for seq in frames:
                sorted_frames = sorted(zip(seq["url"], seq["timestamp"]), key=lambda x: x[1])
                im_urls = [self.source_dir / url for url, _ in sorted_frames]
                output_path = previews_path / f"{seq['sequence_id']}.mp4"
                futures.append(
                    executor.submit(
                        video_utils.create_video_preview,
                        output_path,
                        im_urls,
                        fps=fps,
                        scale=scale,
                    )
                )

            for _ in tqdm.tqdm(
                as_completed(futures),
                total=len(futures),
                desc=f"Generate previews for {table_name}",
            ):
                pass
