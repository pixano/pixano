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

from pixano.utils.labels import (
    coco_ids_80to91,
    coco_names_80,
    coco_names_91,
    dota_ids,
    voc_names,
)


class LabelsUtilsTestCase(unittest.TestCase):
    """Labels utils test case"""

    def test_coco_ids_80to91(self):
        """Test coco_ids_80to91 function"""

        for i in range(1, 80):
            self.assertIsInstance(coco_ids_80to91(i), int)

    def test_coco_names_80(self):
        """Test coco_names_80 function"""

        for i in range(1, 80):
            self.assertIsInstance(coco_names_80(i), str)

    def test_coco_names_91(self):
        """Test coco_names_91 function"""

        for i in range(1, 91):
            self.assertIsInstance(coco_names_91(i), str)

    def test_dota_ids(self):
        """Test dota_ids function"""

        dota_labels = [
            "plane",
            "ship",
            "storage tank",
            "baseball diamond",
            "tennis court",
            "basketball court",
            "ground track field",
            "harbor",
            "bridge",
            "large vehicle",
            "small vehicle",
            "helicopter",
            "roundabout",
            "soccer ball field",
            "swimming pool",
            "container crane",
            "airport",
            "helipad",
        ]
        for label in dota_labels:
            self.assertIsInstance(dota_ids(label), int)

    def test_voc_names(self):
        """Test voc_names function"""

        for i in range(1, 20):
            self.assertIsInstance(voc_names(i), str)
