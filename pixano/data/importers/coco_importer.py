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
from collections.abc import Iterator
from pathlib import Path
from urllib.parse import urlparse

import pyarrow as pa

from pixano import types
from pixano.utils import (
    coco_names_91,
    image_to_thumbnail,
    natural_key,
)

from .data_importer import DataImporter


class COCOImporter(DataImporter):
    """Data Importer class for COCO instances dataset

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
        """Initialize COCO Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
        """

        # Dataset views
        views = [pa.field("image", types.ImageType)]

        # Initialize Data Importer
        super().__init__(name, description, splits, views)

    def import_row(
        self,
        input_dirs: dict[str, Path],
        split: str,
        portable: bool = False,
    ) -> Iterator:
        """Process dataset row for import

        Args:
            input_dirs (dict[str, Path]): Input directories
            split (str): Dataset split
            portable (bool, optional): True to move or download media files inside dataset. Defaults to False.

        Yields:
            Iterator: Processed rows
        """

        # Open annotation files
        with open(input_dirs["objects"] / f"instances_{split}.json", "r") as f:
            coco_instances = json.load(f)

        # Group annotations by image ID
        annotations = defaultdict(list)
        for ann in coco_instances["annotations"]:
            annotations[ann["image_id"]].append(ann)

        # Process rows
        for im in sorted(coco_instances["images"], key=lambda x: natural_key(x["id"])):
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
                "image": types.Image(im_uri, None, im_thumb),
                "objects": [
                    types.ObjectAnnotation(
                        id=str(ann["id"]),
                        view_id="image",
                        area=float(ann["area"]) if ann["area"] else None,
                        bbox=types.BBox.from_xywh(ann["bbox"]).normalize(
                            im["height"], im["width"]
                        ),
                        mask=types.CompressedRLE.encode(
                            ann["segmentation"], im["height"], im["width"]
                        ),
                        is_group_of=bool(ann["iscrowd"]) if ann["iscrowd"] else None,
                        category_id=int(ann["category_id"]),
                        category_name=coco_names_91(ann["category_id"]),
                    )
                    for ann in im_anns
                ],
                "split": split,
            }

            # Return row
            yield row
