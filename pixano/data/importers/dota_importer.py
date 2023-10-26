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
from pixano.data.importers.importer import Importer
from pixano.utils import dota_ids, image_to_thumbnail, natural_key


class DOTAImporter(Importer):
    """Importer class for DOTA dataset

    Attributes:
        info (DatasetInfo): Dataset information
    """

    def __init__(
        self,
        name: str,
        description: str,
        splits: list[str],
    ):
        """Initialize DOTA Importer

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
                        "category_id": "int",
                        "category_name": "str",
                    },
                    "source": "Ground Truth",
                }
            ],
        }

        # Initialize Importer
        super().__init__(name, description, tables, splits)

    def import_rows(
        self,
        input_dirs: dict[str, Path],
        portable: bool = False,
    ) -> Iterator:
        """Process dataset rows for import

        Args:
            input_dirs (dict[str, Path]): Input directories
            portable (bool, optional): True to move or download media files inside dataset. Defaults to False.

        Yields:
            Iterator: Processed rows
        """
        for split in self.info.splits:
            # Get images paths
            image_paths = glob.glob(str(input_dirs["image"] / split / "*.png"))
            image_paths = [Path(p) for p in sorted(image_paths, key=natural_key)]

            # Process rows
            for im_path in image_paths:
                # Load image annotations
                im_anns_file = (
                    input_dirs["objects"]
                    / split
                    / "hbb"
                    / im_path.name.replace("png", "txt")
                )
                with open(im_anns_file) as f:
                    im_anns = [line.strip().split() for line in f]

                # Allow DOTA largest images
                PILImage.MAX_IMAGE_PIXELS = 806504000

                # Get image dimensions and thumbnail
                with PILImage.open(im_path) as im:
                    im_w, im_h = im.size
                    im_thumb = image_to_thumbnail(im)

                # Set image URI
                im_uri = (
                    f"image/{split}/{im_path.name}"
                    if portable
                    else im_path.absolute().as_uri()
                )

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
                                "category_id": dota_ids(str(ann[8])),
                                "category_name": str(ann[8]).replace("-", " "),
                            }
                            for ann in im_anns
                        ]
                    },
                }

                yield rows
