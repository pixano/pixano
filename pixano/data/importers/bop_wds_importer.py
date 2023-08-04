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
import os
import sys
from pathlib import Path
from typing import Iterator, Optional

import pyarrow as pa
from PIL import Image as PILImage

from pixano.core import (
    BBox,
    Camera,
    CameraType,
    CompressedRLE,
    CompressedRLEType,
    DepthImage,
    DepthImageType,
    GtInfo,
    GtInfoType,
    Image,
    ImageType,
    Pose,
    PoseType,
)
from pixano.data import Fields
from pixano.data.importers.importer import Importer
from pixano.utils import image_to_binary, image_to_thumbnail


def row_to_array(
    row, split: str, fields: Fields, coco_json_path: Optional[Path | str] = None
) -> pa.StructArray:
    struct_arr = []

    try:
        # Add the path to bop_toolkit
        sys.path.append("/home/maximilien/work/lib/bop_toolkit")
        import bop_toolkit_lib.dataset.bop_webdataset as btk

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

        nb_object = len(sample["gt"])
        keys = fields.to_dict().keys()

        # id
        if "id" in keys:
            id = row["__key__"]
            struct_arr.append(pa.array([id]))

        # rgb
        if "rgb" in keys:
            im_pil = PILImage.fromarray(sample["im_rgb"])
            im_pil = image_to_binary(im_pil, format="JPEG")
            preview = image_to_thumbnail(im_pil)

            rgb = Image(f"", im_pil, preview)
            rgbs = ImageType.Array.from_list([rgb])
            struct_arr.append(rgbs)

        # depth
        if "depth" in keys:
            depths = DepthImageType.Array.from_list(
                [
                    DepthImage(
                        depth_map=sample["im_depth"],
                        shape=sample["im_depth"].shape,
                    )
                ]
            )
            struct_arr.append(depths)

        # camera
        if "camera" in keys:
            cameras = CameraType.Array.from_list([Camera.from_dict(sample["camera"])])
            struct_arr.append(cameras)

        # category
        if "category_id" in keys:
            category_id = [sample["gt"][i]["object_id"] for i in range(nb_object)]
            category_id_arr = pa.array([category_id])
            struct_arr.append(category_id_arr)

        # objects_ids and masks
        if coco_json_path is not None:
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

            struct_arr.append(object_ids_arr)
            struct_arr.append(masks_arr)

        # pose
        if "gt" in keys:
            gt = [
                Pose(
                    sample["gt"][i]["cam_R_m2c"].flatten(),
                    sample["gt"][i]["cam_t_m2c"].flatten(),
                )
                for i in range(nb_object)
            ]
            gt_arr = PoseType.Array.from_lists([gt])
            struct_arr.append(gt_arr)

        # gt_info
        if "gt_info" in keys:
            gt_infos = [
                GtInfo.from_dict(
                    {
                        **sample["gt_info"][i],
                        "bbox_obj": BBox.from_xywh(sample["gt_info"][i]["bbox_obj"]),
                        "bbox_visib": BBox.from_xywh(
                            sample["gt_info"][i]["bbox_visib"]
                        ),
                    }
                )
                for i in range(nb_object)
            ]
            gt_infos_arr = GtInfoType.Array.from_lists([gt_infos])
            struct_arr.append(gt_infos_arr)

        # split
        if "split" in keys:
            struct_arr.append(pa.array([split]))

        # Struct array
        return pa.StructArray.from_arrays(struct_arr, fields=fields.to_pyarrow())
    except ImportError as e:
        raise ImportError(f"bop_toolkit_lib package missing: {e}")


class BopWDSImporter(Importer):
    """Importer class for BOP WDS dataset

    Attributes:
        info (DatasetInfo): Dataset information
        schema (pa.schema): Dataset schema
        splits (list[str]): Dataset splits
    """

    def __init__(
        self,
        name: str,
        description: str,
        splits: list[str],
    ):
        """Initialize BOP WDS Importer

        Args:
            name (str): Dataset name
            description (str): Dataset description
            splits (list[str]): Dataset splits
        """

        # Comment/uncomment to desactivate/activate a feature (need coco_json_path for object_id and mask)
        fields = Fields.from_dict(
            {
                "id": "str",
                "rgb": "Image",
                "depth": "DepthImage",
                "camera": "Camera",
                "category_id": "[int]",
                # "objects_id": "[str]",
                # "masks": "[CompressedRLE]",
                "gt": "[Pose]",
                "gt_info": "[GtInfo]",
                "split": "str",
            }
        )

        super().__init__(name, description, fields, splits)

    def shard_list(self, input_dir: str | Path) -> dict[str, list[str]]:
        return {
            split: [
                os.path.join(input_dir, split, shard)
                for shard in os.listdir(input_dir / split)
                if shard.endswith(".tar")
            ]
            for split in self.splits
        }

    def import_row(self, input_dirs: dict[str, str | Path]) -> Iterator:
        try:
            import webdataset as wds

            for input_dir in input_dirs.values():
                shard_split_dict = self.shard_list(input_dir)
                # split dataset
                for split, shard_list in shard_split_dict.items():
                    _wds_pipeline = wds.DataPipeline(
                        wds.SimpleShardList(shard_list), wds.tarfile_to_samples()
                    )

                    # extract row of each split
                    for row in _wds_pipeline:
                        yield pa.RecordBatch.from_struct_array(
                            #### Change Coco_json_path here
                            row_to_array(
                                row, split, self.info.fields, coco_json_path=None
                            )
                        )

        except ImportError as e:
            raise ImportError(f"webdataset package missing: {e}")
