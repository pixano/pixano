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

from pixano.core import ImageType
from pixano.data.fields import Fields


class FieldsTestCase(unittest.TestCase):
    def setUp(self):
        self.dict = {"field1": "int", "field2": "Image"}
        self.fields = Fields(self.dict)
        self.pyarrow_list = [
            pa.field("field1", pa.int64()),
            pa.field("field2", ImageType),
        ]

    def test_init(self):
        fields_from_base_dict = Fields(self.dict)
        fields_from_attr_dict = Fields(self.fields.field_dict)

        self.assertTrue(isinstance(fields_from_base_dict, Fields))
        self.assertTrue(isinstance(fields_from_attr_dict, Fields))
        self.assertEqual(self.fields, fields_from_base_dict)
        self.assertEqual(self.fields, fields_from_attr_dict)

    def test_to_schema(self):
        schema = self.fields.to_schema()

        self.assertTrue(isinstance(schema, pa.Schema))
        for pyarrow_field in schema:
            self.assertTrue(isinstance(pyarrow_field, pa.Field))
        self.assertEqual(schema, pa.schema(self.pyarrow_list))
