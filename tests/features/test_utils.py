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

from pixano.features import ImageType, is_binary, is_float, is_image_type, is_integer


class UtilsTestCase(unittest.TestCase):
    """Core utils functions test case"""

    def test_is_integer(self):
        """Test is_integer function"""

        pa_int_field = pa.field("some integers", pa.int64())
        pa_float_field = pa.field("some floats", pa.float64())

        self.assertTrue(is_integer(pa_int_field.type))
        self.assertFalse(is_integer(pa_float_field.type))

    def test_is_float(self):
        """Test is_float function"""

        pa_int_field = pa.field("some integers", pa.int64())
        pa_float_field = pa.field("some floats", pa.float64())

        self.assertTrue(is_float(pa_float_field.type))
        self.assertFalse(is_float(pa_int_field.type))

    def test_is_binary(self):
        """Test is_binary function"""

        pa_binary_field = pa.field("some binaries", pa.binary())
        pa_string_field = pa.field("some string", pa.string())

        self.assertTrue(is_binary(pa_binary_field.type))
        self.assertFalse(is_binary(pa_string_field.type))

    def test_is_image_type(self):
        """Test is_image_type function"""

        pa_im_field = pa.field("some images", ImageType)

        self.assertTrue(is_image_type(pa_im_field.type))
