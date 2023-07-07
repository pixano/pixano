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

import pyarrow as pa
import shortuuid
from PIL import Image

from pixano.core import arrow_types
from pixano.transforms import (
    dota_ids,
    image_to_thumbnail,
    natural_key,
    normalize,
    xyxy_to_xywh,
)

from .data_loader import DataLoader


class DOTALoader(DataLoader):
    """Data Loader class for DOTA dataset

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
    ) -> Iterator:
        """Process dataset row for import

        Args:
            input_dirs (dict[str, Path]): Input directories
            split (str): Dataset split
            portable (bool, optional): True to move or download media files inside dataset. Defaults to False.

        Yields:
            Iterator: Processed rows
        """

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

            # Allow DOTA largest images
            Image.MAX_IMAGE_PIXELS = 806504000

            # Get image dimensions and thumbnail
            with Image.open(im_path) as im:
                im_w, im_h = im.size
                im_thumb = image_to_thumbnail(im)

            # Set image URI
            im_uri = (
                f"image/{split}/{im_path.name}"
                if portable
                else im_path.absolute().as_uri()
            )

            # Fill row with ID, image, and list of image annotations
            with open(im_anns_file) as im_anns:
                row = {
                    "id": im_path.stem,
                    "image": arrow_types.Image(im_uri, None, im_thumb).to_dict(),
                    "objects": [
                        arrow_types.ObjectAnnotation(
                            id=shortuuid.uuid(),
                            view_id="image",
                            bbox=normalize(
                                xyxy_to_xywh(
                                    [
                                        float(line.strip().split()[0]),
                                        float(line.strip().split()[1]),
                                        float(line.strip().split()[4]),
                                        float(line.strip().split()[5]),
                                    ]
                                ),
                                im_h,
                                im_w,
                            ),
                            is_difficult=bool(line.strip().split()[9]),
                            category_id=dota_ids(str(line.strip().split()[8])),
                            category_name=str(line.strip().split()[8]).replace(
                                "-", " "
                            ),
                        ).dict()
                        for line in im_anns
                    ],
                    "split": split,
                }

            # Return row
            yield row
