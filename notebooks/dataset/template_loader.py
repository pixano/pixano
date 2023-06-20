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

from collections.abc import Generator
from pathlib import Path

import pyarrow as pa
import shortuuid

from pixano.core import arrow_types
from pixano.data.data_loader import DataLoader
from pixano.transforms import coco_names_91, encode_rle, image_to_thumbnail, normalize


class TemplateLoader(DataLoader):
    """Data Loader class template

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
        """Initialize Template Loader

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
        """

        ##### Add your dataset views here #####
        # One image field or multiple fields for multi-view datasets
        views = [pa.field("image", arrow_types.ImageType())]

        # Initialize Data Loader
        super().__init__(name, description, splits, views)

    def get_row(
        self,
        input_dirs: dict[str, Path],
        split: str,
        portable: bool = False,
    ) -> Generator[dict]:
        """Process dataset row for a given split

        Args:
            input_dirs (dict[str, Path]): Dataset input directories
            split (str): Dataset split
            portable (bool, optional): True to move or download media files inside dataset. Defaults to False.

        Yields:
            Generator[dict]: Processed rows
        """

        ##### Retrieve your images here #####
        image_paths = []

        ##### Retrieve your annotations here #####
        annotations = []

        # Process rows
        for im_id, im_path in enumerate(image_paths):
            ##### Retrieve image data here #####
            im_height = 0
            im_width = 0
            im_anns = annotations[im_id]

            # Create image thumbnail
            im_thumb = image_to_thumbnail(im_path.read_bytes())
            # Set image URI
            im_uri = (
                f"image/{split}/{im_path.name}"
                if portable
                else f"file://{im_path.absolute()}"
            )

            ##### Fill row with ID, image, and list of annotations #####
            row = {
                "id": im_path.stem,
                "image": {
                    "uri": im_uri,
                    "preview_bytes": im_thumb,
                },
                "objects": [
                    arrow_types.ObjectAnnotation(
                        id=shortuuid.uuid(),
                        view_id="image",
                        area=float(ann["area"]),
                        bbox=normalize(ann["bbox"], im_height, im_width),
                        mask=encode_rle(ann["segmentation"], im_height, im_width),
                        is_group_of=False,
                        category_id=int(ann["category_id"]),
                        category_name=coco_names_91(ann["category_id"]),
                    ).dict()
                    for ann in im_anns
                ],
                "split": split,
            }

            # Return row
            yield row
