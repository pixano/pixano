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

import shortuuid

from pixano.core import BBox, CompressedRLE, Image
from pixano.data.importers.importer import Importer
from pixano.data.item.item_feature import FeaturesValues, FeatureValues
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
        media_fields: dict[str, str] = None,
    ):
        """Initialize COCO Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            input_dirs (dict[str, Path]): Dataset input directories
            splits (list[str]): Dataset splits
            media_fields (dict[str, str]): Dataset media fields, with field names as keys and field types as values. Default to None.
        """

        # Object fields
        object_fields = {
            "original_id": "str",
            "bbox": "bbox",
            "mask": "compressedrle",
            "category": "str",
            "category_id": "int",
            "supercategory": "str",
        }

        # Create features_values
        features_values = FeaturesValues(
            objects={
                "category": FeatureValues(restricted=False, values=[]),
                "category_id": FeatureValues(restricted=False, values=[]),
                "supercategory": FeatureValues(restricted=False, values=[]),
            }
        )
        for split in splits:
            with open(
                input_dirs["objects"] / f"instances_{split}.json", "r", encoding="utf-8"
            ) as f:
                coco_instances = json.load(f)
                if "categories" in coco_instances:
                    for category in coco_instances["categories"]:
                        features_values.objects["category"].values.append(
                            category["name"]
                        )
                        features_values.objects["category_id"].values.append(
                            category["id"]
                        )
                        if "supercategory" in category:
                            features_values.objects["supercategory"].values.append(
                                category["supercategory"]
                            )
        if len(features_values.objects["supercategory"].values) == 0:
            features_values.objects.pop("supercategory")
            object_fields.pop("supercategory")
        else:
            features_values.objects["supercategory"].values = list(
                set(features_values.objects["supercategory"].values)
            )
        FeaturesValues.model_validate(features_values)

        # Create tables
        tables = super().create_tables(
            media_fields,
            object_fields,
        )

        # Initialize Importer
        self.input_dirs = input_dirs
        super().__init__(name, description, tables, splits, features_values)

    def import_rows(self) -> Iterator:
        """Process dataset rows for import

        Yields:
            Iterator: Processed rows
        """

        # Iterate on splits
        for split in self.info.splits:
            # Open annotation files
            with open(
                self.input_dirs["objects"] / f"instances_{split}.json",
                "r",
                encoding="utf-8",
            ) as f:
                coco_instances = json.load(f)

            # Group annotations by image ID
            annotations = defaultdict(list)
            for ann in coco_instances["annotations"]:
                annotations[ann["image_id"]].append(ann)

            # Create a COCO category id to COCO category name and supercategory dictionary
            categories = {}
            supercategories = {}
            for cat in coco_instances["categories"]:
                categories[cat["id"]] = cat["name"]
                supercategories[cat["id"]] = (
                    cat["supercategory"] if "supercategory" in cat else None
                )

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

                # Set unique id
                item_id = shortuuid.uuid()

                # Return rows
                rows = {
                    "main": {
                        "db": [
                            {
                                "id": item_id,
                                "original_id": str(im["id"]),
                                "views": ["image"],
                                "split": split,
                            }
                        ]
                    },
                    "media": {
                        "image": [
                            {
                                "id": item_id,
                                "image": Image(im_uri, None, im_thumb).to_dict(),
                            }
                        ]
                    },
                    "objects": {
                        "objects": [
                            {
                                "id": shortuuid.uuid(),
                                "original_id": str(ann["id"]),
                                "item_id": item_id,
                                "view_id": "image",
                                "bbox": (
                                    BBox.from_xywh(ann["bbox"])
                                    .normalize(im["height"], im["width"])
                                    .to_dict()
                                    if ann["bbox"]
                                    else None
                                ),
                                "mask": (
                                    CompressedRLE.encode(
                                        ann["segmentation"], im["height"], im["width"]
                                    ).to_dict()
                                    if ann["segmentation"]
                                    else None
                                ),
                                "category": str(categories[ann["category_id"]]),
                                "category_id": ann["category_id"],
                                "supercategory": supercategories[ann["category_id"]],
                            }
                            for ann in im_anns
                        ]
                    },
                }

                # Remove supercategory if empty
                for obj in rows["objects"]["objects"]:
                    if obj["supercategory"] is None:
                        obj.pop("supercategory")

                yield rows
