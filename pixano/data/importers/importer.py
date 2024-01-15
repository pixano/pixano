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

from pixano.data.dataset import Dataset, DatasetCategory, DatasetInfo, DatasetTable
from pixano.data.fields import Fields
from pixano.utils import estimate_size


class Importer(ABC):
    """Dataset Importer class

    Attributes:
        info (DatasetInfo): Dataset information
        input_dirs (dict[str, Path]): Dataset input directories
    """

    info: DatasetInfo
    input_dirs: dict[str, Path]

    def __init__(
        self,
        name: str,
        description: str,
        tables: dict[str, list[DatasetTable]],
        splits: list[str],
        categories: list[DatasetCategory] = None,
    ):
        """Initialize Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            tables (dict[str, list[DatasetTable]]): Dataset tables
            splits (list[str]): Dataset splits
            categories (list[DatasetCategory], optional): Dataset categories
        """

        # Check input directories
        for source_path in self.input_dirs.values():
            if not source_path.exists():
                raise FileNotFoundError(f"{source_path} does not exist.")
            if not any(source_path.iterdir()):
                raise FileNotFoundError(f"{source_path} is empty.")

        # Create DatasetInfo
        self.info = DatasetInfo(
            id=shortuuid.uuid(),
            name=name,
            description=description,
            estimated_size="N/A",
            num_elements=0,
            splits=splits,
            tables=tables,
            categories=categories,
        )

    def create_tables(
        self, media_fields: dict[str, str] = None, object_fields: dict[str, str] = None
    ):
        """Create dataset tables

        Args:
            media_fields (dict[str, str], optional): Media fields. Defaults to None.
            object_fields (dict[str, str], optional): Object fields. Defaults to None.

        Returns:
            dict[str, list[DatasetTable]]: Tables
        """

        if media_fields is None:
            media_fields = {"image": "image"}

        tables: dict[str, list[DatasetTable]] = {
            "main": [
                DatasetTable(
                    name="db",
                    fields={
                        "id": "str",
                        "views": "[str]",
                        "split": "str",
                    },
                )
            ],
            "media": [],
        }

        # Add media fields
        for field_name, field_type in media_fields.items():
            table_exists = False
            # If table for given field type exists
            for media_table in tables["media"]:
                if field_type == media_table.name and not table_exists:
                    media_table.fields[field_name] = field_type
                    table_exists = True
            # Else, create that table
            if not table_exists:
                tables["media"].append(
                    DatasetTable(
                        name=field_type,
                        fields={
                            "id": "str",
                            field_name: field_type,
                        },
                    )
                )

        # Add object fields
        if object_fields is not None:
            tables["objects"] = [
                DatasetTable(
                    name="objects",
                    fields={"id": "str", "item_id": "str", "view_id": "str"}
                    | object_fields,
                    source="Ground Truth",
                )
            ]

        return tables

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

    def copy_or_move_files(
        self,
        import_dir: Path,
        ds_tables: dict[str, dict[str, lancedb.db.LanceTable]],
        copy: bool,
    ):
        """Copy or move dataset files

        Args:
            import_dir (Path): Import directory
            ds_tables (dict[str, dict[str, lancedb.db.LanceTable]]): Dataset tables
            copy (bool): True to copy files, False to move them
        """

        if copy:
            for table in tqdm(
                ds_tables["media"].values(), desc="Copying media directories"
            ):
                for field in table.schema:
                    if field.name in self.input_dirs:
                        field_dir = import_dir / "media" / field.name
                        field_dir.mkdir(parents=True, exist_ok=True)
                        if self.input_dirs[field.name] != field_dir:
                            shutil.copytree(
                                self.input_dirs[field.name],
                                field_dir,
                                dirs_exist_ok=True,
                            )
        else:
            for table in tqdm(
                ds_tables["media"].values(), desc="Moving media directories"
            ):
                for field in table.schema:
                    if field.name in self.input_dirs:
                        field_dir = import_dir / "media" / field.name
                        if self.input_dirs[field.name] != field_dir:
                            self.input_dirs[field.name].rename(field_dir)

    @abstractmethod
    def import_rows(self) -> Iterator:
        """Process dataset rows for import

        Yields:
            Iterator: Processed rows
        """

    def import_dataset(
        self,
        import_dir: Path,
        copy: bool = True,
    ) -> Dataset:
        """Import dataset to Pixano format

        Args:
            import_dir (Path): Import directory
            copy (bool, optional): True to copy files to the import directory, False to move them. Defaults to True.

        Returns:
            Dataset: Imported dataset
        """

        # Create dataset
        dataset = Dataset.create(import_dir, self.info)

        # Load dataset tables
        ds_tables = dataset.open_tables()

        # Initalize batches
        ds_batches: dict[str, dict[str, list]] = defaultdict(dict)
        for group_name, table_group in self.info.tables.items():
            for table in table_group:
                ds_batches[group_name][table.name] = []

        # Add rows to tables
        save_batch_size = 1024
        for rows in tqdm(self.import_rows(), desc="Importing dataset"):
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
        ds_tables = dataset.open_tables()

        # Raise error if generated dataset is empty
        if len(ds_tables["main"]["db"]) == 0:
            raise FileNotFoundError(
                "Generated dataset is empty. Please make sure that the paths to your media files are correct, and that they each contain subfolders for your splits."
            )

        # Create DatasetInfo
        dataset.info.num_elements = len(ds_tables["main"]["db"])
        dataset.info.estimated_size = estimate_size(import_dir)
        dataset.save_info()

        # Create thumbnail
        self.create_preview(import_dir, ds_tables)

        # Copy or move media directories
        self.copy_or_move_files(import_dir, ds_tables, copy)

        return Dataset(import_dir)
