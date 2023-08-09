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

import tempfile
import unittest

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from pixano.core.bbox import BBox
from pixano.core.compressed_rle import CompressedRLE
from pixano.core.object_annotation import ObjectAnnotation, ObjectAnnotationType
from pixano.core.pose import Pose


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
        objAnn_arr = ObjectAnnotationType.Array.from_pylist(
            self.object_annotations_list
        )

        schema = pa.schema([pa.field("ObjectAnn", ObjectAnnotationType, nullable=True)])

        table = pa.Table.from_arrays([objAnn_arr], schema=schema)

        with tempfile.NamedTemporaryFile(suffix=".parquet") as temp_file:
            temp_file_path = temp_file.name
            pq.write_table(table, temp_file_path)
            re_table = pq.read_table(temp_file_path)

        self.assertEqual(re_table.column_names, ["ObjectAnn"])

        objectAnn_from_table = re_table.to_pylist()[0]["ObjectAnn"]
        self.assertTrue(isinstance(objectAnn_from_table, ObjectAnnotation))
