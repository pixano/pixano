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
