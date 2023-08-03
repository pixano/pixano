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

from pixano.types import Fields

from .dataset import Dataset, DatasetInfo


class TestDataset(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp())

    def test_from_spec(self):
        info = DatasetInfo(
            id="datasetid001",
            name="My dataset",
            description="Dataset from a great AI project",
            fields=Fields.from_dict({"field1": "int32", "field2": "image"}),
        )
        with open(self.tmpdir / "spec.json", "w") as f:
            json.dump(info.to_dict(), f)

        dataset = Dataset(self.tmpdir)

        self.assertEqual(info.id, dataset.info.id)
        self.assertEqual(info.name, dataset.info.name)
        self.assertEqual(info.description, dataset.info.description)
        self.assertEqual(info.fields, dataset.info.fields)
