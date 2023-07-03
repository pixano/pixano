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

from pixano.core import arrow_types
from pixano.transforms import image_to_thumbnail, natural_key

from .data_loader import DataLoader


class ImageLoader(DataLoader):
    """Data Loader class for demo datasets

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
        image_paths = []
        for type in ["*.png", "*.jpg", "*.jpeg"]:
            image_paths.extend(glob.glob(str(input_dirs["image"] / split / type)))
        image_paths = [Path(p) for p in sorted(image_paths, key=natural_key)]

        # Process rows
        for im_path in image_paths:
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
                "id": im_path.name,
                "image": arrow_types.Image(im_uri, None, im_thumb).to_dict(),
                # TODO: find a way to return an empty list
                "objects": [
                    arrow_types.ObjectAnnotation(
                        id=shortuuid.uuid(),
                        category_id=0,
                    ).dict()
                ],
                "split": split,
            }

            # Return row
            yield row
