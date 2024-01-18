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

import shortuuid
from PIL import Image as PILImage

from pixano.core import BBox, Image
from pixano.data.dataset import DatasetCategory
from pixano.data.importers.importer import Importer
from pixano.utils import image_to_thumbnail, natural_key


class DOTAImporter(Importer):
    """Importer class for DOTA dataset

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
    ):
        """Initialize DOTA Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            input_dirs (dict[str, Path]): Dataset input directories
            splits (list[str]): Dataset splits
        """

        # Create tables
        tables = super().create_tables(
            media_fields={"image": "image"},
            object_fields={
                "bbox": "bbox",
                "category": "str",
            },
        )

        # Create categories
        categories = [
            DatasetCategory(name="plane", id=1),
            DatasetCategory(name="ship", id=2),
            DatasetCategory(name="storage tank", id=3),
            DatasetCategory(name="baseball diamond", id=4),
            DatasetCategory(name="tennis court", id=5),
            DatasetCategory(name="basketball court", id=6),
            DatasetCategory(name="ground track field", id=7),
            DatasetCategory(name="harbor", id=8),
            DatasetCategory(name="bridge", id=9),
            DatasetCategory(name="large vehicle", id=10),
            DatasetCategory(name="small vehicle", id=11),
            DatasetCategory(name="helicopter", id=12),
            DatasetCategory(name="roundabout", id=13),
            DatasetCategory(name="soccer ball field", id=14),
            DatasetCategory(name="swimming pool", id=15),
            DatasetCategory(name="container crane", id=16),
            DatasetCategory(name="airport", id=17),
            DatasetCategory(name="helipad", id=18),
        ]

        # Initialize Importer
        self.input_dirs = input_dirs
        super().__init__(name, description, tables, splits, categories)

    def import_rows(self) -> Iterator:
        """Process dataset rows for import

        Yields:
            Iterator: Processed rows
        """
        for split in self.info.splits:
            # Get images paths
            image_paths = glob.glob(str(self.input_dirs["image"] / split / "*.png"))
            image_paths = [Path(p) for p in sorted(image_paths, key=natural_key)]

            # Process rows
            for im_path in image_paths:
                # Load image annotations
                im_anns_file = (
                    self.input_dirs["objects"]
                    / split
                    / "hbb"
                    / im_path.name.replace("png", "txt")
                )
                with open(im_anns_file, encoding="utf-8") as f:
                    im_anns = [line.strip().split() for line in f]

                # Allow DOTA largest images
                PILImage.MAX_IMAGE_PIXELS = 806504000

                # Get image dimensions and thumbnail
                with PILImage.open(im_path) as im:
                    im_w, im_h = im.size
                    im_thumb = image_to_thumbnail(im)

                # Set image URI
                im_uri = f"image/{split}/{im_path.name}"

                # Return rows
                rows = {
                    "main": {
                        "db": [
                            {
                                "id": im_path.stem,
                                "views": ["image"],
                                "split": split,
                            }
                        ]
                    },
                    "media": {
                        "image": [
                            {
                                "id": im_path.stem,
                                "image": Image(im_uri, None, im_thumb).to_dict(),
                            }
                        ]
                    },
                    "objects": {
                        "objects": [
                            {
                                "id": shortuuid.uuid(),
                                "item_id": im_path.stem,
                                "view_id": "image",
                                "bbox": BBox.from_xyxy(
                                    [
                                        float(ann[0]),
                                        float(ann[1]),
                                        float(ann[4]),
                                        float(ann[5]),
                                    ]
                                )
                                .normalize(im_h, im_w)
                                .to_dict(),
                                "category": str(ann[8]).replace("-", " "),
                            }
                            for ann in im_anns
                        ]
                    },
                }

                yield rows
