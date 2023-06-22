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
from collections import defaultdict
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm.auto import tqdm

from pixano.core import DatasetInfo, arrow_types
from pixano.transforms import (
    coco_names_91,
    denormalize,
    encode_rle,
    image_to_thumbnail,
    normalize,
    rle_to_urle,
)

from .data_loader import DataLoader


class COCOLoader(DataLoader):
    """Data Loader class for COCO instances dataset

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
    ):
        """Initialize COCO Loader

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
        """

        # Dataset views
        views = [pa.field("image", arrow_types.ImageType())]

        # Initialize Data Loader
        super().__init__(name, description, splits, views)

    def import_row(
        self,
        input_dirs: dict[str, Path],
        split: str,
        portable: bool = False,
    ) -> Generator[dict]:
        """Process dataset row for import

        Args:
            input_dirs (dict[str, Path]): Input directories
            split (str): Dataset split
            portable (bool, optional): True to move or download media files inside dataset. Defaults to False.

        Yields:
            Generator[dict]: Processed rows
        """

        # Open annotation files
        with open(input_dirs["objects"] / f"instances_{split}.json", "r") as f:
            coco_instances = json.load(f)

        # Group annotations by image ID
        annotations = defaultdict(list)
        for ann in coco_instances["annotations"]:
            annotations[ann["image_id"]].append(ann)

        # Process rows
        for im in sorted(coco_instances["images"], key=lambda x: x["id"]):
            # Load image annotations
            im_anns = annotations[im["id"]]
            # Load image
            file_name_uri = urlparse(im["file_name"])
            if file_name_uri.scheme == "":
                im_path = input_dirs["image"] / split / im["file_name"]
            else:
                im_path = Path(file_name_uri.path)

            # Create image thumbnail
            im_thumb = image_to_thumbnail(im_path.read_bytes())

            # Set image URI
            im_uri = (
                f"image/{split}/{im_path.name}"
                if portable
                else im_path.absolute().as_uri()
            )

            # Fill row with ID, image, and list of image annotations
            row = {
                "id": str(im["id"]),
                "image": arrow_types.Image(im_uri, None, im_thumb).to_dict(),
                "objects": [
                    arrow_types.ObjectAnnotation(
                        id=str(ann["id"]),
                        view_id="image",
                        area=float(ann["area"]) if ann["area"] else None,
                        bbox=normalize(ann["bbox"], im["height"], im["width"]),
                        mask=encode_rle(ann["segmentation"], im["height"], im["width"]),
                        is_group_of=bool(ann["iscrowd"]) if ann["iscrowd"] else None,
                        category_id=int(ann["category_id"]),
                        category_name=coco_names_91(ann["category_id"]),
                    ).dict()
                    for ann in im_anns
                ],
                "split": split,
            }

            # Return row
            yield row

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

            # Create COCO json
            coco_json = {
                "info": {
                    "description": input_info.name,
                    "url": "N/A",
                    "version": f"v{datetime.datetime.now().strftime('%y%m%d.%H%M%S')}",
                    "year": datetime.date.today().year,
                    "contributor": "Exported from Pixano",
                    "date_created": datetime.date.today().isoformat(),
                },
                "licences": [
                    {
                        "url": "N/A",
                        "id": 1,
                        "name": "Unknown",
                    },
                ],
                "images": [],
                "annotations": [],
                "categories": [],
            }

            # Iterate on files
            for file in tqdm(files, desc=f"Processing {split_name} split", position=0):
                # Load file into rows
                table = pq.read_table(file)
                rows = table.to_batches(max_chunksize=1)
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
                            im = row[field.name][0].as_py(uri_prefix)
                            im_w, im_h = im.size
                            # Append image info
                            coco_json["images"].append(
                                {
                                    "license": 1,
                                    "file_name": im.uri,
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
                                coco_json["annotations"].append(
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
                                    coco_json["categories"].append(
                                        {
                                            "supercategory": "N/A",
                                            "id": row_ann["category_id"],
                                            "name": row_ann["category_name"],
                                        },
                                    )
                                    seen_category_ids.append(row_ann["category_id"])

            # Sort categories
            coco_json["categories"] = sorted(
                coco_json["categories"], key=lambda c: c["id"]
            )

            # Save COCO json
            with open(export_dir / f"instances_{split_name}.json", "w") as f:
                json.dump(coco_json, f)
