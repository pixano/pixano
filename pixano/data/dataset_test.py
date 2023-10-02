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

from pixano.data.dataset import Dataset
from pixano.data.dataset_info import DatasetInfo
from pixano.data.fields import Fields


class DatasetTestCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

        self.info = DatasetInfo(
            id="datasetid001",
            name="My dataset",
            description="Dataset from a great AI project",
            fields=Fields.from_dict({"field1": "int", "field2": "Image"}),
        )
        with open(self.tmpdir / "db.json", "w") as f:
            json.dump(self.info.to_dict(), f)

        self.dataset = Dataset(self.tmpdir)

    def test_info_property(self):
        self.assertTrue(isinstance(self.dataset.info, DatasetInfo))
        self.assertEqual(self.dataset.info, self.info)

    def test_path_property(self):
        self.assertTrue(isinstance(self.dataset.path, Path))
        self.assertEqual(self.dataset.path, self.tmpdir)

    def test_media_dir_property(self):
        self.assertTrue(isinstance(self.dataset.media_dir, Path))
        self.assertEqual(self.dataset.media_dir, self.tmpdir / "media")
