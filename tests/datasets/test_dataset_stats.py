# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import tempfile
import unittest
from pathlib import Path

from pixano.datasets import DatasetStat


class DatasetStatTestCase(unittest.TestCase):
    """DatasetStat test case"""

    def setUp(self):
        """Tests setup"""

        # Create temporary directory
        # pylint: disable=consider-using-with
        self.temp_dir = tempfile.TemporaryDirectory()
        self.path = Path(self.temp_dir.name)

        # Create stats
        self.stats = [
            DatasetStat(
                name="Some numerical statistics",
                type="numerical",
                histogram=[
                    {"bin_start": 0.0, "bin_end": 1.0, "counts": 2, "split": "train"},
                    {"bin_start": 1.0, "bin_end": 2.0, "counts": 4, "split": "train"},
                    {"bin_start": 2.0, "bin_end": 3.0, "counts": 6, "split": "train"},
                    {"bin_start": 3.0, "bin_end": 4.0, "counts": 8, "split": "train"},
                ],
                range=[0.0, 10.0],
            ),
            DatasetStat(
                name="Some categorical statistics",
                type="categorical",
                histogram=[
                    {"Some categorical statistics": "a", "counts": 2, "split": "train"},
                    {"Some categorical statistics": "b", "counts": 4, "split": "train"},
                    {"Some categorical statistics": "c", "counts": 6, "split": "train"},
                    {"Some categorical statistics": "d", "counts": 8, "split": "train"},
                ],
            ),
        ]
        with open(self.path / "stats.json", "w", encoding="utf-8") as f:
            json.dump([stat.model_dump() for stat in self.stats], f)

    def tearDown(self):
        """Tests teardown"""

        self.temp_dir.cleanup()

    def test_from_json(self):
        """Test DatasetStat from_json method"""

        loaded_stats = DatasetStat.from_json(Path(self.path) / "stats.json")

        self.assertIsInstance(loaded_stats, list)
        for stat in loaded_stats:
            self.assertIsInstance(stat, DatasetStat)

        self.assertEqual(loaded_stats, self.stats)
