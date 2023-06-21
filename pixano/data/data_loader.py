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

import datetime
import json
import os
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
import pyarrow.parquet as pq
import shortuuid
from PIL import Image
from tqdm.auto import tqdm

from pixano.analytics import compute_stats
from pixano.core import DatasetInfo, arrow_types
from pixano.transforms import denormalize, rle_to_urle


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
        splits (list[str]): Dataset splits
        schema (pa.schema): Dataset schema
        partitioning (ds.partitioning): Dataset partitioning
    """

    def __init__(
        self,
        name: str,
        description: str,
        splits: list[str],
        views: list[pa.field],
    ):
        """Initialize Data Loader

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
            views (list[pa.field]): Dataset views
        """

        # Dataset info
        self.info = DatasetInfo(
            id=shortuuid.uuid(),
            name=name,
            description=description,
            num_elements=0,
        )
        self.splits = splits

        # Dataset schema
        fields = [
            pa.field("split", pa.string()),
            pa.field("id", pa.string()),
            pa.field("objects", pa.list_(arrow_types.ObjectAnnotationType())),
        ]
        fields.extend(views)
        self.schema = pa.schema(fields)
        self.partitioning = ds.partitioning(
            pa.schema([("split", pa.string())]), flavor="hive"
        )

    def create_json(self, import_dir: Path):
        """Create dataset spec.json

        Args:
            import_dir (Path): Dataset import directory
        """

        with tqdm(desc="Creating dataset info file", total=1) as progress:
            # Read dataset
            dataset = ds.dataset(import_dir / "db", partitioning=self.partitioning)

            # Check number of rows in the created dataset
            self.info.num_elements = dataset.count_rows()

            # Create spec.json
            with open(import_dir / "spec.json", "w") as f:
                json.dump(vars(self.info), f)
            progress.update(1)

    def create_preview(self, import_dir: Path):
        """Create dataset preview image

        Args:
            import_dir (Path): Dataset import directory
        """

        # Read dataset
        dataset = ds.dataset(import_dir / "db", partitioning=self.partitioning)

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
            import_dir (Path): Dataset import directory
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
            import_dir (Path): Dataset import directory
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
            import_dir (Path): Dataset import directory
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
                    im = row[field.name][0].as_py(uri_prefix).as_pillow()
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
            import_dir (Path): Dataset import directory
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
    def get_row(
        self,
        input_dirs: dict[str, Path],
        split: str,
        portable: bool = False,
    ) -> Generator[dict]:
        """Process dataset row for a given split

        Args:
            input_dirs (dict[str, Path]): Dataset input directories
            split (str): Dataset split
            portable (bool, optional): True to move or download media files inside dataset. Defaults to False.

        Yields:
            Generator[dict]: Processed rows
        """

        pass

    def import_dataset(
        self,
        input_dirs: dict[str, Path],
        import_dir: Path,
        portable: bool = False,
        batch_size: int = 2048,
    ):
        """Import dataset to Pixano format

        Args:
            input_dirs (dict[str, Path]): Dataset input directories
            import_dir (Path): Dataset import directory
            portable (int, optional): True to move or download files inside import directory. Defaults to False.
            batch_size (int, optional): Number of rows per file. Defaults to 2048.
        """

        # Check input directories
        for source_path in input_dirs.values():
            if not Path.exists(source_path):
                raise Exception(f"{source_path} does not exist.")
            if not any(source_path.iterdir()):
                raise Exception(f"{source_path} is empty.")

        # Iterate on splits
        for split in self.splits:
            batches = _batch_dict(self.get_row(input_dirs, split, portable), batch_size)
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
                    base_dir=import_dir / "db",
                    basename_template=f"part-{{i}}-{i}.parquet",
                    format="parquet",
                    existing_data_behavior="overwrite_or_ignore",
                    partitioning=self.partitioning,
                )

        # Create spec.json
        self.create_json(import_dir)

        # Create preview.png
        self.create_preview(import_dir)

        # Move media directories if portable
        if portable:
            for field in tqdm(self.schema, desc=f"Moving media directories"):
                if arrow_types.is_image_type(field.type):
                    field_dir = import_dir / "media" / field.name
                    field_dir.mkdir(parents=True, exist_ok=True)
                    input_dirs[field.name].rename(field_dir)

        # Create stats
        self.create_stats(import_dir)

    def export_dataset(self, input_dir: Path, export_dir: Path):
        """Export dataset back to original format

        Args:
            input_dir (Path): Input directory
            export_dir (Path): Export directory
        """

        # Load spec.json
        input_info = DatasetInfo.parse_file(input_dir / "spec.json")

        # Create URI prefix
        media_dir = input_dir / "media"
        uri_prefix = media_dir.absolute().as_uri()

        # If splits provided, check if they exist
        splits = [f"split={s}" for s in self.splits if not s.startswith("split=")]
        for split in splits:
            split_dir = input_dir / "db" / split
            if not Path.exists(split_dir):
                raise Exception(f"{split_dir} does not exist.")
            if not any(split_dir.iterdir()):
                raise Exception(f"{split_dir} is empty.")

        # If no splits provided, select all splits
        if splits == []:
            splits = [s.name for s in os.scandir(input_dir / "db") if s.is_dir()]

        # Iterate on splits
        for split in splits:
            # List dataset files
            files = sorted((input_dir / "db" / split).glob("*.parquet"))
            split_name = split.replace("split=", "")

            # Iterate on files
            for file in tqdm(files, desc=f"Processing {split_name} split", position=0):
                # Load file into rows
                table = pq.read_table(file)
                rows = table.to_batches(max_chunksize=1)
                images = []
                annotations = []
                categories = []
                seen_category_ids = []

                # Iterate on rows
                for row in tqdm(
                    rows,
                    desc=f"Processsing {file.name}",
                    total=table.num_rows,
                    position=1,
                ):
                    for field in self.schema:
                        # If column has images
                        if arrow_types.is_image_type(field.type):
                            # Open image
                            image = row[field.name][0].as_py(uri_prefix)
                            im_w, im_h = image.as_pillow().size
                            # Append image info
                            images.append(
                                {
                                    "license": 1,
                                    "file_name": image.uri,
                                    "height": im_h,
                                    "width": im_w,
                                    "id": row["id"][0].as_py(),
                                }
                            )
                        # If column has annotations
                        # TODO: Change to checking type when ObjectAnnotationType is rebuilt
                        elif field.name == "objects":
                            row_anns = row["objects"][0].as_py()
                            for row_ann in row_anns:
                                # Append annotation
                                annotations.append(
                                    {
                                        "segmentation": rle_to_urle(row_ann["mask"]),
                                        "area": row_ann["area"],
                                        "iscrowd": 0,
                                        "image_id": row["id"][0].as_py(),
                                        "bbox": denormalize(
                                            row_ann["bbox"], *row_ann["mask"]["size"]
                                        ),
                                        "category_id": row_ann["category_id"],
                                        "category_name": row_ann["category_name"],
                                        "id": row_ann["id"],
                                    }
                                )
                                # Append category if not seen yet
                                if row_ann["category_id"] not in seen_category_ids:
                                    categories.append(
                                        {
                                            "supercategory": "N/A",
                                            "id": row_ann["category_id"],
                                            "name": row_ann["category_name"],
                                        },
                                    )
                                    seen_category_ids.append(row_ann["category_id"])

            # Create COCO info fields
            coco_info = {
                "description": input_info.name,
                "url": "N/A",
                "version": f"v{datetime.datetime.now().strftime('%y%m%d.%H%M%S')}",
                "year": datetime.date.today().year,
                "contributor": "Exported from Pixano",
                "date_created": datetime.date.today().isoformat(),
            }
            coco_licences = [
                {
                    "url": "N/A",
                    "id": 1,
                    "name": "Unknown",
                },
            ]

            # Create COCO json
            coco_json = {
                "info": coco_info,
                "licences": coco_licences,
                "images": images,
                "annotations": annotations,
                "categories": categories,
            }

            # Save COCO json
            with open(export_dir / f"instances_{split_name}.json", "w") as f:
                json.dump(coco_json, f)
