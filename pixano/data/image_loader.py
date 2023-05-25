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
from collections.abc import Generator
from pathlib import Path

import pyarrow as pa
import shortuuid

from pixano.core import arrow_types
from pixano.transforms import image_to_thumbnail

from .data_loader import DataLoader


class ImageLoader(DataLoader):
    """Data Loader class for demo datasets

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
        image_paths = []
        for type in ["*.png", "*.jpg", "*.jpeg"]:
            image_paths.extend(glob.glob(str(self.source_dirs["image"] / split / type)))
        image_paths = [Path(p) for p in sorted(image_paths)]

        # Process rows
        for im_path in sorted(image_paths):
            # Create image thumbnail
            im_thumb = image_to_thumbnail(im_path.read_bytes())

            # Fill row with ID, image, and list of image annotations
            row = {
                "id": shortuuid.uuid(),
                "image": {
                    "uri": f"image/{split}/{im_path.name}",
                    "preview_bytes": im_thumb,
                },
                "objects": [
                    arrow_types.ObjectAnnotation(
                        id=shortuuid.uuid(),
                        view_id="image",
                        bbox=[0.0, 0.0, 0.0, 0.0],
                        category_id=-1,
                        category_name="No ground truths",
                    ).dict()
                ],
                "split": split,
            }

            # Return row
            yield row
