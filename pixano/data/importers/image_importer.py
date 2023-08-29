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

from pixano.core import Image, ImageType
from pixano.data import Fields
from pixano.data.importers.importer import Importer
from pixano.utils import image_to_thumbnail, natural_key


class ImageImporter(Importer):
    """Importer class for image datasets

    Attributes:
        info (DatasetInfo): Dataset information
        schema (pa.schema): Dataset schema
        splits (list[str]): Dataset splits
    """

    def __init__(self, name: str, description: str, splits: list[str]):
        """Initialize Image Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
        """

        fields = Fields.from_dict(
            {
                "id": "str",
                "image": "Image",
                "split": "str",
            }
        )

        # Initialize Importer
        super().__init__(name, description, fields, splits)

    def import_row(
        self,
        input_dirs: dict[str, Path],
        portable: bool = False,
    ) -> Iterator:
        """Process dataset row for import

        Args:
            input_dirs (dict[str, Path]): Input directories
            portable (bool, optional): True to move or download media files inside dataset. Defaults to False.

        Yields:
            Iterator: Processed rows
        """
        for split in self.splits:
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

                # Fill row with ID, image, and split
                row = {
                    "id": im_path.name,
                    "image": Image(im_uri, None, im_thumb),
                    "split": split,
                }

                yield super().dict_to_structarray(row)
