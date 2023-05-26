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
from collections import defaultdict
from collections.abc import Generator
from pathlib import Path

import pyarrow as pa

from pixano.core import arrow_types
from pixano.transforms import coco_names_91, encode_rle, image_to_thumbnail, normalize

from .data_loader import DataLoader


class COCOLoader(DataLoader):
    """Data Loader class for COCO instances dataset

    Attributes:
        name (str): Dataset name
        description (str): Dataset description
        source_dirs (dict[str, Path]): Dataset source directories
        target_dir (Path): Dataset target directory
        schema (pa.schema): Dataset schema
        partitioning (ds.partitioning): Dataset partitioning
    """

    def __init__(
        self,
        name: str,
        description: str,
        source_dirs: dict[str, Path],
        target_dir: Path,
    ):
        """Initialize COCO Loader

        Args:
            name (str): Dataset name
            description (str): Dataset description
            source_dirs (dict[str, Path]): Dataset source directories
            target_dir (Path): Dataset target directory
        """

        # Dataset additional fields (in addition to split, id, and objects)
        add_fields = [pa.field("image", arrow_types.ImageType())]

        # Initialize Data Loader
        super().__init__(name, description, source_dirs, target_dir, add_fields)

    def get_row(self, split: str) -> Generator[dict]:
        """Process dataset row for a given split

        Args:
            split (str): Dataset split

        Yields:
            Generator[dict]: Rows processed to be stored in a parquet
        """

        # Open annotation files
        with open(self.source_dirs["objects"] / f"instances_{split}.json", "r") as f:
            coco_instances = json.load(f)

        # Group annotations by image ID
        annotations = defaultdict(list)
        for ann in coco_instances["annotations"]:
            annotations[ann["image_id"]].append(ann)

        # Process rows
        for im in sorted(coco_instances["images"], key=lambda x: x["id"]):
            # Load image annotations
            im_anns = annotations[im["id"]]
            # Load image directory
            im_path = self.source_dirs["image"] / split / im["file_name"]
            # Create image thumbnail
            im_thumb = image_to_thumbnail(im_path.read_bytes())

            # Fill row with ID, image, and list of image annotations
            row = {
                "id": str(im["id"]),
                "image": {
                    "uri": f"image/{split}/{im['file_name']}",
                    "preview_bytes": im_thumb,
                },
                "objects": [
                    arrow_types.ObjectAnnotation(
                        id=str(ann["id"]),
                        view_id="image",
                        area=float(ann["area"]),
                        bbox=normalize(ann["bbox"], im["height"], im["width"]),
                        mask=encode_rle(ann["segmentation"], im["height"], im["width"]),
                        is_group_of=bool(ann["iscrowd"]),
                        category_id=int(ann["category_id"]),
                        category_name=coco_names_91(ann["category_id"]),
                    ).dict()
                    for ann in im_anns
                ],
                "split": split,
            }

            # Return row
            yield row
