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
import tempfile
import unittest
from pathlib import Path

from pixano.data.dataset_info import DatasetInfo
from pixano.data.fields import Fields


class DatasetInfoTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

        self.info = DatasetInfo(
            id="datasetid001",
            name="My dataset",
            description="Dataset from a great AI project",
            fields=Fields.from_dict({"field1": "int", "field2": "Image"}),
        )

    def test_parse_file(self):
        with open(self.tmpdir / "db.json", "w") as f:
            json.dump(self.info.to_dict(), f)

        info_read = DatasetInfo.parse_file(self.tmpdir / "db.json")

        self.assertTrue(isinstance(info_read, DatasetInfo))
        self.assertEqual(self.info.id, info_read.id)
        self.assertEqual(self.info.name, info_read.name)
        self.assertEqual(self.info.description, info_read.description)
        self.assertEqual(self.info.fields, info_read.fields)

    def test_to_dict(self):
        info_dict = self.info.to_dict()

        self.assertTrue(isinstance(info_dict, dict))
        self.assertEqual(self.info.id, info_dict["id"])
        self.assertEqual(self.info.name, info_dict["name"])
        self.assertEqual(self.info.description, info_dict["description"])
        self.assertEqual(self.info.fields.to_dict(), info_dict["fields"])

        info_convert = DatasetInfo(**info_dict)

        self.assertTrue(isinstance(info_convert, DatasetInfo))
        self.assertEqual(self.info.id, info_convert.id)
        self.assertEqual(self.info.name, info_convert.name)
        self.assertEqual(self.info.description, info_convert.description)
        self.assertEqual(self.info.fields, info_convert.fields)
