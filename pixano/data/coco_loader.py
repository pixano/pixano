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

import os

from PIL import Image
from pycocotools.coco import COCO

from pixano import transforms
from pixano.core import arrow_types

from .data_loader import DataLoader


class CocoLoader(DataLoader):
    """COCO Data Loader

    Attributes:
        coco (COCO): COCO dataset
        info (dict): Dataset info
        img_ids (list[int]): Image IDs
        iter_img_ids (iter): Image IDs iterable
        idx (int): Index
    """

    def __init__(self, workspace: str, ann_file: str, img_path: str):
        """Initialize COCO Data Loader

        Args:
            workspace (str): Data path
            ann_file (str): Annotations path
            img_path (str): Images path
        """

        annf = os.path.join(workspace, ann_file)

        # initialize COCO api for instance annotations
        self.coco = COCO(annf)

        self.img_ids = self.coco.getImgIds()
        self.img_ids.sort()
        self.info = self.coco.dataset["info"]
        self.info["annotation_file"] = annf
        self.info["images_path"] = os.path.join(workspace, img_path)
        self.info["nb_images"] = len(self.img_ids)

        # make img_ids iterable
        self.iter_img_ids = iter(self.img_ids)
        self.idx = 0

    def load_ann(self, id: int, width: int, height: int) -> list[dict]:
        """Load COCO annotations

        Args:
            id (int): image id
            width (int): image width, for normalization
            height (int): image height, for normalization

        Returns:
            list[dict]: Annotation data
        """

        ann_ids = self.coco.getAnnIds(id)
        anns = self.coco.loadAnns(ids=ann_ids)
        objects = []
        for ann in anns:
            bbox = None
            if ann["bbox"]:
                bbox = transforms.normalize(ann["bbox"], width, height)
            rle = None
            if ann["segmentation"]:
                rle = self.coco.annToRLE(ann)

            # TMP to check
            if isinstance(rle, list) and len(rle) > 1:
                print("WARNING - MULTI RLE SPOTTED !!", len(rle), rle)

            objects.append(
                arrow_types.ObjectAnnotation(
                    id=str(ann["id"]),
                    view_id="image",
                    is_group_of=bool(ann["iscrowd"]),
                    category_id=ann["category_id"],
                    category_name=self.coco.loadCats(ann["category_id"])[0]["name"],
                    bbox=bbox,
                    mask=rle,
                ).dict()
            )

        # print("OBJTYPE:", type_spec(objects))
        return objects

    def __iter__(self):
        self.idx = 0
        return self

    def __next__(self):
        id = next(self.iter_img_ids)
        ex = self.coco.loadImgs(ids=id)[0]
        image = Image.open(os.path.join(self.info["images_path"], ex["file_name"]))
        anns = self.load_ann(id, image.width, image.height)

        # thumbnail -- after load_ann else image.width/.height are thumbnail height/width
        image.thumbnail((128, 128))
        image_thumb = transforms.image_to_binary(image, "JPEG")

        # tmp, previous col names for now
        row = {
            "id": str(id),
            "image": {
                "uri": ex["file_name"],
                "bytes": None,
                "preview_bytes": image_thumb,
            },
            "image.width": image.width,
            "image.height": image.height,
            "objects": anns,
        }

        return row
