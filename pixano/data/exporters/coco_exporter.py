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
import shutil
from math import ceil
from pathlib import Path
from urllib.parse import urlparse

import duckdb
import lancedb
from tqdm.auto import tqdm

from pixano.core import Image
from pixano.data import Dataset
from pixano.data.exporters.exporter import Exporter


class COCOExporter(Exporter):
    """Exporter class for COCO instances dataset"""

    def export_dataset(
        self,
        input_dir: Path,
        export_dir: Path,
        splits: list[str] = None,
        objects_sources: list[str] = None,
        copy: bool = True,
    ):
        """Export dataset back to original format

        Args:
            input_dir (Path): Input directory
            export_dir (Path): Export directory
            splits (list[str], optional): Dataset splits to export, all if None. Defaults to None.
            objects_sources (list[str], optional): Objects sources to export, all if None. Defaults to None.
            copy (bool, optional): True to copy files to export directory. Defaults to True.
        """

        # Load dataset
        dataset = Dataset(input_dir)

        # Load tables
        ds_tables = dataset.open_tables()

        # If no splits provided, select all splits
        if not splits:
            splits = dataset.info.splits
            # If no splits, there is nothing to export
            if not splits:
                raise Exception("Dataset has no splits to export.")

        # If no object sources provided, select all object tables
        if not objects_sources:
            objects_sources = list(ds_tables["objects"].keys())
            # If no object tables, there is nothing to export
            if not objects_sources:
                raise Exception("Dataset has no objects tables to export.")

        # Create export directory
        ann_dir = export_dir / f"annotations [{', '.join(objects_sources)}]"
        ann_dir.mkdir(parents=True, exist_ok=True)

        # Iterate on splits
        with tqdm(desc="Processing dataset", total=dataset.num_rows) as progress:
            for split in splits:
                # Create COCO json
                coco_json = {
                    "info": {
                        "description": dataset.info.name,
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
                category_ids = []
                batch_size = 1024

                for i in range(ceil(dataset.num_rows / batch_size)):
                    # Load items
                    offset = i * batch_size
                    limit = min(dataset.num_rows, offset + batch_size)
                    items = dataset.load_items(limit, offset)

                    # Iterate on items
                    for item in items:
                        # Filter on split
                        if item.split in splits:
                            # Export images
                            images: dict[str, Image] = {}
                            for image_view in item.image:
                                # Reformat URI for export
                                uri = (
                                    image_view.uri.replace(
                                        f"data/{dataset.path.name}/media/", ""
                                    )
                                    if urlparse(image_view.uri).scheme == ""
                                    else image_view.uri
                                )
                                # Create image from URI
                                images[image_view.id] = Image(
                                    uri=uri,
                                    uri_prefix=dataset.media_dir.absolute().as_uri(),
                                )
                                # Append image info
                                coco_json["images"].append(
                                    {
                                        "license": 1,
                                        "coco_url": images[image_view.id].uri,
                                        "file_name": images[image_view.id].file_name,
                                        "height": images[image_view.id].height,
                                        "width": images[image_view.id].width,
                                        "id": item.id,
                                    }
                                )

                            # Export objects
                            item = dataset.load_item(item.id, load_objects=True)
                            for obj in item.objects:
                                # Filter by views and object sources
                                if (
                                    obj.view_id in images.keys()
                                    and obj.source_id in objects_sources
                                ):
                                    # Bounding box
                                    bbox = (
                                        obj.bbox.to_pyarrow()
                                        .denormalize(
                                            height=images[obj.view_id].height,
                                            width=images[obj.view_id].width,
                                        )
                                        .xywh_coords
                                        if obj.bbox
                                        else None
                                    )
                                    # Mask
                                    mask = (
                                        obj.mask.to_pyarrow().to_urle()
                                        if obj.mask
                                        else None
                                    )
                                    # Category
                                    category = {
                                        "id": obj.find_feature("category_id"),
                                        "name": obj.find_feature("category_name"),
                                    }
                                    # Add object
                                    coco_json["annotations"].append(
                                        {
                                            "id": obj.id,
                                            "image_id": item.id,
                                            "segmentation": mask,
                                            "bbox": bbox,
                                            "area": 0,
                                            "iscrowd": 0,
                                            "category_id": category["id"],
                                            "category_name": category["name"],
                                        }
                                    )
                                    # Add category if not seen yet
                                    if (
                                        category["id"] not in category_ids
                                        and category["name"] is not None
                                    ):
                                        category_ids.append(category["id"])
                                        coco_json["categories"].append(
                                            {
                                                "supercategory": "N/A",
                                                "id": category["id"],
                                                "name": category["name"],
                                            },
                                        )

                            # Update progress bar after processing row
                            progress.update(1)

                # Sort categories
                coco_json["categories"] = sorted(
                    coco_json["categories"], key=lambda c: c["id"]
                )
                # Save COCO format .json file
                with open(ann_dir / f"instances_{split}.json", "w") as f:
                    json.dump(coco_json, f)

        # Copy media directory
        if copy:
            if dataset.media_dir.exists() and dataset.media_dir != export_dir / "media":
                shutil.copytree(
                    dataset.media_dir, export_dir / "media", dirs_exist_ok=True
                )
