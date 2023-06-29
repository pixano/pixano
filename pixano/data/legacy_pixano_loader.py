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

import datetime
import json
import os
from math import isnan
from pycocotools import mask as mask_api
from collections import defaultdict
from collections.abc import Generator
from pathlib import Path
from urllib.parse import urlparse
from io import BytesIO
from PIL import Image

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm.auto import tqdm

from pixano.core import DatasetInfo, arrow_types
from pixano.transforms import (
    # normalize,
    denormalize,
    # encode_rle,
    image_to_thumbnail,
    natural_key,
    rle_to_urle,
    xyxy_to_xywh
)

from .data_loader import DataLoader


class LegacyPixanoLoader(DataLoader):
    """Data Loader class for Pixano legacy annotation format instances dataset

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
        views: list[str],
        json_files: dict[str, str],
        splits: list[str],
    ):
        """Initialize Pixano Legacy Loader

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
        """
        self.json_files = json_files
        self.views = views

        # Initialize Data Loader
        super().__init__(name, description, splits, [pa.field(view, arrow_types.ImageType()) for view in views])

    def import_row(
        self,
        input_dirs: dict[str, Path],  # contain "workspace"
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
        print("eze")

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
                for im in sorted(pix_json["data"]["children"], key=lambda x: x["timestamp"]):

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

                    feats[str(im["timestamp"])].append({
                        "viewId": view,
                        "width": im_w,
                        "height": im_h,
                        "im_thumb": im_thumb,
                        "im_uri": (
                            f"image/{split}/{im_path.name}"
                            if portable
                            else im_path.absolute().as_uri()
                        ),
                        "anns": annotations[str(im["timestamp"])]
                    })

        for timestamp in feats:
            # Fill row with ID, image
            row = {
                "id": timestamp,
                "objects": [],
                "split": split,
            }
            for f in feats[timestamp]:
                row[f['viewId']] = arrow_types.Image(f['im_uri'], None, f['im_thumb']).to_dict()

                # Fill row with list of image annotations
                for ann in f['anns']:
                    # collect categories to build category ids
                    if ann["category"] not in category_ids:
                        category_ids[ann["category"]] = len(category_ids)

                    bbox = [0.0, 0.0, 0.0, 0.0]
                    mask = None

                    if "geometry" in ann:
                        if (ann["geometry"]["type"] == "polygon" and ann["geometry"]["vertices"]):
                            # Polygon
                            # we have normalized coords, we must denorm before making RLE
                            if not isnan(ann["geometry"]["vertices"][0]):
                                if len(ann["geometry"]["vertices"]) > 4:
                                    denorm = denormalize(ann["geometry"]["vertices"], f['height'], f['width'])
                                    rles = mask_api.frPyObjects([denorm], f['height'], f['width'])
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
                                    denormalize(poly, f['height'], f['width'])
                                    for poly in ann["geometry"]["mvertices"]
                                ]
                                rles = mask_api.frPyObjects(denorm, f['height'], f['width'])
                                mask = mask_api.merge(rles)
                        elif (
                            ann["geometry"]["type"] == "rectangle"
                            and ann["geometry"]["vertices"]
                        ):  # BBox
                            if not isnan(ann["geometry"]["vertices"][0]):
                                denorm = denormalize([ann["geometry"]["vertices"]], f['height'], f['width'])
                                bbox = xyxy_to_xywh(denorm)
                        elif (
                            ann["geometry"]["type"] == "graph" and ann["geometry"]["vertices"]
                        ):  # Keypoints
                            print("Keypoints are not implemented yet")
                        else:
                            # print('Unknown geometry', ann['geometry']['type'])  # log can be annoying if many...
                            pass
                    else:
                        print("No geometry?")  # Ca peut etre un mask, ou 3d, trackink... etc.

                    row['objects'].append(arrow_types.ObjectAnnotation(
                            id=str(ann["id"]),
                            view_id=f['viewId'],
                            bbox=bbox,
                            mask=mask,
                            is_group_of=bool(ann["iscrowd"]) if "iscrowd" in ann else None,
                            category_id=category_ids[ann["category"]],
                            category_name=ann["category"],
                        ).dict())

            # Return row
            yield row

    def export_dataset(self, input_dir: Path, export_dir: Path):
        """Export dataset back to original format

        Args:
            input_dir (Path): Input directory
            export_dir (Path): Export directory
        """

        # Load spec.json
        input_info = DatasetInfo.parse_file(input_dir / "spec.json")

        # Create export directory
        export_dir.mkdir(parents=True, exist_ok=True)

        # Create URI prefix
        media_dir = input_dir / "media"
        uri_prefix = media_dir.absolute().as_uri()

        # If no splits provided, select all splits
        if not self.splits:
            splits = [s.name for s in os.scandir(input_dir / "db") if s.is_dir()]
        # Else, if splits provided, check if they exist
        else:
            splits = [f"split={s}" for s in self.splits if not s.startswith("split=")]
            for split in splits:
                split_dir = input_dir / "db" / split
                if not Path.exists(split_dir):
                    raise Exception(f"{split_dir} does not exist.")
                if not any(split_dir.iterdir()):
                    raise Exception(f"{split_dir} is empty.")

        # Iterate on splits
        for split in splits:
            # List split files
            files = (input_dir / "db" / split).glob("*.parquet")
            files = sorted(files, key=lambda x: natural_key(x.name))
            split_name = split.replace("split=", "")

            # Create COCO json
            coco_json = {
                "info": {
                    "description": input_info.name,
                    "url": "N/A",
                    "version": f"v{datetime.datetime.now().strftime('%y%m%d.%H%M%S')}",
                    "year": datetime.date.today().year,
                    "contributor": "Exported from Pixano",
                    "date_created": datetime.date.today().isoformat(),
                },
                "licences": [
                    {
                        "url": "N/A",
                        "id": 1,
                        "name": "Unknown",
                    },
                ],
                "images": [],
                "annotations": [],
                "categories": [],
            }

            # Iterate on files
            for file in tqdm(files, desc=f"Processing {split_name} split", position=0):
                # Load file into rows
                table = pq.read_table(file)
                rows = table.to_batches(max_chunksize=1)
                seen_category_ids = []

                # Iterate on rows
                for row in tqdm(
                    rows,
                    desc=f"Processsing {file.name}",
                    total=table.num_rows,
                    position=1,
                ):
                    for field in self.schema:
                        # If column has images
                        if arrow_types.is_image_type(field.type):
                            # Open image
                            im = row[field.name][0].as_py(uri_prefix)
                            im_w, im_h = im.size
                            # Append image info
                            coco_json["images"].append(
                                {
                                    "license": 1,
                                    "file_name": im.uri,
                                    "height": im_h,
                                    "width": im_w,
                                    "id": row["id"][0].as_py(),
                                }
                            )
                        # If column has annotations
                        # TODO: Change to checking type when ObjectAnnotationType is rebuilt
                        elif field.name == "objects":
                            row_anns = row["objects"][0].as_py()
                            for row_ann in row_anns:
                                # Append annotation
                                # TODO: Find solution for bbox denormalization when no masks
                                coco_json["annotations"].append(
                                    {
                                        "segmentation": rle_to_urle(row_ann["mask"]),
                                        "area": row_ann["area"],
                                        "iscrowd": 0,
                                        "image_id": row["id"][0].as_py(),
                                        "bbox": denormalize(
                                            row_ann["bbox"], *row_ann["mask"]["size"]
                                        ),
                                        "category_id": row_ann["category_id"],
                                        "category_name": row_ann["category_name"],
                                        "id": row_ann["id"],
                                    }
                                )
                                # Append category if not seen yet
                                if row_ann["category_id"] not in seen_category_ids:
                                    coco_json["categories"].append(
                                        {
                                            "supercategory": "N/A",
                                            "id": row_ann["category_id"],
                                            "name": row_ann["category_name"],
                                        },
                                    )
                                    seen_category_ids.append(row_ann["category_id"])

            # Sort categories
            coco_json["categories"] = sorted(
                coco_json["categories"], key=lambda c: c["id"]
            )

            # Save COCO json
            with open(export_dir / f"instances_{split_name}.json", "w") as f:
                json.dump(coco_json, f)
