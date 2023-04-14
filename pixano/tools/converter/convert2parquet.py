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


def media_copy(images_path, fname, dest, view, multiview):
    """Copy file from given source to "media" directory

    Args:
        images_path (str | Path): images source path
        fname (str): image file name
        dest (Path): path to dataset
        view (str): view name
        multiview (boolean): true if multiview
    """
    # copy file "view_feat['<view>_path']" in dest/media/<view>
    if fname is None or len(fname) == 0:
        print("No uri !")
        return
    fsrc = Path(images_path) / Path(fname)
    # checks needed because of inconsistent old Pixano format...
    if not fsrc.is_file():
        fsrc = Path(images_path) / Path(fname).name
        if not fsrc.is_file():
            raise f"Unable to find image.\nimage path: {images_path}\nfile: {fsrc}"

    if multiview:
        fdest_path = dest / "media" / view
    else:
        fdest_path = dest / "media"
    if not fdest_path.exists():
        fdest_path.mkdir(parents=True)
    try:
        shutil.copy(fsrc, fdest_path / fsrc.name)
    except Exception as e:
        print("Image copy error", e)
        print("    src", fsrc)
        print("    dst", str(fdest_path / fsrc.name))


def generate_spec(split_info, dest: Path, name, description=None, stop=None):
    """genarate spec.json specification file

    Args:
        split_info (dict): dict which contain genrator for each split and views
        dest (Path): path to dataset
        name (str): dataset name
        description(str, optionnal): description of dataset
        stop (list[int], optional): array of limit to number of image, per split
    """
    spec = {}
    spec["id"] = uuid.uuid4().hex
    spec["name"] = str(name)
    spec["description"] = description if description else str(name)

    if stop:
        spec["num_elements"] = sum(stop)
    else:
        nb_images = 0
        for split in split_info:
            if hasattr(split_info[split], "info"):
                nb_images += split_info[split].info["nb_images"]
            else:
                counts = [d.info["nb_images"] for d in split_info[split].values()]
                if counts.count(counts[0]) != len(counts):
                    raise Exception(
                        "Images counts are not consistent across views:"
                        + ", ".join(str(k) for k in split_info[split])
                    )
                nb_images += counts[0]
        spec["num_elements"] = nb_images

    try:
        with open(dest / "spec.json", "w") as f:
            json.dump(spec, f)
            print("File " + str(dest) + "/spec.json written")
    except IOError as err:
        print("Error creating spec.json file:" + err)


def generate_parquet(split_info, dest, schema=None, stop=None):
    """Generate parquet file

    Args:
        split_info (dict): dict which contain genrator for each split and views
        dest (Path): path to dataset
        schema (pyarrow.schema, optionnal): pyarrow schema if custom schema needed
        stop (list[int], optional): array of limit to number of image, per split
    """

    parquet_path = dest / "db"
    if not parquet_path.exists():
        parquet_path.mkdir(parents=True)

    for i, split in enumerate(split_info):
        split_stop = stop[i] if stop else None
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
                if split_stop is None or split_stop > nb_images:
                    split_stop = nb_images
                    print(
                        f"Reading data for whole dataset (split:{split}) of {split_stop} items."
                    )
                else:
                    print(
                        f"Reading data for subset dataset (split:{split}) of first {split_stop}/{nb_images} items."
                    )
                for i in tqdm(range(split_stop)):
                    feat = {}
                    for i, data in enumerate(datas):
                        view_feat = next(data)
                        if "uri" in view_feat[views[i]]:
                            media_copy(
                                data.info["images_path"],
                                view_feat[views[i]]["uri"],
                                dest,
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
                while (feat := next(data)) and (split_stop < 0 or i < split_stop):
                    feat["split"] = split
                    lfeat.append(feat)
                    i = 1 + i
                    if i % 100 == 0:
                        print("*", end="", flush=True)
                    else:
                        if i % 10 == 0:
                            print(".", end="", flush=True)
                    if i == split_stop:
                        raise StopIteration
        except StopIteration:
            print("Done!")

        if not schema:
            sch = [
                pa.field("id", pa.string()),
                pa.field("objects", pa.list_(arrow_types.ObjectAnnotationType())),
                pa.field("split", pa.string()),
            ]
            for view in views:
                sch.append(pa.field(view + ".width", pa.int32(), nullable=True))
                sch.append(pa.field(view + ".height", pa.int32(), nullable=True))
                sch.append(pa.field(view, arrow_types.ImageType()))

            schema = pa.schema(sch)

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
            base_dir=parquet_path / split,
            basename_template=f"part-{{i}}.parquet",
            format="parquet",
            max_rows_per_file=2048,
            max_rows_per_group=2048,
            existing_data_behavior="overwrite_or_ignore",
        )

        print("Parquet written in " + str(parquet_path / split))

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
        preview.save(dest / "preview.png")


def convert(split_info, outpath, name, schema=None, stop=None, description=None):
    """Create Pixano parquet dataset from generator(s)

    Args:
        split_info (dict): dict which contain genrator for each split and views
        outpath (str): destination path, should be path to library
        name (str): dataset name
        schema (pyarrow.schema, optionnal): _description_
        stop (list[int], optional): array of limit to number of image, per split
        description (str, optional): Description of dataset. Defaults to None.
    """
    dataset_path = Path(outpath) / name

    generate_parquet(split_info, dataset_path, schema, stop)
    generate_spec(split_info, dataset_path, name, description, stop)
