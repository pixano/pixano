# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import unittest
from pathlib import Path

from pixano.datasets import Settings


class SettingsTestCase(unittest.TestCase):
    """Settings test case"""

    def test_init(self):
        """Test Settings init method"""

        default_settings = Settings()
        custom_settings = Settings(library_dir="my_custom_library")

        self.assertEqual(
            default_settings.data_dir.absolute(),
            (Path.cwd() / "library").absolute(),
        )
        self.assertEqual(
            custom_settings.data_dir.absolute(),
            (Path.cwd() / "my_custom_library").absolute(),
        )
