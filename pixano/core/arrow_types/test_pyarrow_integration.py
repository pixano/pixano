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


import subprocess
import unittest
from io import BytesIO

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from PIL import Image as pilImage

from pixano.transforms import image_to_binary

from . import *


class TestParquetBBox(unittest.TestCase):
    def setUp(self) -> None:
        self.bbox_list = [
            BBox([0.1, 0.2, 0.3, 0.4], "xyxy", True),
            BBox([0.1, 0.2, 0.2, 0.2], "xywh", True),
            BBox([12, 2.9, 3.3, 7], "xyxy", False),
        ]

    def test_bbox_table(self):
        bbox_arr = BBoxArray.from_BBox_list(self.bbox_list)

        table = pa.Table.from_arrays([bbox_arr], names=["bbox"])
        pq.write_table(table, "test_bbox.parquet", store_schema=True)

        re_table = pq.read_table("test_bbox.parquet")
        self.assertEqual(re_table.column_names, ["bbox"])
        Bbox0 = re_table.take([0])["bbox"][0].as_py()
        self.assertTrue(isinstance(Bbox0, BBox))

    def test_bbox_table_with_panda(self):
        bbox_arr = BBoxArray.from_BBox_list(self.bbox_list)

        pd_bbox = bbox_arr.to_pandas()

        df = pd.DataFrame(pd_bbox, columns=["bbox"])
        pd_table = pa.Table.from_pandas(df)

        pq.write_table(pd_table, "test_bbox.parquet")

        reload_pd_table = pq.read_pandas("test_bbox.parquet")
        BBox1 = reload_pd_table.take([0])["bbox"][0].as_py()

        self.assertEqual(reload_pd_table.column_names, ["bbox"])
        # panda give dict
        self.assertTrue(isinstance(BBox1, dict))

    @classmethod
    def tearDownClass(cls):
        # subprocess.run(["make", "clean"])  # comment here for not cleaning parquet file after test
        None


class TestParquetImage(unittest.TestCase):
    def test_image_table(self):
        uri = "http://farm3.staticflickr.com/2595/3984712091_e82c5ec1ca_z.jpg"
        im_data = requests.get(uri)
        im = pilImage.open(BytesIO(im_data.content))
        im.thumbnail((128, 128))
        im.save("thumb.png")
        preview = image_to_binary(im)
        image = Image(uri, None, preview)
        image_array = ImageArray.from_Image_list([image])

        schema = pa.schema(
            [
                pa.field("image", ImageType()),
            ]
        )
        table = pa.Table.from_arrays([image_array], schema=schema)
        pq.write_table(table, "test_image.parquet", store_schema=True)
        re_table = pq.read_table("test_image.parquet")

        self.assertEqual(re_table.column_names, ["image"])
        image0 = re_table.take([0])["image"][0].as_py()
        self.assertTrue(isinstance(image0, Image))

    @classmethod
    def tearDownClass(cls):
        # subprocess.run(["make", "clean"])  # comment here for not cleaning parquet file after test
        None


class TestParquetPose(unittest.TestCase):
    def setUp(self) -> None:
        cam_R_m2c0, cam_R_m2c1 = [i % 2.4 for i in range(9)], [
            i % 1.7 for i in range(9)
        ]
        cam_t_m2c0, cam_t_m2c1 = [i for i in range(3)], [3 * i for i in range(3)]

        self.pose_list = [Pose(cam_R_m2c0, cam_t_m2c0), Pose(cam_R_m2c1, cam_t_m2c1)]

    def test_pose_table(self):
        pose_array = PoseArray.from_Pose_list(self.pose_list)

        schema = pa.schema(
            [
                pa.field("pose", PoseType()),
            ]
        )
        table = pa.Table.from_arrays([pose_array], schema=schema)
        pq.write_table(table, "test_pose.parquet", store_schema=True)
        re_table = pq.read_table("test_pose.parquet")

        self.assertEqual(re_table.column_names, ["pose"])
        pose1 = re_table.take([1])["pose"][0].as_py()
        self.assertTrue(isinstance(pose1, Pose))

    @classmethod
    def tearDownClass(cls):
        # subprocess.run(["make", "clean"])  # comment here for not cleaning parquet file after test
        None


class TestParquetCompressedRLE(unittest.TestCase):
    def setUp(self) -> None:
        self.compressedRLE_list = [
            CompressedRLE([1, 2], None),
            CompressedRLE([1, 2], None),
        ]

    def test_compressedRLE_table(self):
        compressedRLE_array = CompressedRLEArray.from_CompressedRLE_list(
            self.compressedRLE_list
        )

        schema = pa.schema(
            [
                pa.field("compressedRLE", CompressedRLEType()),
            ]
        )
        table = pa.Table.from_arrays([compressedRLE_array], schema=schema)
        pq.write_table(table, "test_compressedRLE.parquet", store_schema=True)
        re_table = pq.read_table("test_compressedRLE.parquet")

        self.assertEqual(re_table.column_names, ["compressedRLE"])
        compressedRLE1 = re_table.take([0])["compressedRLE"][0].as_py()
        self.assertTrue(isinstance(compressedRLE1, CompressedRLE))

    @classmethod
    def tearDownClass(cls):
        # subprocess.run(["make", "clean"])  # comment here for not cleaning parquet file after test
        None


class TestParquetObjectAnnotation(unittest.TestCase):
    def setUp(self) -> None:
        self.object_annotations_list = [
            ObjectAnnotation(
                id="annotation_001",
                view_id="image",
                bbox=BBox.from_xyxy([10, 20, 50, 40]),
                bbox_source="manual",
                bbox_confidence=0.9,
                is_group_of=False,
                is_difficult=False,
                is_truncated=False,
                mask=CompressedRLE([2, 4], None),
                mask_source="manual",
                area=200.0,
                pose=Pose(
                    [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], [1.0, 2.0, 3.0]
                ),
                category_id=1,
                category_name="person",
                identity="John Doe",
            ),
            ObjectAnnotation(
                id="annotation_002",
                view_id="image",
                bbox=BBox.from_xyxy([20, 30, 60, 50]),
                bbox_source="manual",
                bbox_confidence=0.8,
                is_group_of=False,
                is_difficult=False,
                is_truncated=False,
                mask=CompressedRLE([1, 1], None),
                mask_source="manual",
                area=300.0,
                pose=Pose(
                    [0.1, 0.1, 0.1, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9], [1.0, 1.0, 1.0]
                ),
                category_id=2,
                category_name="car",
                identity=None,
            ),
        ]

    def test_object_annotation_table(self):
        object_annotation_array = ObjectAnnotationArray.from_ObjectAnnotation_list(
            self.object_annotations_list
        )

        schema = pa.schema(
            [
                pa.field("objectAnnotation", ObjectAnnotationType()),
            ]
        )

        table = pa.Table.from_arrays([object_annotation_array], schema=schema)
        pq.write_table(table, "test_object_annotation.parquet", store_schema=True)
        re_table = pq.read_table("test_object_annotation.parquet")

        self.assertEqual(re_table.column_names, ["objectAnnotation"])
        objectAnnotation1 = re_table.take([0])["compressedRLE"][0].as_py()
        self.assertTrue(isinstance(objectAnnotation1, ObjectAnnotation))

    @classmethod
    def tearDownClass(cls):
        # subprocess.run(["make", "clean"])  # comment here for not cleaning parquet file after test
        None
