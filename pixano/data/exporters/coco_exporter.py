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

from tqdm.auto import tqdm

from pixano.core import Image
from pixano.data.exporters.exporter import Exporter


class COCOExporter(Exporter):
    """Exporter class for COCO instances dataset

    Attributes:
    dataset (Dataset): Dataset to export
    """

    def export_dataset(
        self,
        export_dir: Path,
        splits: list[str] = None,
        objects_sources: list[str] = None,
        copy: bool = True,
    ):
        """Export dataset back to original format

        Args:
            export_dir (Path): Export directory
            splits (list[str], optional): Dataset splits to export, all if None. Defaults to None.
            objects_sources (list[str], optional): Objects sources to export, all if None. Defaults to None.
            copy (bool, optional): True to copy files to export directory. Defaults to True.
        """

        # Load tables
        ds_tables = self.dataset.open_tables()

        # If no splits provided, select all splits
        if not splits:
            splits = self.dataset.info.splits
            # If no splits, there is nothing to export
            if not splits:
                raise ValueError("Dataset has no splits to export.")

        # If no object sources provided, select all object tables
        if not objects_sources:
            objects_sources = list(ds_tables["objects"].keys())
            # If no object tables, there is nothing to export
            if not objects_sources:
                raise ValueError("Dataset has no objects tables to export.")

        # Create export directory
        ann_dir = export_dir / f"annotations [{', '.join(objects_sources)}]"
        ann_dir.mkdir(parents=True, exist_ok=True)

        # Iterate on splits
        with tqdm(desc="Processing dataset", total=self.dataset.num_rows) as progress:
            for split in splits:
                # Create COCO json
                coco_json = {
                    "info": {
                        "description": self.dataset.info.name,
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
                    "categories": [
                        cat.model_dump() for cat in self.dataset.info.categories
                    ],
                }
                category_ids = [cat.id for cat in self.dataset.info.categories]
                batch_size = 1024

                for i in range(ceil(self.dataset.num_rows / batch_size)):
                    # Load items
                    offset = i * batch_size
                    limit = min(self.dataset.num_rows, offset + batch_size)
                    items = self.dataset.load_items(limit, offset)

                    # Iterate on items
                    for item in items:
                        # Filter on split
                        if item.split in splits:
                            # Export images
                            images: dict[str, Image] = {}
                            for view in item.views.values():
                                if view.type == "image":
                                    # Reformat URI for export
                                    uri = (
                                        view.uri.replace(
                                            f"data/{self.dataset.path.name}/media/", ""
                                        )
                                        if urlparse(view.uri).scheme == ""
                                        else view.uri
                                    )
                                    # Create image from URI
                                    images[view.id] = Image(
                                        uri=uri,
                                        uri_prefix=self.dataset.media_dir.absolute().as_uri(),
                                    )
                                    # Append image info
                                    coco_json["images"].append(
                                        {
                                            "license": 1,
                                            "coco_url": images[view.id].uri,
                                            "file_name": images[view.id].file_name,
                                            "height": images[view.id].height,
                                            "width": images[view.id].width,
                                            "id": item.id,
                                        }
                                    )

                            # Export objects
                            item = self.dataset.load_item(item.id, load_objects=True)
                            for obj in item.objects.values():
                                # Filter by views and object sources
                                if (
                                    obj.view_id in images
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
                                        "id": obj.features["category_id"].value
                                        if "category_id" in obj.features
                                        else None,
                                        "name": obj.features["category_name"].value
                                        if "category_name" in obj.features
                                        else None,
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
                with open(
                    ann_dir / f"instances_{split}.json", "w", encoding="utf-8"
                ) as f:
                    json.dump(coco_json, f)

        # Copy media directory
        if copy:
            if (
                self.dataset.media_dir.exists()
                and self.dataset.media_dir != export_dir / "media"
            ):
                shutil.copytree(
                    self.dataset.media_dir, export_dir / "media", dirs_exist_ok=True
                )
