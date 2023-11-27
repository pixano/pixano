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

import glob
from collections.abc import Iterator
from pathlib import Path

from pixano.core import BBox, CompressedRLE, Image
from pixano.data import Importer
from pixano.utils import coco_names_91, image_to_thumbnail


class TemplateImporter(Importer):
    """Template Dataset Importer class template

    Attributes:
        info (DatasetInfo): Dataset information
        schema (pa.schema): Dataset schema
        splits (list[str]): Dataset splits
    """

    def __init__(
        self,
        name: str,
        description: str,
        splits: list[str],
    ):
        """Initialize Template Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
        """

        tables = {
            "main": [
                {
                    "name": "db",
                    "fields": {
                        "id": "str",
                        "views": "[str]",
                        "split": "str",
                    },
                }
            ],
            "media": [
                {
                    "name": "image",
                    "fields": {
                        "id": "str",
                        "image": "image",
                    },
                }
            ],
            "objects": [
                {
                    "name": "objects",
                    "fields": {
                        "id": "str",
                        "item_id": "str",
                        "view_id": "str",
                        "bbox": "bbox",
                        "mask": "compressedrle",
                        "category_id": "int",
                        "category_name": "str",
                    },
                    "source": "Ground Truth",
                }
            ],
        }

        # Initialize Importer
        super().__init__(name, description, splits, tables)

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

        for split in self.info.splits:
            ##### Retrieve your annotations #####
            annotations = input_dirs["objects"] / "......"

            ##### Retrieve your images #####
            image_paths = glob.glob(str(input_dirs["image"] / split / "......"))

            # Process rows
            for im_path in image_paths:
                # Create image thumbnail
                im_thumb = image_to_thumbnail(im_path.read_bytes())
                # Set image URI
                im_uri = f"image/{split}/{im_path.name}"
                # Load image
                image = Image(im_uri, None, im_thumb)
                w, h = image.size

                ##### Load image annotation #####
                im_anns = annotations[im_path]

                # Return rows
                rows = {
                    "main": {
                        "db": [
                            {
                                "id": im_path.name,
                                "views": ["image"],
                                "split": split,
                            }
                        ]
                    },
                    "media": {
                        "image": [
                            {
                                "id": im_path.name,
                                "image": image.to_dict(),
                            }
                        ]
                    },
                    "objects": {
                        "objects": [
                            {
                                "id": str(ann["id"]),
                                "item_id": im_path.name,
                                "view_id": "image",
                                "bbox": BBox.from_xywh(ann["bbox"])
                                .normalize(h, w)
                                .to_dict(),
                                "mask": CompressedRLE.encode(
                                    ann["segmentation"], h, w
                                ).to_dict(),
                                "category_id": int(ann["category_id"]),
                                "category_name": coco_names_91(ann["category_id"]),
                            }
                            for ann in im_anns
                        ]
                    },
                }

                yield rows
