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
from io import BytesIO
from math import isnan
from pathlib import Path
from urllib.parse import urlparse

import pyarrow as pa
from PIL import Image
from pycocotools import mask as mask_api

from pixano.core import arrow_types
from pixano.transforms import denormalize, image_to_thumbnail, xyxy_to_xywh

from .data_loader import DataLoader


class LegacyLoader(DataLoader):
    """Data Loader class for Pixano legacy format datasets

    Attributes:
        name (str): Dataset name
        description (str): Dataset description
        splits (list[str]): Dataset splits
        views (list[str]): Dataset views
        json_files (dict[str, str]): json file paths relative to workspace
    """

    def __init__(
        self,
        name: str,
        description: str,
        splits: list[str],
        views: list[str],
        json_files: dict[str, str],
    ):
        """Initialize Pixano Legacy Loader

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
            views (list[str]): Dataset views
            json_files (dict[str, str]): json file paths relative to workspace
        """

        self.views = views
        self.json_files = json_files

        # Initialize Data Loader
        super().__init__(
            name,
            description,
            splits,
            [pa.field(view, arrow_types.ImageType()) for view in views],
        )

    def import_row(
        self,
        input_dirs: dict[str, Path],
        split: str,
        portable: bool = False,
    ) -> Iterator:
        """Process dataset row for import

        Args:
            input_dirs (dict[str, Path]): Input directory workspace for json files and images
            split (str): Dataset split
            portable (bool, optional): True to move or download media files inside dataset. Defaults to False.

        Yields:
            Iterator: Processed rows
        """

        category_ids = {}
        feats = defaultdict(list)
        for view in self.views:
            # Open annotation files
            with open(input_dirs["workspace"] / self.json_files[view], "r") as f:
                pix_json = json.load(f)

                # Group annotations by image ID (timestamp)
                annotations = defaultdict(list)
                for ann in pix_json["annotations"]:
                    annotations[str(ann["timestamp"])].append(ann)

                # Process rows
                for im in sorted(
                    pix_json["data"]["children"], key=lambda x: x["timestamp"]
                ):
                    # Load image
                    file_name_uri = urlparse(im["path"])
                    if file_name_uri.scheme == "":
                        im_path = input_dirs["workspace"] / im["path"]
                    else:
                        im_path = Path(file_name_uri.path)

                    image = Image.open(BytesIO(im_path.read_bytes()))
                    im_w = image.width
                    im_h = image.height
                    im_thumb = image_to_thumbnail(image)

                    feats[str(im["timestamp"])].append(
                        {
                            "viewId": view,
                            "width": im_w,
                            "height": im_h,
                            "im_thumb": im_thumb,
                            "im_uri": (
                                f"image/{split}/{im_path.name}"
                                if portable
                                else im_path.absolute().as_uri()
                            ),
                            "anns": annotations[str(im["timestamp"])],
                        }
                    )

        for timestamp in feats:
            # Fill row with ID, image
            row = {
                "id": timestamp,
                "objects": [],
                "split": split,
            }
            for f in feats[timestamp]:
                row[f["viewId"]] = arrow_types.Image(
                    f["im_uri"], None, f["im_thumb"]
                ).to_dict()

                # Fill row with list of image annotations
                for ann in f["anns"]:
                    # collect categories to build category ids
                    if ann["category"] not in category_ids:
                        category_ids[ann["category"]] = len(category_ids)

                    bbox = [0.0, 0.0, 0.0, 0.0]
                    mask = None

                    if "geometry" in ann:
                        if (
                            ann["geometry"]["type"] == "polygon"
                            and ann["geometry"]["vertices"]
                        ):
                            # Polygon
                            # we have normalized coords, we must denorm before making RLE
                            if not isnan(ann["geometry"]["vertices"][0]):
                                if len(ann["geometry"]["vertices"]) > 4:
                                    denorm = denormalize(
                                        ann["geometry"]["vertices"],
                                        f["height"],
                                        f["width"],
                                    )
                                    rles = mask_api.frPyObjects(
                                        [denorm], f["height"], f["width"]
                                    )
                                    mask = mask_api.merge(rles)
                                else:
                                    print(
                                        "Polygon with 2 or less points. Discarded\n",
                                        ann["geometry"],
                                    )
                        elif (
                            ann["geometry"]["type"] == "mpolygon"
                            and ann["geometry"]["mvertices"]
                        ):
                            # MultiPolygon
                            if not isnan(ann["geometry"]["mvertices"][0][0]):
                                denorm = [
                                    denormalize(poly, f["height"], f["width"])
                                    for poly in ann["geometry"]["mvertices"]
                                ]
                                rles = mask_api.frPyObjects(
                                    denorm, f["height"], f["width"]
                                )
                                mask = mask_api.merge(rles)
                        elif (
                            ann["geometry"]["type"] == "rectangle"
                            and ann["geometry"]["vertices"]
                        ):  # BBox
                            if not isnan(ann["geometry"]["vertices"][0]):
                                denorm = denormalize(
                                    [ann["geometry"]["vertices"]],
                                    f["height"],
                                    f["width"],
                                )
                                bbox = xyxy_to_xywh(denorm)
                        elif (
                            ann["geometry"]["type"] == "graph"
                            and ann["geometry"]["vertices"]
                        ):  # Keypoints
                            print("Keypoints are not implemented yet")
                        else:
                            # print('Unknown geometry', ann['geometry']['type'])  # log can be annoying if many...
                            pass
                    else:
                        # Ca peut etre un mask, ou 3d, trackink... etc.
                        print("No geometry?")

                    row["objects"].append(
                        arrow_types.ObjectAnnotation(
                            id=str(ann["id"]),
                            view_id=f["viewId"],
                            bbox=bbox,
                            mask=mask,
                            is_group_of=bool(ann["iscrowd"])
                            if "iscrowd" in ann
                            else None,
                            category_id=category_ids[ann["category"]],
                            category_name=ann["category"],
                        ).dict()
                    )

            # Return row
            yield row
