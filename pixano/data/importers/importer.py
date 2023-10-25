# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

import json
import random
import shutil
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterator
from datetime import timedelta
from io import BytesIO
from pathlib import Path

import lance
import lancedb
import pyarrow as pa
import shortuuid
from PIL import Image
from tqdm.auto import tqdm

from pixano.data import Dataset, DatasetInfo, Fields
from pixano.utils import estimate_size


class Importer(ABC):
    """Dataset Importer class

    Attributes:
        info (DatasetInfo): Dataset information
    """

    def __init__(
        self,
        name: str,
        description: str,
        tables: dict[str, list],
        splits: list[str],
    ):
        """Initialize Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            tables (dict[str, list]): Dataset fields
            splits (list[str]): Dataset splits
        """

        # Dataset info
        self.info = DatasetInfo(
            id=shortuuid.uuid(),
            name=name,
            description=description,
            estimated_size="N/A",
            num_elements=0,
            preview=None,
            splits=splits,
            tables=tables,
            categories=[],
        )

    def create_json(
        self,
        import_dir: Path,
        ds_tables: dict[str, dict[str, lancedb.db.LanceTable]],
    ):
        """Create dataset spec.json

        Args:
            import_dir (Path): Import directory
            ds_tables (dict[str, dict[str, lancedb.db.LanceTable]]): Dataset tables
        """

        self.info.num_elements = len(ds_tables["main"]["db"])
        self.info.estimated_size = estimate_size(import_dir)

        with tqdm(desc="Creating dataset info file", total=1) as progress:
            # Create spec.json
            with open(import_dir / "db.json", "w", encoding="utf-8") as f:
                json.dump(self.info.dict(), f)
            progress.update(1)

    def create_preview(
        self,
        import_dir: Path,
        ds_tables: dict[str, dict[str, lancedb.db.LanceTable]],
    ):
        """Create dataset preview image

        Args:
            import_dir (Path): Import directory
            ds_tables (dict[str, dict[str, lancedb.db.LanceTable]]): Dataset tables
        """

        # Get list of image fields
        if "media" in ds_tables:
            if "image" in ds_tables["media"]:
                image_table = ds_tables["media"]["image"]
                if len(image_table) > 0:
                    image_fields = [
                        field.name for field in image_table.schema if field.name != "id"
                    ]
                    with tqdm(desc="Creating dataset thumbnail", total=1) as progress:
                        tile_w = 64
                        tile_h = 64
                        preview = Image.new("RGB", (4 * tile_w, 2 * tile_h))
                        for i in range(8):
                            field = image_fields[i % len(image_fields)]
                            item_id = random.randrange(len(image_table))
                            item = image_table.to_lance().take([item_id]).to_pylist()[0]
                            with Image.open(BytesIO(item[field].preview_bytes)) as im:
                                preview.paste(
                                    im,
                                    ((i % 4) * tile_w, (int(i / 4) % 2) * tile_h),
                                )
                        preview.save(import_dir / "preview.png")
                        progress.update(1)

    @abstractmethod
    def import_rows(
        self,
        input_dirs: dict[str, Path],
        portable: bool = False,
    ) -> Iterator:
        """Process dataset rows for import

        Args:
            input_dirs (dict[str, Path]): Input directories

        Yields:
            Iterator: Processed rows
        """

    def import_dataset(
        self,
        input_dirs: dict[str, Path],
        import_dir: Path,
        portable: bool = False,
    ) -> Dataset:
        """Import dataset to Pixano format

        Args:
            input_dirs (dict[str, Path]): Input directories
            import_dir (Path): Import directory
            portable (bool, optional): True to copy or download files to import directory and use relative paths. Defaults to False.

        Returns:
            Dataset: Imported dataset
        """

        # Check input directories
        for source_path in input_dirs.values():
            if not source_path.exists():
                raise FileNotFoundError(f"{source_path} does not exist.")
            if not any(source_path.iterdir()):
                raise FileNotFoundError(f"{source_path} is empty.")

        # Connect to dataset
        import_dir.mkdir(parents=True, exist_ok=True)
        ds = lancedb.connect(import_dir)

        # Initialize dataset tables
        ds_tables: dict[str, dict[str, lancedb.db.LanceTable]] = defaultdict(dict)
        ds_batches: dict[str, dict[str, list]] = defaultdict(dict)

        # Create tables
        for table_group, tables in self.info.tables.items():
            for table in tables:
                ds_tables[table_group][table["name"]] = ds.create_table(
                    table["name"],
                    schema=Fields(table["fields"]).to_schema(),
                    mode="overwrite",
                )
                ds_batches[table_group][table["name"]] = []
        save_batch_size = 1024

        # Add rows to tables
        for rows in tqdm(
            self.import_rows(input_dirs, portable),
            desc="Importing dataset",
        ):
            for table_group, tables in self.info.tables.items():
                for table in tables:
                    # Store rows in a batch
                    ds_batches[table_group][table["name"]].extend(
                        rows[table_group][table["name"]]
                    )
                    # If batch reaches 1024 rows, store in table
                    if len(ds_batches[table_group][table["name"]]) >= save_batch_size:
                        pa_batch = pa.Table.from_pylist(
                            ds_batches[table_group][table["name"]],
                            schema=Fields(table["fields"]).to_schema(),
                        )
                        lance.write_dataset(
                            pa_batch,
                            uri=ds_tables[table_group][table["name"]].to_lance().uri,
                            mode="append",
                        )
                        ds_batches[table_group][table["name"]] = []

        # Store final batches
        for table_group, tables in self.info.tables.items():
            for table in tables:
                if len(ds_batches[table_group][table["name"]]) > 0:
                    pa_batch = pa.Table.from_pylist(
                        ds_batches[table_group][table["name"]],
                        schema=Fields(table["fields"]).to_schema(),
                    )
                    lance.write_dataset(
                        pa_batch,
                        uri=ds_tables[table_group][table["name"]].to_lance().uri,
                        mode="append",
                    )
                    ds_batches[table_group][table["name"]] = []

        # Optimize and clear creation history
        for tables in ds_tables.values():
            for table in tables.values():
                table.to_lance().optimize.compact_files()
                table.to_lance().cleanup_old_versions(older_than=timedelta(0))

        # Refresh tables
        for table_group, tables in self.info.tables.items():
            for table in tables:
                ds_tables[table_group][table["name"]] = ds.open_table(table["name"])

        # Copy media directories if portable
        if portable and "media" in ds_tables:
            for table in tqdm(
                ds_tables["media"].values(), desc="Copying media directories"
            ):
                for field in table.schema:
                    if field.name in input_dirs:
                        field_dir = import_dir / "media" / field.name
                        field_dir.mkdir(parents=True, exist_ok=True)
                        if input_dirs[field.name] != field_dir:
                            shutil.copytree(
                                input_dirs[field.name], field_dir, dirs_exist_ok=True
                            )

        # Create spec.json
        self.create_json(import_dir, ds_tables)

        # Create preview.png
        self.create_preview(import_dir, ds_tables)

        return Dataset(import_dir)
