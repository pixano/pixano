import unittest

import numpy as np
from .bbox import Bbox

class BboxTestCase(unittest.TestCase):
    def setUp(self):
        self.xyxy_coords = [0.1, 0.2, 0.3, 0.4]
        self.xywh_coords = [0.1, 0.2, 0.3, 0.4]
        self.bbox_xyxy = Bbox.from_xyxy(self.xyxy_coords)
        self.bbox_xywh = Bbox.from_xywh(self.xywh_coords)

    def test_format_property(self):
        self.assertEqual(self.bbox_xyxy.format, 'xyxy')
        self.assertEqual(self.bbox_xywh.format, 'xywh')

    def test_is_normalized_property(self):
        self.assertTrue(self.bbox_xyxy.is_normalized)
        self.assertTrue(self.bbox_xywh.is_normalized)

    def test_to_xyxy(self):
        converted_coords = self.bbox_xyxy.to_xyxy()
        self.assertTrue(np.allclose(converted_coords, self.xyxy_coords))

    def test_to_xywh(self):
        converted_coords = self.bbox_xywh.to_xywh()
        self.assertTrue(np.allclose(converted_coords, self.xywh_coords))

    def test_format_conversion(self):
        self.bbox_xyxy.format_xywh()
        self.assertEqual(self.bbox_xyxy.format, 'xywh')
        self.assertTrue(np.allclose(self.bbox_xyxy.to_xywh(), [0.1, 0.2, 0.2, 0.2]))

        self.bbox_xywh.format_xyxy()
        self.assertEqual(self.bbox_xywh.format, 'xyxy')
        self.assertTrue(np.allclose(self.bbox_xywh.to_xyxy(), [0.1, 0.2, 0.4, 0.6]))

    def test_normalize(self):
        self.bbox_to_normalize = Bbox.from_xyxy([10, 10, 20, 20])
        height = 100
        width = 200
        self.bbox_to_normalize.normalize(height, width)
        self.assertTrue(np.allclose(self.bbox_to_normalize.to_xyxy(), [0.05, 0.1, 0.1, 0.2]))

