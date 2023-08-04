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

import pyarrow as pa

from pixano.core.image import ImageType
from pixano.core.object_annotation import ObjectAnnotationType
from pixano.core.utils import (
    is_image_type,
    is_list_of_object_annotation_type,
    is_number,
)


class IsNumberTestCase(unittest.TestCase):
    def test_is_number(self):
        pa_int_field = pa.field("some integers", pa.int64())
        self.assertTrue(is_number(pa_int_field.type))

        pa_float_field = pa.field("some floats", pa.float64())
        self.assertTrue(is_number(pa_float_field.type))


class IsImageTypeTestCase(unittest.TestCase):
    def test_is_image_type(self):
        pa_im_field = pa.field("some images", ImageType)
        self.assertTrue(is_image_type(pa_im_field.type))


class IsListOfObjectAnnotationTypeTestCase(unittest.TestCase):
    def test_is_list_of_object_annotation_type(self):
        pa_obj_field = pa.field(
            "some lists of ObjectAnnotation", pa.list_(ObjectAnnotationType)
        )
        self.assertTrue(is_list_of_object_annotation_type(pa_obj_field.type))
