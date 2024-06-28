# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from abc import ABC, abstractmethod
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterator, Literal

import duckdb
import lancedb
import shortuuid
import tqdm
from lancedb.table import Table

from pixano.datasets.dataset_schema import DatasetItem, DatasetSchema
from pixano.datasets.features.schemas.base_schema import BaseSchema
from pixano.datasets.features.schemas.group import _SchemaGroup
from pixano.datasets.features.schemas.item import Item

from .. import Dataset, DatasetLibrary
from ..dataset_features_values import DatasetFeaturesValues
from ..features.schemas import image as image_schema
from ..features.schemas import sequence_frame as sequence_frame_schema
from ..utils import video as video_utils


class DatasetBuilder(ABC):
    """Abstract base class for dataset builders.

    Attributes:
        target_dir (Path): The target directory for the dataset.
        source_dir (Path): The source directory for the dataset.
        dataset_schema (DatasetSchema): The dataset schema for the dataset.
        schemas (dict[str, BaseSchema]): The schemas for the dataset tables infered from the dataset schema.
        db (lancedb.Database): The lancedb.Database instance for the dataset.
    """

    def __init__(
        self,
        source_dir: Path | str,
        target_dir: Path | str,
        schemas: type[DatasetItem],
        info: DatasetLibrary,
    ):
        """Initialize the BaseDatasetBuilder instance.

        Args:
            source_dir (Path | str): The source directory for the dataset.
            target_dir (Path | str): The target directory for the dataset.
            schemas (type[DatasetItem]): The schemas for the dataset tables.
            info (DatasetLibrary): User informations (name, description, ...)
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
        items_per_transaction: int | None = None,
        compact_every_n_transactions: int | None = None,
        mode: Literal["create", "overwrite", "add"] = "create",
    ) -> Dataset:
        """Build the dataset.

        Args:
            items_per_transaction (int | None): The number of items per transaction. If None, items are inserted at each
                iteration.
            compact_every_n_transactions (int | None): The number of transactions before compacting the dataset.
                If None, the dataset is compacted only at the end.
            mode (Literal["create", "overwrite", "add"]): The mode for creating the tables in the database.

        Returns:
            Dataset: The built dataset.
        """
        if mode == "add":
            tables = self._open_tables()
        else:
            tables = self._create_tables(mode)

        # accumulate items to insert in tables
        accumulate_tables = {table_name: [] for table_name in tables.keys()}

        for count, items in enumerate(tqdm.tqdm(self._generate_items(), desc="Import items")):
            # assert that items have keys that are in tables
            for table_name, item_value in items.items():
                assert table_name in tables, f"Table {table_name} not found in tables"

                for it in item_value if isinstance(item_value, list) else [item_value]:
                    if " " in it.id:
                        raise ValueError(f"ids should not contain spaces (table: {table_name}, " f"id:{it.id})")

                accumulate_tables[table_name].extend(item_value if isinstance(item_value, list) else [item_value])

                # make transaction every n items per table
                if len(accumulate_tables[table_name]) > 0 and (
                    items_per_transaction is None or len(accumulate_tables[table_name]) % items_per_transaction == 0
                ):
                    table = tables[table_name]
                    table.add(accumulate_tables[table_name])
                    accumulate_tables[table_name] = []

                # compact dataset every n transactions
                if compact_every_n_transactions is not None and count % compact_every_n_transactions == 0:
                    self._compact_dataset()

        # make transaction for final batch
        for table_name, table in tables.items():
            if len(accumulate_tables[table_name]) > 0:
                table.add(accumulate_tables[table_name])
        self._compact_dataset()

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

    def _compact_dataset(self) -> None:
        for table in self._open_tables().values():
            table.cleanup_old_versions(delete_unverified=True)
            table.compact_files()

    @abstractmethod
    def _generate_items(self) -> Iterator[dict[str, BaseSchema | list[BaseSchema]]]:
        """Read items from the source directory.

        Returns:
            Iterator[dict[str, Any]]: An iterator over the items following data schema.

        """
        raise NotImplementedError

    def _generate_media_previews(self, **kwargs) -> None:
        """Generate media previews for the dataset."""
        for table_name, schema in self.schemas.items():
            print(f"Will generate previews for {table_name}")
            if image_schema.is_image(schema):
                self._generate_image_previews(table_name)
            elif sequence_frame_schema.is_sequence_frame(schema):
                fps = kwargs.get("fps", 25)
                scale = kwargs.get("scale", 0.5)
                self._generate_sequence_frame_previews(table_name, fps, scale)
            else:
                continue

    def _create_tables(
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

    def _open_tables(self) -> dict[str, Table]:
        """Open tables in the database.

        Returns:
            dict[str, Table]: The tables in the database.

        """
        tables = {}
        for key in self.schemas.keys():
            tables[key] = self.db.open_table(key)

        return tables

    def _generate_image_previews(self) -> None:
        """Generate image previews for the dataset."""
        pass

    def _generate_sequence_frame_previews(self, table_name: str, fps: int, scale: float):
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
