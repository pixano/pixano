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

from pixano.core.image import Image, ImageType
from pixano.core.utils import is_image_type, is_number, pyarrow_array_from_list


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


class TestPaArrayConversion(unittest.TestCase):
    def test_extension_type_conversion(self):
        data = [Image(uri="1", bytes=b""), Image(uri="2", bytes=b"")]

        result_array = pyarrow_array_from_list(data, ImageType)

        self.assertIsInstance(result_array, pa.Array)

    def test_list_extension_type_conversion(self):
        data = [[Image(uri="1", bytes=b""), Image(uri="2", bytes=b"")]]

        result_array = pyarrow_array_from_list(data, ImageType)

        self.assertIsInstance(result_array, pa.Array)

        self.assertIsInstance(result_array.to_pylist()[0][0], Image)

    def test_data_type_conversion(self):
        data_type = pa.int32()
        data = [1, 2, 3]

        result_array = pyarrow_array_from_list(data, data_type)

        self.assertIsInstance(result_array, pa.Array)
