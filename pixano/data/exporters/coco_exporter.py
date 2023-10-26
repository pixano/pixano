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
        portable: bool = False,
    ):
        """Export dataset back to original format

        Args:
            input_dir (Path): Input directory
            export_dir (Path): Export directory
            splits (list[str], optional): Dataset splits to export, all if None. Defaults to None.
            objects_sources (list[str], optional): Objects sources to export, all if None. Defaults to None.
            portable (bool, optional): True to copy or download files to export directory and use relative paths. Defaults to False.
        """

        # Create URI prefix
        media_dir = input_dir / "media"
        uri_prefix = media_dir.absolute().as_uri()
        export_uri_prefix = (export_dir / "media").absolute().as_uri()

        # Load dataset
        dataset = Dataset(input_dir)
        ds = dataset.connect()
        main_table: lancedb.db.LanceTable = ds.open_table("db")

        image_table: dict[str, lancedb.db.LanceTable]
        image_field_names = []
        if "media" in dataset.info.tables:
            for md_info in dataset.info.tables["media"]:
                if md_info["name"] == "image":
                    image_table = ds.open_table(md_info["name"])
                    image_field_names.extend(
                        [
                            field_name
                            for field_name, field_type in md_info["fields"].items()
                            if field_type == "image"
                        ]
                    )

        obj_tables: dict[str, lancedb.db.LanceTable] = {}
        if "objects" in dataset.info.tables:
            for obj_info in dataset.info.tables["objects"]:
                # If no objects tables provided, select all objects tables
                if not objects_sources or (
                    objects_sources and obj_info["name"] in objects_sources
                ):
                    try:
                        obj_tables[obj_info["source"]] = ds.open_table(obj_info["name"])
                    except FileNotFoundError as e:
                        raise FileNotFoundError(f"Objects table not found: {e}") from e
        else:
            raise Exception("No objects table to export")

        # Create export directory
        ann_dir = export_dir / f"annotations [{', '.join(list(obj_tables.keys()))}]"
        ann_dir.mkdir(parents=True, exist_ok=True)

        # If no splits provided, select all splits
        if not splits:
            splits = dataset.info.splits

        # Iterate on splits
        with tqdm(desc="Processing dataset", total=len(main_table)) as progress:
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
                seen_category_ids = []
                batch_size = 1024

                for i in range(ceil(len(main_table) / batch_size)):
                    # Load rows
                    offset = i * batch_size
                    limit = min(len(main_table), offset + batch_size)
                    pyarrow_table = main_table.to_lance()
                    pyarrow_table = duckdb.query(
                        f"SELECT * FROM pyarrow_table ORDER BY len(id), id LIMIT {limit} OFFSET {offset}"
                    ).to_arrow_table()
                    pyarrow_image_table = image_table.to_lance().to_table(
                        limit=limit, offset=offset
                    )
                    pyarrow_image_table = duckdb.query(
                        f"SELECT * FROM pyarrow_image_table ORDER BY len(id), id LIMIT {limit} OFFSET {offset}"
                    ).to_arrow_table()
                    pyarrow_table = duckdb.query(
                        "SELECT * FROM pyarrow_table LEFT JOIN pyarrow_image_table USING (id) ORDER BY len(id), id"
                    ).to_arrow_table()
                    # Filter split
                    if splits:
                        pyarrow_table = duckdb.query(
                            f"SELECT * FROM pyarrow_table WHERE split in ('{split}')"
                        ).to_arrow_table()

                    # Iterate on rows
                    for row_id in range(pyarrow_table.num_rows):
                        row = pyarrow_table.take([row_id]).to_pylist()[0]
                        # Export images
                        ims = {}
                        for field_name in image_field_names:
                            # Open image
                            ims[field_name] = Image.from_dict(row[field_name])
                            ims[field_name].uri_prefix = (
                                export_uri_prefix if portable else uri_prefix
                            )
                            im_filename = Path(
                                urlparse(ims[field_name].get_uri()).path
                            ).name
                            # Append image info
                            coco_json["images"].append(
                                {
                                    "license": 1,
                                    "coco_url": ims[field_name].get_uri(),
                                    "file_name": im_filename,
                                    "height": ims[field_name].size[1],
                                    "width": ims[field_name].size[0],
                                    "id": row["id"],
                                }
                            )
                        # Export objects
                        objects = {}
                        for obj_source, obj_table in obj_tables.items():
                            media_scanner = obj_table.to_lance().scanner(
                                filter=f"item_id in ('{row['id']}')"
                            )
                            objects[obj_source] = media_scanner.to_table().to_pylist()
                        for obj_source, obj_list in objects.items():
                            for obj in obj_list:
                                if obj["view_id"] in image_field_names:
                                    # Object mask
                                    mask = (
                                        obj["mask"].to_urle() if "mask" in obj else None
                                    )
                                    # Object bounding box
                                    bbox = (
                                        obj["bbox"]
                                        .denormalize(
                                            height=ims[obj["view_id"]].size[1],
                                            width=ims[obj["view_id"]].size[0],
                                        )
                                        .xywh_coords
                                        if "bbox" in obj
                                        else None
                                    )
                                    # Object category
                                    category = (
                                        {
                                            "id": obj["category_id"],
                                            "name": obj["category_name"],
                                        }
                                        if "category_id" in obj
                                        and "category_name" in obj
                                        else None
                                    )
                                    # Add object
                                    coco_json["annotations"].append(
                                        {
                                            "id": obj["id"],
                                            "image_id": row["id"],
                                            "segmentation": mask,
                                            "bbox": bbox,
                                            "area": 0,
                                            "iscrowd": 0,
                                            "category_id": category["id"],
                                            "category_name": category["name"],
                                        }
                                    )
                                    # Append category if not seen yet
                                    if (
                                        category["id"] not in seen_category_ids
                                        and category["name"] is not None
                                    ):
                                        coco_json["categories"].append(
                                            {
                                                "supercategory": "N/A",
                                                "id": category["id"],
                                                "name": category["name"],
                                            },
                                        )
                                        seen_category_ids.append(category["id"])
                        # Update progress bar after processing row
                        progress.update(1)

                # Sort categories
                coco_json["categories"] = sorted(
                    coco_json["categories"], key=lambda c: c["id"]
                )
                # Save COCO format .json file
                with open(ann_dir / f"instances_{split}.json", "w") as f:
                    json.dump(coco_json, f)

        # Copy media directory if portable
        if portable:
            if media_dir.exists():
                if media_dir != export_dir / "media":
                    shutil.copytree(media_dir, export_dir / "media", dirs_exist_ok=True)
            else:
                raise Exception(
                    f"Activated portable option for export but {media_dir} does not exist."
                )
