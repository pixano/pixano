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
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Generator
from io import BytesIO
from itertools import islice
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
import shortuuid
from PIL import Image
from tqdm.auto import tqdm

from pixano.core import DatasetInfo, arrow_types


def batch_dict(iterable: iter, batch_size: int) -> Generator[dict]:
    """Batch dicts

    Args:
        iterable (iter): Iterable
        batch_size (int): Batch size

    Yields:
        Generator[list]: Iterable in batches
    """

    it = iter(iterable)
    while batch := list(islice(it, batch_size)):
        batch_dict = defaultdict(list)
        for d in batch:
            for k, v in d.items():
                batch_dict[k].append(v)
        yield batch_dict


class DataLoader(ABC):
    """Abstract Data Loader class

    Attributes:
        name (str): Dataset name
        description (str): Dataset description
        source_dirs (dict[str, Path]): Dataset source directories
        target_dir (Path): Dataset target directory
        schema (pa.schema): Dataset schema
    """

    def __init__(
        self,
        name: str,
        description: str,
        source_dirs: dict[str, Path],
        target_dir: Path,
        add_fields: list[pa.field],
    ):
        """Initialize Data Loader

        Args:
            name (str): Dataset name
            description (str): Dataset description
            source_dirs (dict[str, Path]): Dataset source directories
            target_dir (Path): Dataset target directory
            add_fields (list[pa.field]): Dataset additional fields
        """

        # Dataset info
        self.info = DatasetInfo(
            id=shortuuid.uuid(),
            name=name,
            description=description,
            num_elements=0,
        )

        # Dataset directories
        self.source_dirs = source_dirs
        self.target_dir = target_dir

        # Dataset schema
        fields = [
            pa.field("split", pa.string()),
            pa.field("id", pa.string()),
            pa.field("objects", pa.list_(arrow_types.ObjectAnnotationType())),
        ]
        fields.extend(add_fields)
        self.schema = pa.schema(fields)

    def create_json(self):
        """Create dataset spec.json"""

        # Read dataset
        dataset = ds.dataset(self.target_dir / "db")

        # Check number of rows in the created dataset
        self.info.num_elements = dataset.count_rows()

        # Create spec.json
        with open(self.target_dir / "spec.json", "w") as f:
            json.dump(vars(self.info), f)

    def create_preview(self):
        """Create dataset preview image"""

        # Read dataset
        dataset = ds.dataset(self.target_dir / "db")

        # Get list of image fields
        image_fields = []
        for field in self.schema:
            if arrow_types.is_image_type(field.type):
                image_fields.append(field.name)

        if image_fields:
            tile_w = 64
            tile_h = 64
            preview = Image.new("RGB", (3 * tile_w, 2 * tile_h))
            for i in range(6):
                field = image_fields[i % len(image_fields)]
                row_number = random.randrange(dataset.count_rows())
                row = dataset.take([row_number]).to_pylist()[0]
                image = Image.open(BytesIO(row[field]._preview_bytes))
                preview.paste(image, ((i % 3) * tile_w, (int(i / 3) % 2) * tile_h))
            preview.save(self.target_dir / "preview.png")

    @abstractmethod
    def process_rows(self, split: str) -> Generator[dict]:
        """Process dataset row for a given split

        Args:
            split (str): Dataset split

        Yields:
            Generator[dict]: Rows processed to be stored in a parquet
        """

        pass

    def process_dataset(
        self,
        splits: list[str],
        batch_size: int = 2048,
    ):
        """Process dataset to parquet format

        Args:
            splits (list[str]): Dataset split
            batch_size (int, optional): Number of rows per file. Defaults to 2048.
        """

        # Iterate on splits
        for split in splits:
            batches = batch_dict(self.process_rows(split), batch_size)
            # Iterate on batches
            for i, batch in tqdm(enumerate(batches), desc=split, position=0):
                # Convert batch fields to PyArrow format
                arrays = []
                for field in self.schema:
                    arrays.append(
                        arrow_types.convert_field(
                            field_name=field.name,
                            field_type=field.type,
                            field_data=batch[field.name],
                        )
                    )
                # Save batch to parquet file
                ds.write_dataset(
                    data=pa.Table.from_arrays(arrays, schema=self.schema),
                    base_dir=self.target_dir / "db",
                    basename_template=f"part-{{i}}-{i}.parquet",
                    format="parquet",
                    existing_data_behavior="overwrite_or_ignore",
                    partitioning=ds.partitioning(
                        pa.schema([("split", pa.string())]), flavor="hive"
                    ),
                )

        # Create spec.json and preview.png
        self.create_json()
        self.create_preview()

        # Move image folders
        for field in self.schema:
            if arrow_types.is_image_type(field.type):
                field_dir = self.target_dir / "media" / field.name
                field_dir.mkdir(parents=True, exist_ok=True)
                self.source_dirs[field.name].rename(field_dir)
