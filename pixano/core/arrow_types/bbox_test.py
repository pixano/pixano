import unittest

import numpy as np
from .bbox import Bbox

class TestBbox(unittest.TestCase):
    def setUp(self):
        self.bbox = Bbox([0.1, 0.2, 0.3, 0.4])
        self.bbox2 = Bbox([10,20,30,40], 'xywh')

    def test_init(self):
        self.assertTrue(np.allclose(self.bbox.coords, [0.1, 0.2, 0.3, 0.4]))
        self.assertEqual(self.bbox.format, 'xyxy')

        with self.assertRaises(ValueError):
            Bbox([0.1, 0.2, 0.3, 0.4], 'invalid')

    def test_set_format_xyxy(self):
        self.bbox2.set_format_xyxy()
        self.assertTrue(np.allclose(self.bbox2.coords, [10, 20, 40, 60]))
        self.assertEqual(self.bbox2.format, 'xyxy')

    def test_set_format_xywh(self):
        self.bbox.set_format_xywh()
        self.assertTrue(np.allclose(self.bbox.coords, [0.1, 0.2, 0.2, 0.2]))
        self.assertEqual(self.bbox.format, 'xywh')

    def test_normalize(self):
        height = 100
        width = 200

        self.bbox2.normalize(height, width)
        self.assertEqual(self.bbox2.coords, [0.05, 0.2, 0.15, 0.4])

    def test_denormalize(self):
        height = 100
        width = 200

        self.bbox2.normalize(height, width)
        self.bbox2.denormalize(height, width)
        self.assertEqual(self.bbox2.coords, [10,20,30,40])

    def test_get_convertion_for_front_end(self):
        is_predicted = True
        confidence = 0.75

        result = self.bbox.get_convertion_for_front_end(is_predicted, confidence)

        # Vérifier que le résultat est un dictionnaire avec les clés attendues
        self.assertIsInstance(result, dict)
        self.assertIn('x', result)
        self.assertIn('y', result)
        self.assertIn('width', result)
        self.assertIn('height', result)
        self.assertIn('is_predict', result)
        self.assertIn('confidence', result)

        # Vérifier que les valeurs du dictionnaire sont correctes
        self.assertAlmostEqual(result['x'], 0.1)
        self.assertAlmostEqual(result['y'], 0.2)
        self.assertAlmostEqual(result['width'], 0.3)
        self.assertAlmostEqual(result['height'], 0.4)
        self.assertEqual(result['is_predict'], is_predicted)
        self.assertEqual(result['confidence'], confidence)