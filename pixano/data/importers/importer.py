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

from pixano.data import Dataset, DatasetInfo, DatasetTable, Fields
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
        tables: dict[str, list[DatasetTable]],
        splits: list[str],
    ):
        """Initialize Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            tables (dict[str, list[DatasetTable]]): Dataset fields
            splits (list[str]): Dataset splits
        """

        # Dataset info
        self.info = DatasetInfo(
            id=shortuuid.uuid(),
            name=name,
            description=description,
            estimated_size="N/A",
            num_elements=0,
            splits=splits,
            tables=tables,
        )

    def create_info(
        self,
        import_dir: Path,
    ):
        """Create dataset info file

        Args:
            import_dir (Path): Import directory
        """

        # Save DatasetInfo
        with tqdm(desc="Creating dataset info file", total=1) as progress:
            self.info.save(import_dir)
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
        copy: bool = True,
    ) -> Dataset:
        """Import dataset to Pixano format

        Args:
            input_dirs (dict[str, Path]): Input directories
            import_dir (Path): Import directory
            copy (bool, optional): True to copy files to the import directory, False to move them. Defaults to True.

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
        for group_name, table_group in self.info.tables.items():
            for table in table_group:
                ds_tables[group_name][table.name] = ds.create_table(
                    table.name,
                    schema=Fields(table.fields).to_schema(),
                    mode="overwrite",
                )
                ds_batches[group_name][table.name] = []
        save_batch_size = 1024

        # Add rows to tables
        for rows in tqdm(
            self.import_rows(input_dirs),
            desc="Importing dataset",
        ):
            for group_name, table_group in self.info.tables.items():
                for table in table_group:
                    # Store rows in a batch
                    ds_batches[group_name][table.name].extend(
                        rows[group_name][table.name]
                    )
                    # If batch reaches 1024 rows, store in table
                    if len(ds_batches[group_name][table.name]) >= save_batch_size:
                        pa_batch = pa.Table.from_pylist(
                            ds_batches[group_name][table.name],
                            schema=Fields(table.fields).to_schema(),
                        )
                        lance.write_dataset(
                            pa_batch,
                            uri=ds_tables[group_name][table.name].to_lance().uri,
                            mode="append",
                        )
                        ds_batches[group_name][table.name] = []

        # Store final batches
        for group_name, table_group in self.info.tables.items():
            for table in table_group:
                if len(ds_batches[group_name][table.name]) > 0:
                    pa_batch = pa.Table.from_pylist(
                        ds_batches[group_name][table.name],
                        schema=Fields(table.fields).to_schema(),
                    )
                    lance.write_dataset(
                        pa_batch,
                        uri=ds_tables[group_name][table.name].to_lance().uri,
                        mode="append",
                    )
                    ds_batches[group_name][table.name] = []

        # Optimize and clear creation history
        for tables in ds_tables.values():
            for table in tables.values():
                table.to_lance().optimize.compact_files()
                table.to_lance().cleanup_old_versions(older_than=timedelta(0))

        # Refresh tables
        for group_name, table_group in self.info.tables.items():
            for table in table_group:
                ds_tables[group_name][table.name] = ds.open_table(table.name)

        # Raise error if generated dataset is empty
        if len(ds_tables["main"]["db"]) == 0:
            raise FileNotFoundError(
                "Generated dataset is empty. Please make sure that the paths to your media files are correct, and that they each contain subfolders for your splits."
            )

        # Copy or move media directories
        if "media" in ds_tables:
            if copy:
                for table in tqdm(
                    ds_tables["media"].values(), desc="Copying media directories"
                ):
                    for field in table.schema:
                        if field.name in input_dirs:
                            field_dir = import_dir / "media" / field.name
                            field_dir.mkdir(parents=True, exist_ok=True)
                            if input_dirs[field.name] != field_dir:
                                shutil.copytree(
                                    input_dirs[field.name],
                                    field_dir,
                                    dirs_exist_ok=True,
                                )
            else:
                for table in tqdm(
                    ds_tables["media"].values(), desc="Moving media directories"
                ):
                    for field in table.schema:
                        if field.name in input_dirs:
                            field_dir = import_dir / "media" / field.name
                            if input_dirs[field.name] != field_dir:
                                input_dirs[field.name].rename(field_dir)

        # Create DatasetInfo
        self.info.num_elements = len(ds_tables["main"]["db"])
        self.info.estimated_size = estimate_size(import_dir)
        self.create_info(import_dir)

        # Create thumbnail
        self.create_preview(import_dir, ds_tables)

        return Dataset(import_dir)
