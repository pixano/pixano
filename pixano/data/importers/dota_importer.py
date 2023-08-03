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
from PIL import Image as PILImage

from pixano.core import (
    BBox,
    Fields,
    Image,
    ImageType,
    ObjectAnnotation,
    ObjectAnnotationType,
)
from pixano.utils import dota_ids, image_to_thumbnail, natural_key

from .importer import Importer


class DOTAImporter(Importer):
    """Importer class for DOTA dataset

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
        """Initialize DOTAImporter

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
        """

        self.fields = Fields.from_dict(
            {
                "id": "str",
                "image": "Image",
                "objects": "[ObjectAnnotation]",
                "split": "str",
            }
        )

        self.splits = splits

        # Initialize Importer
        super().__init__(name, description, self.fields)

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

                # Fill row with ID, image, and list of image annotations
                with open(im_anns_file) as im_anns:
                    row = {
                        "id": im_path.stem,
                        "image": Image(im_uri, None, im_thumb),
                        "objects": [
                            ObjectAnnotation(
                                id=shortuuid.uuid(),
                                view_id="image",
                                bbox=BBox.from_xyxy(
                                    [
                                        float(line.strip().split()[0]),
                                        float(line.strip().split()[1]),
                                        float(line.strip().split()[4]),
                                        float(line.strip().split()[5]),
                                    ]
                                ).normalize(im_h, im_w),
                                is_difficult=bool(line.strip().split()[9]),
                                category_id=dota_ids(str(line.strip().split()[8])),
                                category_name=str(line.strip().split()[8]).replace(
                                    "-", " "
                                ),
                            )
                            for line in im_anns
                        ],
                        "split": split,
                    }
                    struct_arr = pa.StructArray.from_arrays(
                        [
                            pa.array([row["id"]]),
                            ImageType.Array.from_list([row["image"]]),
                            ObjectAnnotationType.Array.from_lists([row["objects"]]),
                            pa.array([row["split"]]),
                        ],
                        fields=self.fields.to_pyarrow(),
                    )

                    # Return row
                    yield pa.RecordBatch.from_struct_array(struct_arr)
