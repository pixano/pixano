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
from msilib import Feature
import random
import shutil
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterator
from io import BytesIO
from itertools import islice
from pathlib import Path

import lance
import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import shortuuid
from PIL import Image
from tqdm.auto import tqdm

from pixano.analytics import compute_stats
from pixano.core import DatasetInfo, arrow_types, Features



class Importer(ABC):
    """Abstract Data Importer class

    Attributes:
        name (str): Dataset name
        description (str): Dataset description
        splits (list[str]): Dataset splits
        schema (pa.schema): Dataset schema
        partitioning (ds.partitioning): Dataset partitioning
    """

    def __init__(
        self,
        name: str,
        description: str,
        features: Features,  # TODO change by spec and feature
    ):
        """Init importer

        Args:
            name (str): name of dataset
            description (str): description of dataset
            features (Features): features of dataset as pixano features
        """

        # Dataset info
        self.info = DatasetInfo(
            id=shortuuid.uuid(),
            name=name,
            description=description,
            num_elements=0,
            preview=None,
            categories=[],
            features=features,
        )

        # Dataset schema
        self.schema = pa.schema(self.info.features.to_fields())


    def create_json(self, import_dir: Path, categories: list[dict] = []):
        """Create dataset spec.json

        Args:
            import_dir (Path): Import directory
            categories (list[dict], optional): Dataset categories. Defaults to [].
        """

        with tqdm(desc="Creating dataset info file", total=1) as progress:

            # Read dataset
            dataset = lance.dataset(import_dir / "db.lance")
            # Check number of rows in the created dataset
            self.info.num_elements += dataset.count_rows()

            # Add categories
            if categories:
                self.info.categories = categories

            # Create spec.json
            with open(import_dir / "spec.json", "w") as f:
                json.dump(vars(self.info), f)
            progress.update(1)

    def create_preview(self, import_dir: Path):
        """Create dataset preview image

        Args:
            import_dir (Path): Import directory
        """

        # Read dataset
        dataset = lance.dataset(import_dir / "db")

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
                preview.save(import_dir / "preview.png")
                progress.update(1)

    def create_stats(self, import_dir: Path):
        """Create dataset statistics

        Args:
            import_dir (Path): Import directory
        """

        # Reset json file
        open(import_dir / "db_feature_statistics.json", "w").close()
        # Create objects stats
        self.objects_stats(import_dir)
        # Create image stats
        self.image_stats(import_dir)

    def objects_stats(self, import_dir: Path):
        """Create dataset objects statistics

        Args:
            import_dir (Path): Import directory
        """

        # Read dataset
        dataset = ds.dataset(import_dir / "db", partitioning=self.partitioning)

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
            self.save_stats(import_dir, stats, features_df)

    def image_stats(self, import_dir: Path):
        """Create dataset image statistics

        Args:
            import_dir (Path): Import directory
        """

        # Read dataset
        dataset = ds.dataset(import_dir / "db", partitioning=self.partitioning)

        # Create URI prefix
        media_dir = import_dir / "media"
        uri_prefix = media_dir.absolute().as_uri()

        # Iterate over dataset columns
        for field in dataset.schema:
            # If column has images
            if arrow_types.is_image_type(field.type):
                features = []
                rows = dataset.to_batches(columns=[field.name, "split"], batch_size=1)

                # Get features
                for row in tqdm(
                    rows,
                    desc=f"Computing {field.name} stats",
                    total=dataset.count_rows(),
                ):
                    # Open image
                    im = row[field.name][0].as_py(uri_prefix)
                    im_w, im_h = im.size
                    # Compute image features
                    aspect_ratio = round(im_w / im_h, 1)
                    features.append(
                        {
                            f"{field.name} - aspect ratio": aspect_ratio,
                            "split": row["split"][0].as_py(),
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
                self.save_stats(import_dir, stats, features_df)

    def save_stats(self, import_dir: Path, stats: list[dict], df: pd.DataFrame):
        """Compute and save stats to json

        Args:
            import_dir (Path): Import directory
            stats (list[dict]): List of stats to save
            df (pd.DataFrame): DataFrame to create stats from
        """

        # Compute stats
        for split in self.splits:
            for stat in stats:
                split_df = df[df["split"] == split]
                stat["histogram"].extend(compute_stats(split_df, split, stat))

        # Check for existing db_feature_statistics.json
        with open(import_dir / "db_feature_statistics.json", "r") as f:
            try:
                stat_json = json.load(f)
                stat_json.extend(stats)
            except ValueError:
                stat_json = stats

        # Add to db_feature_statistics.json
        with open(import_dir / "db_feature_statistics.json", "w") as f:
            json.dump(stat_json, f)

    @abstractmethod
    def import_row(
        self,
        input_dirs: str | Path
    ) -> Iterator:
        """Process dataset row for import

        Args:
            input_dirs (dict[str, Path]): Input directories

        Yields:
            Iterator: Processed rows
        """

        pass

    def import_dataset(
        self,
        input_dirs: dict[str, Path],
        import_dir: Path,
        portable: bool = False,
    ):
        """Import dataset to Pixano format

        Args:
            input_dirs (dict[str, Path]): Input directories
            import_dir (Path): Import directory
            portable (int, optional): True to move or download files inside import directory. Defaults to False.
            batch_size (int, optional): Number of rows per file. Defaults to 2048.
        """

        # Check input directories
        for source_path in input_dirs.values():
            if not source_path.exists():
                raise Exception(f"{source_path} does not exist.")
            if not any(source_path.iterdir()):
                raise Exception(f"{source_path} is empty.")


        # Iterate on splits
        reader = pa.RecordBatchReader.from_batches(self.schema(), self.import_row(input_dirs))
        ds = lance.write_dataset(reader, import_dir / "db.lance", str="overwrite")

        # Create spec.json
        self.create_json(import_dir)

        # Create preview.png
        self.create_preview(import_dir)

        # Move media directories if portable
        if portable:
            for field in tqdm(self.schema, desc="Moving media directories"):
                if arrow_types.is_image_type(field.type):
                    field_dir = import_dir / "media" / field.name
                    field_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copytree(
                        input_dirs[field.name], field_dir, dirs_exist_ok=True
                    )

        # Create stats
        self.create_stats(import_dir)
