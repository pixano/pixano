import unittest

import numpy as np
from .bbox import Bbox

class TestBbox(unittest.TestCase):
    def test_init(self):
        bbox = Bbox([0.1, 0.2, 0.3, 0.4])
        self.assertTrue(np.allclose(bbox.coords, [0.1, 0.2, 0.3, 0.4]))
        self.assertEqual(bbox.format, 'xyxy')

        bbox = Bbox([0.1, 0.2, 0.3, 0.4], 'xywh')
        self.assertTrue(np.allclose(bbox.coords, [0.1, 0.2, 0.3, 0.4]))
        self.assertEqual(bbox.format, 'xywh')

        with self.assertRaises(ValueError):
            Bbox([0.1, 0.2, 0.3, 0.4], 'invalid')

    def test_set_format_xyxy(self):
        bbox = Bbox([0.1, 0.2, 0.3, 0.4], 'xywh')
        bbox.set_format_xyxy()
        self.assertTrue(np.allclose(bbox.coords, [0.1, 0.2, 0.4, 0.6]))
        self.assertEqual(bbox.format, 'xyxy')

        bbox = Bbox([0.1, 0.2, 0.3, 0.4])
        bbox.set_format_xyxy()
        self.assertTrue(np.allclose(bbox.coords, [0.1, 0.2, 0.3, 0.4]))
        self.assertEqual(bbox.format, 'xyxy')

    def test_set_format_xywh(self):
        bbox = Bbox([0.1, 0.2, 0.4, 0.6])
        bbox.set_format_xywh()
        self.assertTrue(np.allclose(bbox.coords, [0.1, 0.2, 0.3, 0.4]))
        self.assertEqual(bbox.format, 'xywh')

        bbox = Bbox([0.1, 0.2, 0.3, 0.4], 'xywh')
        bbox.set_format_xywh()
        self.assertTrue(np.allclose(bbox.coords, [0.1, 0.2, 0.3, 0.4]))
        self.assertEqual(bbox.format, 'xywh')
