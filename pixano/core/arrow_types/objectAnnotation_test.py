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

import unittest

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from .bbox import BBox
from .compressedRLE import CompressedRLE
from .objectAnnotation import ObjectAnnotation, ObjectAnnotationArray
from .pose import Pose


class ObjectAnnotationTestCase(unittest.TestCase):
    pass


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
        objAnn_arr = ObjectAnnotationArray.from_ObjAnnot_list(
            self.object_annotations_list
        )

        table = pa.Table.from_arrays([objAnn_arr], names=["objAnn"])
        pq.write_table(table, "test_object_annotation.parquet")
        re_table = pq.read_table("test_object_annotation.parquet")

        self.assertEqual(re_table.column_names, ["objAnn"])

        # self.assertTrue(isinstance(objectAnnotation1, ObjectAnnotation))
