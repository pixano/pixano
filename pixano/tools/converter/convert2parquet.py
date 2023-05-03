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

import io
import json
import shutil
import uuid
from pathlib import Path

import pyarrow as pa
import pyarrow.dataset as ds
from PIL import Image
from tqdm import tqdm

from pixano.core import arrow_types


def media_copy(
    images_path: Path, filename: str, path: Path, view: str, multiview: bool
):
    """Copy file from source to media directory

    Args:
        images_path (Path): Image path
        filename (str): Image filename
        path (Path): Dataset path
        view (str): View name
        multiview (bool): True if multiview

    Raises:
        Exception: Empty filename
        Exception: File not found
        Exception: File copy error
    """

    # Check provided filename
    if filename is None or len(filename) == 0:
        raise Exception("No uri given")

    # Get file
    file = Path(images_path) / Path(filename)

    # Check if file exists
    if not file.is_file():
        # Because of inconsistent old Pixano format, try this first
        file = Path(images_path) / Path(filename).name
        if not file.is_file():
            raise Exception(f"File not found (path: {images_path}, filename: {file})")

    # Media path
    media_path = path / "media"
    if multiview:
        media_path = media_path / view
    media_path.mkdir(parents=True, exist_ok=True)

    # Copy
    try:
        shutil.copy(file, media_path / file.name)
    except Exception as e:
        raise Exception(
            f"Image copy error: {e} (src: {file}, dst: {str(media_path / file.name)})"
        )


def generate_spec(
    split_info: dict,
    path: Path,
    name: str,
    description: str = "",
    limits: list[int] = [],
):
    """Generate spec.json

    Args:
        split_info (dict): Generator for each split and views
        path (Path): Dataset path
        name (str): Dataset name
        description (str, optional): Dataset description. Defaults to "".
        limits (list[int], optional): Image limits per split. Defaults to [].

    Raises:
        Exception: File creation error
    """

    spec = {}
    spec["id"] = uuid.uuid4().hex
    spec["name"] = str(name)
    spec["description"] = description if description else str(name)

    if limits:
        spec["num_elements"] = sum(limits)
    else:
        num_elements = 0
        for split in split_info:
            if hasattr(split_info[split], "info"):
                num_elements += split_info[split].info["nb_images"]
            else:
                counts = [d.info["nb_images"] for d in split_info[split].values()]
                if counts.count(counts[0]) != len(counts):
                    raise Exception(
                        "Images counts are not consistent across views:"
                        + ", ".join(str(k) for k in split_info[split])
                    )
                num_elements += counts[0]
        spec["num_elements"] = num_elements

    try:
        with open(path / "spec.json", "w") as f:
            json.dump(spec, f)
            print("File " + str(path) + "/spec.json written")
    except IOError as err:
        raise Exception(f"Error creating spec.json file: {err}")


def generate_parquet(
    split_info: dict, path: Path, schema: pa.schema = None, limits: list[int] = []
):
    """Generate parquet file

    Args:
        split_info (dict): Generators for each split and view
        path (Path): Dataset path
        schema (pa.schema, optional): Dataset PyArrow schema. Defaults to None.
        limits (list[int], optional): Image limits per split. Defaults to None.
    """

    db_path = path / "db"
    db_path.mkdir(parents=True, exist_ok=True)

    for i, split in enumerate(split_info):
        split_limit = limits[i] if limits else 0
        lfeat = []
        if hasattr(split_info[split], "info"):
            # SingleView
            multiview = False
            datas = [split_info[split]]
            views = [
                "image"
            ]  # WARNING: We should try to get "only view" name ("image" by default, but could be "rgb")
            nb_images = datas[0].info["nb_images"]
        else:
            # MultiView: one view per generator
            multiview = True
            datas = split_info[split].values()
            views = list(split_info[split].keys())
            counts = [d.info["nb_images"] for d in datas]
            if counts.count(counts[0]) != len(counts):
                raise Exception(
                    "Images counts are not consistent across views:"
                    + ", ".join(str(v) for v in views)
                )
            nb_images = counts[0]

        try:
            if nb_images:
                if split_limit is 0 or split_limit > nb_images:
                    split_limit = nb_images
                    print(
                        f"Reading data for whole dataset (split:{split}) of {split_limit} items."
                    )
                else:
                    print(
                        f"Reading data for subset dataset (split:{split}) of first {split_limit}/{nb_images} items."
                    )
                for i in tqdm(range(split_limit)):
                    feat = {}
                    for i, data in enumerate(datas):
                        view_feat = next(data)
                        if "uri" in view_feat[views[i]]:
                            media_copy(
                                data.info["images_path"],
                                view_feat[views[i]]["uri"],
                                path,
                                views[i],
                                multiview,
                            )

                        if "objects" in feat:
                            # extend annotations
                            view_feat["objects"].extend(feat["objects"])
                        feat.update(view_feat)
                    feat["split"] = split
                    lfeat.append(feat)
            else:
                # TODO not consistent anymore with if case...
                print(
                    "Generating parquet file. Number of image unknown. Prints ./* every 10/100 items."
                )
                i = 0
                # TODO multiview
                while (feat := next(data)) and (split_limit < 0 or i < split_limit):
                    feat["split"] = split
                    lfeat.append(feat)
                    i = 1 + i
                    if i % 100 == 0:
                        print("*", end="", flush=True)
                    else:
                        if i % 10 == 0:
                            print(".", end="", flush=True)
                    if i == split_limit:
                        raise StopIteration
        except StopIteration:
            print("Done!")

        if schema is None:
            fields = [
                pa.field("id", pa.string()),
                pa.field("objects", pa.list_(arrow_types.ObjectAnnotationType())),
                pa.field("split", pa.string()),
            ]
            for view in views:
                fields.append(pa.field(view + ".width", pa.int32(), nullable=True))
                fields.append(pa.field(view + ".height", pa.int32(), nullable=True))
                fields.append(pa.field(view, arrow_types.ImageType()))

            schema = pa.schema(fields)

        # Transpose lfeats (list of rows to cols (list of col))
        cols = {k: [dic[k] for dic in lfeat] for k in lfeat[0]}

        arrays = []
        for field in schema:
            if field.name in cols:
                col = cols[field.name]
                arr = arrow_types.convert_field(field.name, field.type, col)
                arrays.append(arr)
            else:
                print("Incorrect field:", field.name)

        table = pa.Table.from_arrays(arrays=arrays, schema=schema)

        ds.write_dataset(
            data=table,
            base_dir=db_path / split,
            basename_template=f"part-{{i}}.parquet",
            format="parquet",
            max_rows_per_file=2048,
            max_rows_per_group=2048,
            existing_data_behavior="overwrite_or_ignore",
        )

        print("Parquet written in " + str(db_path / split))

    # PREVIEW - create file "preview.png"
    # get 6 first (todo? random) images
    # get image field names for preview
    image_fields = []
    for f in schema:
        if arrow_types.is_image_type(f.type):
            image_fields.append(f.name)

    if len(image_fields) > 0:
        tile_w = 64
        tile_h = 64
        preview = Image.new("RGB", (3 * tile_w, 2 * tile_h))
        for i, f in enumerate(lfeat[:6]):
            im = f[image_fields[i % len(image_fields)]]
            image = Image.open(io.BytesIO(im["preview_bytes"]))
            preview.paste(image, ((i % 3) * tile_w, (int(i / 3) % 2) * tile_h))
        preview.save(path / "preview.png")


def convert(
    split_info: dict,
    library_path: str,
    name: str,
    schema: pa.schema = None,
    limits: list[int] = [],
    description: str = "",
):
    """Create Pixano parquet dataset from generator(s)

    Args:
        split_info (dict): Generators for each split and view
        library_path (str): Dataset library path
        name (str): Dataset name
        schema (pa.schema, optional): Dataset PyArrow schema. Defaults to None.
        limits (list[int], optional): Image limits per split. Defaults to [].
        description (str, optional): Dataset description. Defaults to "".
    """

    path = Path(library_path) / name
    generate_parquet(split_info, path, schema, limits)
    generate_spec(split_info, path, name, description, limits)
