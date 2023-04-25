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
import time
from math import isnan
from pathlib import Path

from PIL import Image
from pycocotools import mask as mask_api
from tqdm import tqdm

from pixano import transforms
from pixano.core import arrow_types

from .data_loader import DataLoader


class PixanoLoader(DataLoader):
    """Pixano Data Loader

    Attributes:
        dataset (dict): Dataset
        info (dict): Dataset info
        iter_data (iter): Data iterable
    """

    def __init__(
        self, workspace: str, ann_file: str, img_path: Path = None, view: str = "image"
    ):
        """Initalize COCO Data Loader

        Args:
            workspace (str): Data path
            ann_file (str): Annotation file name
            img_path (Path, optional): Image path. Defaults to None.
            view (str, optional): Image view name. Defaults to "image".
        """

        if ann_file is None:
            print(
                "PixanoLoader: Please provide an annotation file, or use another Loader if no annotations"
            )
            return
        self.info = {}

        # load dataset
        self.dataset = dict()
        print("loading annotations into memory...")
        tic = time.time()
        workspace = Path(workspace)
        with open(workspace / ann_file, "r") as f:
            raw_json = json.load(f)
        assert type(raw_json) == dict, "annotation file format {} not supported".format(
            type(raw_json)
        )
        print("Done (t={:0.2f}s)".format(time.time() - tic))

        # create index
        print("creating index...")
        tic = time.time()
        self.dataset = self.getFeaturesFromJSON(raw_json, workspace, img_path, view)
        self.iter_data = iter(self.dataset)
        print("Done (t={:0.2f}s)".format(time.time() - tic))
        self.info["nb_images"] = len(self.dataset)
        self.info["task"] = raw_json["task_name"]
        self.info["data_type"] = raw_json["data"]["type"]

    # Pixano wrapper
    # Pixano json has "annotations", a list of all annotations (image_id inside)
    # and "data", list of image path and id (timestamp)
    # (path is relative to workspace, and may be wrong: we keep only basename)
    # contains also Pixano task name
    """ For Reference: Pixano "annotations" structure
    class PixanoAnns:
    {
        "annotations": [
            'associated_to': str
            'category': str
            'geometry': {
                'mvertices': list[int]
                'type': str
                'vertices': list[int]
            }
            'id': str
            'options': {
                'occlusion': float
                'truncation': float
            }
            'timestamp': int
        ]
        "data": {
            "children": [
                {
                    "path": "images/cylindric/test/20170320_163113/cam_0/20170320_163113_cam_0_00006300.jpg",
                    "timestamp": 0
                }]
            "path": "images/cylindric/test/20170320_163113/cam_0",
            "type": "sequence_image"
        },
        "task_name": "object2d"
    }
    """

    def getFeaturesFromJSON(
        self, data, workspace: Path, img_path: Path, view: str
    ) -> list[dict]:
        """Get features from Pixano annotation file

        Args:
            data (str): raw json
            workspace (Path): Data path
            img_path (Path): Image path
            view (str): Image view name

        Raises:
            Exception: Image not found

        Returns:
            list[dict]: List of features
        """

        img_list = None
        if img_path is not None:
            self.info["images_path"] = str(workspace / img_path)
            img_list = sorted(list((workspace / img_path / view).glob("*.jpg")))
            if len(img_list) != len(data["data"]["children"]):
                print(
                    f"WARNING: Number ({len(img_list)}) of files in {img_path / view} differ \
                      than number {len(data['data']['children'])} of defined files in annotation file"
                )
                img_list = img_list[: len(data["data"]["children"])]
        else:
            self.info["images_path"] = str(workspace / data["data"]["path"])

        wraped_ds = []
        categories = set()
        # first we create Features with id, filename, width, height
        for idx, file_item in enumerate(tqdm(data["data"]["children"])):
            if img_list is not None:
                image = Image.open(img_list[idx])
                image_filename = str(Path(view) / Path(img_list[idx]).name)
            else:
                # Old Pixano format can be surprising... We need to check how to build file path
                fpath = workspace / data["data"]["path"] / file_item["path"]
                if not fpath.is_file():
                    fpath = (
                        workspace / data["data"]["path"] / Path(file_item["path"]).name
                    )
                    image_filename = fpath.name  # get rid of path in filename
                    if not fpath.is_file():
                        raise Exception("Unable to find image:" + str(fpath))
                image = Image.open(fpath)

            # keep real image size before thumbnailing
            img_w = image.width
            img_h = image.height

            image.thumbnail((128, 128))
            image_thumb = transforms.image_to_binary(image)

            feats = {
                "id": str(file_item["timestamp"]),
                view: {
                    "uri": image_filename,
                    "bytes": None,
                    "preview_bytes": image_thumb,
                },
                view + ".width": img_w,
                view + ".height": img_h,
                "objects": [],
            }
            wraped_ds.append(feats)

        # then we put annotations inside
        for ann in data["annotations"]:
            lfeats = [f for f in wraped_ds if f["id"] == str(ann["timestamp"])]
            feats = lfeats[0]
            w = feats[view + ".width"]
            h = feats[view + ".height"]
            categories.add(ann["category"])
            rle = None
            bbox = [0] * 4  # None  -- should be ok with None, but it's not
            if "geometry" in ann:
                if (
                    ann["geometry"]["type"] == "polygon" and ann["geometry"]["vertices"]
                ):  # Polygon
                    # we have normalized coords, we must denorm before making RLE
                    if not isnan(ann["geometry"]["vertices"][0]):
                        if len(ann["geometry"]["vertices"]) > 4:
                            denorm = transforms.denormalize(
                                ann["geometry"]["vertices"], w, h
                            )
                            rles = mask_api.frPyObjects([denorm], h, w)
                            rle = mask_api.merge(rles)
                        else:
                            print(
                                "Polygon with 2 or less points. Discarded\n",
                                ann["geometry"],
                            )
                elif (
                    ann["geometry"]["type"] == "mpolygon"
                    and ann["geometry"]["mvertices"]
                ):  # MultiPolygon
                    if not isnan(ann["geometry"]["mvertices"][0][0]):
                        denorm = [
                            transforms.denormalize(poly, w, h)
                            for poly in ann["geometry"]["mvertices"]
                        ]
                        rles = mask_api.frPyObjects(denorm, h, w)
                        rle = mask_api.merge(rles)
                elif (
                    ann["geometry"]["type"] == "rectangle"
                    and ann["geometry"]["vertices"]
                ):  # BBox
                    if not isnan(ann["geometry"]["vertices"][0]):
                        denorm = transforms.denormalize(
                            [ann["geometry"]["vertices"]], w, h
                        )
                        bbox = transforms.xyxy_to_xywh(denorm)
                elif (
                    ann["geometry"]["type"] == "graph" and ann["geometry"]["vertices"]
                ):  # Keypoints
                    print("Keypoints are not implemented yet")
                else:
                    # print('Unknown geometry', ann['geometry']['type'])  # log can be annoying if many...
                    pass
            else:
                print("No geometry?")  # Ca peut etre un mask, ou 3d, trackink... etc.

            # TMP to check
            if isinstance(rle, list) and len(rle) > 1:
                print("WARNING - MULTI RLE SPOTTED !!", len(rle), rle)

            feats["objects"].append(
                arrow_types.ObjectAnnotation(
                    id=str(ann["id"]),
                    view_id=view,
                    is_group_of=False,
                    # category_id=  # pas de categoryId, on le crée ensuite
                    category_name=ann["category"],
                    bbox=bbox,
                    mask=rle,
                ).dict()
            )

        # create category id based on existing categories index
        ordered_cat = list(categories)
        ordered_cat.sort()
        dict_cat_idx = dict([(cat, idx) for idx, cat in enumerate(ordered_cat)])
        for feats in wraped_ds:
            for obj in feats["objects"]:
                obj["category_id"] = dict_cat_idx[obj["category_name"]]
        return wraped_ds

    def __iter__(self):
        return self

    def __next__(self):
        return next(self.iter_data)
