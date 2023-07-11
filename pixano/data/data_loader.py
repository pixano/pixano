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

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import shortuuid
from PIL import Image
from tqdm.auto import tqdm

from pixano.analytics import compute_stats
from pixano.core import DatasetInfo, arrow_types


def _batch_dict(iterable: iter, batch_size: int) -> Generator[dict]:
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
        splits (list[str]): Dataset splits
        schema (pa.schema): Dataset schema
        partitioning (ds.partitioning): Dataset partitioning
    """

    def __init__(
        self,
        name: str,
        description: str,
        source_dirs: dict[str, Path],
        target_dir: Path,
        splits: list[str],
        add_fields: list[pa.field],
    ):
        """Initialize Data Loader

        Args:
            name (str): Dataset name
            description (str): Dataset description
            source_dirs (dict[str, Path]): Dataset source directories
            target_dir (Path): Dataset target directory
            splits (list[str]): Dataset splits
            add_fields (list[pa.field]): Dataset additional fields
        """

        # Dataset info
        self.info = DatasetInfo(
            id=shortuuid.uuid(),
            name=name,
            description=description,
            features={}
            num_elements=0
        )
        self.splits = splits

        # Dataset directories
        for source_path in source_dirs.values():
            if not Path.exists(source_path):
                raise Exception(f"{source_path} does not exist.")
            if not any(source_path.iterdir()):
                raise Exception(f"{source_path} is empty.")
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
        self.partitioning = ds.partitioning(
            pa.schema([("split", pa.string())]), flavor="hive"
        )

    def create_json(self):
        """Create dataset spec.json"""

        with tqdm(desc="Creating dataset info file", total=1) as progress:
            # Read dataset
            dataset = ds.dataset(self.target_dir / "db", partitioning=self.partitioning)

            # Check number of rows in the created dataset
            self.info.num_elements = dataset.count_rows()

            # Create spec.json
            with open(self.target_dir / "spec.json", "w") as f:
                json.dump(vars(self.info), f)
            progress.update(1)

    def create_preview(self):
        """Create dataset preview image"""

        # Read dataset
        dataset = ds.dataset(self.target_dir / "db", partitioning=self.partitioning)

        # Get list of image fields
        image_fields = []
        for field in self.schema:
            if arrow_types.is_image_type(field.type):
                image_fields.append(field.name)

        if image_fields:
            with tqdm(desc="Creating dataset thumbnail", total=1) as progress:
                tile_w = 64
                tile_h = 64
                preview = Image.new("RGB", (3 * tile_w, 2 * tile_h))
                for i in range(6):
                    field = image_fields[i % len(image_fields)]
                    row_number = random.randrange(dataset.count_rows())
                    row = dataset.take([row_number]).to_pylist()[0]
                    with Image.open(BytesIO(row[field]._preview_bytes)) as im:
                        preview.paste(im, ((i % 3) * tile_w, (int(i / 3) % 2) * tile_h))
                preview.save(self.target_dir / "preview.png")
                progress.update(1)

    def create_stats(self):
        """Create dataset statistics"""

        # Reset json file
        open(self.target_dir / "db_feature_statistics.json", "w").close()
        # Create objects stats
        self.objects_stats()
        # Create image stats
        self.image_stats()

    def objects_stats(self):
        """Create dataset objects statistics"""

        # Read dataset
        dataset = ds.dataset(self.target_dir / "db", partitioning=self.partitioning)

        # Create stats if objects field exist
        objects = pa.field("objects", pa.list_(arrow_types.ObjectAnnotationType()))
        if objects in self.schema:
            # Create dataframe
            df = dataset.to_table(columns=["split", "objects"]).to_pandas()
            # Split objects in one object per row
            df = df.explode("objects")
            # Remove empty objects
            df = df[df["objects"].notnull()]

            # Get features
            features = []
            for split, object in tqdm(
                zip(df["split"], df["objects"]),
                desc="Computing objects stats",
                total=len(df.index),
            ):
                try:
                    area = 100 * (object["area"] / np.prod(object["mask"]["size"]))
                except TypeError:
                    area = None
                features.append(
                    {
                        "id": object["id"],
                        "view id": object["view_id"],
                        "objects - is group of": object["is_group_of"],
                        "objects - area (%)": area,
                        "objects - category": object["category_name"],
                        "split": split,
                    }
                )
            features_df = pd.DataFrame.from_records(features).astype(
                {
                    "id": "string",
                    "view id": "string",
                    "objects - is group of": bool,
                    "objects - area (%)": float,
                    "objects - category": "string",
                    "split": "string",
                }
            )

            # Initialize stats
            stats = [
                {
                    "name": "objects - category",
                    "type": "categorical",
                    "histogram": [],
                },
                {
                    "name": "objects - is group of",
                    "type": "categorical",
                    "histogram": [],
                },
                {
                    "name": "objects - area (%)",
                    "type": "numerical",
                    "range": [0.0, 100.0],
                    "histogram": [],
                },
            ]

            # Save stats
            self.save_stats(stats, features_df)

    def image_stats(self):
        """Create dataset image statistics"""

        # Read dataset
        dataset = ds.dataset(self.target_dir / "db", partitioning=self.partitioning)

        # Create stats if objects field exist
        schema = dataset.schema

        # Iterate over dataset columns
        for field in schema:
            # If column has images
            if arrow_types.is_image_type(field.type):
                # Get features
                features = []
                for batch_row in tqdm(
                    dataset.to_batches(columns=[field.name, "split"], batch_size=1),
                    desc=f"Computing {field.name} stats",
                    total=dataset.count_rows(),
                ):
                    row = batch_row.to_pydict()
                    # Open image
                    with Image.open(
                        self.target_dir / "media" / row["image"][0]._uri
                    ) as im:
                        im_w, im_h = im.size
                        # Compute image features
                        aspect_ratio = round(im_w / im_h, 1)
                    features.append(
                        {
                            f"{field.name} - aspect ratio": aspect_ratio,
                            "split": row["split"][0],
                        }
                    )
                features_df = pd.DataFrame.from_records(features).astype(
                    {
                        f"{field.name} - aspect ratio": "float",
                        "split": "string",
                    }
                )

                # Initialize stats
                stats = [
                    {
                        "name": f"{field.name} - aspect ratio",
                        "type": "numerical",
                        "histogram": [],
                        "range": [
                            features_df[f"{field.name} - aspect ratio"].min(),
                            features_df[f"{field.name} - aspect ratio"].max(),
                        ],
                    },
                ]

                # Save stats
                self.save_stats(stats, features_df)

    def save_stats(self, stats: list[dict], df: pd.DataFrame):
        """Compute and save stats to json

        Args:
            stats (list[dict]): List of stats to save
            df (pd.DataFrame): DataFrame to create stats from
        """

        # Compute stats
        for split in self.splits:
            for stat in stats:
                split_df = df[df["split"] == split]
                stat["histogram"].extend(compute_stats(split_df, split, stat))

        # Check for existing db_feature_statistics.json
        with open(self.target_dir / "db_feature_statistics.json", "r") as f:
            try:
                stat_json = json.load(f)
                stat_json.extend(stats)
            except ValueError:
                stat_json = stats

        # Add to db_feature_statistics.json
        with open(self.target_dir / "db_feature_statistics.json", "w") as f:
            json.dump(stat_json, f)

    @abstractmethod
    def get_row(self, split: str) -> Generator[dict]:
        """Process dataset row for a given split

        Args:
            split (str): Dataset split

        Yields:
            Generator[dict]: Processed rows
        """

        pass

    def import_dataset(self, batch_size: int = 2048):
        """Import dataset to Pixano format

        Args:
            batch_size (int, optional): Number of rows per file. Defaults to 2048.
        """

        # Iterate on splits
        for split in self.splits:
            batches = _batch_dict(self.get_row(split), batch_size)
            # Iterate on batches
            for i, batch in tqdm(enumerate(batches), desc=f"Converting {split} split"):
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
                # Save to file
                ds.write_dataset(
                    data=pa.Table.from_arrays(arrays, schema=self.schema),
                    base_dir=self.target_dir / "db",
                    basename_template=f"part-{{i}}-{i}.parquet",
                    format="parquet",
                    existing_data_behavior="overwrite_or_ignore",
                    partitioning=self.partitioning,
                )

        # Create spec.json
        self.create_json()

        # Create preview.png
        self.create_preview()

        # Move media folders
        for field in self.schema:
            if arrow_types.is_image_type(field.type):
                field_dir = self.target_dir / "media" / field.name
                field_dir.mkdir(parents=True, exist_ok=True)
                self.source_dirs[field.name].rename(field_dir)

        # Create stats
        self.create_stats()

    def export_dataset(self, export_dir: Path):
        """Export dataset back to original format

        Args:
            export_dir (Path): Export directory
        """

        pass
