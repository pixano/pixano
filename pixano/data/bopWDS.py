from typing import Iterator
import lance

import bop_toolkit_lib.dataset.bop_webdataset as btk

import webdataset as wds

import json
import numpy as np
import time
from pathlib import Path
from PIL import Image as pilImage
import pyarrow as pa

from pixano.core import *
from pixano.data.importer import Importer
from pixano.core.arrow_types import *


from lance import LanceDataset
from pixano.core.dataset import DatasetInfo
from pixano.transforms.image import image_to_thumbnail, image_to_binary


class BopWDS_Importer(Importer):
    def __init__(
        self,
        shard_split: dict[str, list[str]],
    ):
        
        self.shard_split = shard_split
        
        self.features_dict = {
            "id": "str",
            "rgb": "Image",
            "depth": "DepthImage",
            "camera": "Camera",
            "category_id": "[int]",
            "objects_id": "[str]",
            "masks": "[CompressedRLE]",
            "gt": "[Pose]",
            "gt_info": "[GtInfo]",
            "split": "str",
        }

        super().__init__("BopWDS", "Bop dataset as webdataset format", self.features)

    @property
    def features(self) -> Features:
        return Features.from_string_dict(self.features_dict)

    def import_row(
        self,
        input_dirs: str | Path
    ) -> Iterator:
        # split dataset
        for split, shard_list in self.shard_split.items():
            _wds_pipeline = wds.DataPipeline(
                wds.SimpleShardList(shard_list), wds.tarfile_to_samples()
            )

            # extract row of each split
            for n, row in enumerate(_wds_pipeline):
                if True:
                    sample = btk.decode_sample(
                        row,
                        decode_camera=True,
                        decode_rgb=True,
                        decode_gray=False,
                        decode_depth=True,
                        decode_gt=True,
                        decode_gt_info=True,
                        decode_mask_visib=False,
                        decode_mask=False,
                        rgb_suffix=".png",
                    )

                    # id
                    id = row["__key__"]

                    scene, image = id.split("_")
                    coco_json_path = f"{input_dirs}/{split}/{scene}/scene_gt_coco.json"

                    # rgb
                    im_pil = pilImage.fromarray(sample["im_rgb"])

                    im_pil = image_to_binary(im_pil, format="JPEG")

                    preview = image_to_thumbnail(im_pil)
                    rgb = Image(f"", im_pil, preview)
                    rgbs = ImageType.Array.from_list([rgb])

                    # depth
                    depths = DepthImageType.Array.from_list(
                        [
                            DepthImage(
                                depth_map=sample["im_depth"],
                                shape=sample["im_depth"].shape,
                            )
                        ]
                    )
                    # camera
                    cameras = CameraType.Array.from_list(
                        [Camera.from_dict(sample["camera"])]
                    )

                    # Objects
                    nb_object = len(sample["gt"])
                    # category
                    category_id = [
                        sample["gt"][i]["object_id"] for i in range(nb_object)
                    ]
                    category_id_arr = pa.array([category_id])

                    # pose
                    gt = [
                        Pose(
                            sample["gt"][i]["cam_R_m2c"].flatten(),
                            sample["gt"][i]["cam_t_m2c"].flatten(),
                        )
                        for i in range(nb_object)
                    ]
                    gt_arr = PoseType.Array.from_lists([gt])

                    # gt_info
                    gt_infos = [
                        GtInfo.from_dict(
                            {
                                **sample["gt_info"][i],
                                "bbox_obj": BBox.from_xywh(
                                    sample["gt_info"][i]["bbox_obj"]
                                ),
                                "bbox_visib": BBox.from_xywh(
                                    sample["gt_info"][i]["bbox_visib"]
                                ),
                            }
                        )
                        for i in range(nb_object)
                    ]
                    gt_infos_arr = GtInfoType.Array.from_lists([gt_infos])

                    # objects_ids and masks
                    with open(coco_json_path, "r") as f:
                        data = json.load(f)

                    object_ids = []
                    masks = []
                    for ann in data["annotations"]:
                        # check if same image key, then annotations are in same order as other object's attribute in coco.json
                        if "000" + ann["image_id"] == id.replace("_", "-"):
                            object_ids.append(ann["id"])
                            masks.append(
                                CompressedRLE.from_urle(
                                    ann["segmentation"],
                                    ann["segmentation"]["size"][0],
                                    ann["segmentation"]["size"][1],
                                )
                            )

                    masks_arr = CompressedRLEType.Array.from_lists([masks])
                    object_ids_arr = pa.array([object_ids])

                    # Struct array
                    struct_arr = pa.StructArray.from_arrays(
                        [
                            pa.array([id]),
                            rgbs,
                            depths,
                            cameras,
                            category_id_arr,
                            object_ids_arr,
                            masks_arr,
                            gt_arr,
                            gt_infos_arr,
                            pa.array([split]),
                        ],
                        fields=self.features.to_fields()
                    )

                    yield pa.RecordBatch.from_struct_array(struct_arr)
