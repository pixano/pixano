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

from pixano.core import BBox, CompressedRLE, Image
from pixano.data.dataset import DatasetCategory, DatasetTable
from pixano.data.importers.importer import Importer
from pixano.utils import image_to_thumbnail, natural_key


class COCOImporter(Importer):
    """Importer class for COCO instances format datasets

    Attributes:
        info (DatasetInfo): Dataset information
        input_dirs (dict[str, Path]): Dataset input directories
    """

    def __init__(
        self,
        name: str,
        description: str,
        input_dirs: dict[str, Path],
        splits: list[str],
        media_fields: dict[str, str] = {"image": "image"},
    ):
        """Initialize COCO Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            input_dirs (dict[str, Path]): Dataset input directories
            splits (list[str]): Dataset splits
            media_fields (dict[str, str]): Dataset media fields, with field names as keys and field types as values. Default to {"image": "image"}.
        """

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
            "objects": [
                DatasetTable(
                    name="objects",
                    fields={
                        "id": "str",
                        "item_id": "str",
                        "view_id": "str",
                        "bbox": "bbox",
                        "mask": "compressedrle",
                        "category_id": "int",
                        "category_name": "str",
                    },
                    source="Ground Truth",
                )
            ],
        }

        # Add media fields to tables
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

        # Check input directories
        self.input_dirs = input_dirs
        for source_path in self.input_dirs.values():
            if not source_path.exists():
                raise FileNotFoundError(f"{source_path} does not exist.")
            if not any(source_path.iterdir()):
                raise FileNotFoundError(f"{source_path} is empty.")

        # Get COCO categories
        categories = []
        for split in splits:
            with open(input_dirs["objects"] / f"instances_{split}.json", "r") as f:
                coco_instances = json.load(f)
                for category in coco_instances["categories"]:
                    categories.append(DatasetCategory.model_validate(category))

        # Initialize Importer
        super().__init__(name, description, tables, splits, categories)

    def import_rows(self) -> Iterator:
        """Process dataset rows for import

        Yields:
            Iterator: Processed rows
        """

        # Iterate on splits
        for split in self.info.splits:
            # Open annotation files
            with open(self.input_dirs["objects"] / f"instances_{split}.json", "r") as f:
                coco_instances = json.load(f)

            # Group annotations by image ID
            annotations = defaultdict(list)
            for ann in coco_instances["annotations"]:
                annotations[ann["image_id"]].append(ann)

            # Create a COCO category id to COCO category dictionary
            categories = {}
            for cat in coco_instances["categories"]:
                categories[cat["id"]] = cat

            # Process rows
            for im in sorted(
                coco_instances["images"], key=lambda x: natural_key(str(x["id"]))
            ):
                # Load image annotations
                im_anns = annotations[im["id"]]
                # Load image
                file_name_uri = urlparse(im["file_name"])
                if file_name_uri.scheme == "":
                    im_path = self.input_dirs["image"] / split / im["file_name"]
                else:
                    im_path = Path(file_name_uri.path)

                # Create image thumbnail
                im_thumb = image_to_thumbnail(im_path.read_bytes())

                # Set image URI
                im_uri = f"image/{split}/{im_path.name}"

                # Return rows
                rows = {
                    "main": {
                        "db": [
                            {
                                "id": str(im["id"]),
                                "views": ["image"],
                                "split": split,
                            }
                        ]
                    },
                    "media": {
                        "image": [
                            {
                                "id": str(im["id"]),
                                "image": Image(im_uri, None, im_thumb).to_dict(),
                            }
                        ]
                    },
                    "objects": {
                        "objects": [
                            {
                                "id": str(ann["id"]),
                                "item_id": str(im["id"]),
                                "view_id": "image",
                                "bbox": BBox.from_xywh(ann["bbox"])
                                .normalize(im["height"], im["width"])
                                .to_dict()
                                if ann["bbox"]
                                else None,
                                "mask": CompressedRLE.encode(
                                    ann["segmentation"], im["height"], im["width"]
                                ).to_dict()
                                if ann["segmentation"]
                                else None,
                                "category_id": int(ann["category_id"]),
                                "category_name": str(
                                    categories[ann["category_id"]]["name"]
                                ),
                            }
                            for ann in im_anns
                        ]
                    },
                }

                yield rows
