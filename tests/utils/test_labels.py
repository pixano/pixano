# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import unittest

from pixano.datasets.utils.labels import (
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
