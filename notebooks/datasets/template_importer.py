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

from pixano.core import BBox, CompressedRLE, Image, ImageType, ObjectAnnotation
from pixano.data.importers import Importer
from pixano.utils import coco_names_91, image_to_thumbnail


class TemplateImporter(Importer):
    """Template Dataset Importer class template

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
        """Initialize Template Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
        """

        ##### Add your dataset views here #####
        # One image field or multiple fields for multi-view datasets
        views = [pa.field("image", ImageType)]

        # Initialize Importer
        super().__init__(name, description, splits, views)

    def import_row(
        self,
        input_dirs: dict[str, Path],
        split: str,
        portable: bool = False,
    ) -> Generator[dict]:
        """Process dataset row for import

        Args:
            input_dirs (dict[str, Path]): Input directories
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
                else im_path.absolute().as_uri()
            )

            ##### Fill row with ID, image, and list of annotations #####
            row = {
                "id": im_path.stem,
                "image": Image(im_uri, None, im_thumb),
                "objects": [
                    ObjectAnnotation(
                        id=shortuuid.uuid(),
                        view_id="image",
                        area=float(ann["area"]),
                        bbox=BBox.from_xywh(ann["bbox"]).normalize(im_height, im_width),
                        mask=CompressedRLE.from_mask(ann["segmentation"]),
                        is_group_of=False,
                        category_id=int(ann["category_id"]),
                        category_name=coco_names_91(ann["category_id"]),
                    )
                    for ann in im_anns
                ],
                "split": split,
            }

            # Return row
            yield row
