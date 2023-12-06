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

from pixano.data import Settings


class SettingsTestCase(unittest.TestCase):
    def test_init(self):
        custom_path = Path("test")

        default_settings = Settings()
        custom_settings = Settings(data_dir=custom_path)

        self.assertEqual(default_settings.data_dir, Path.cwd() / "library")
        self.assertEqual(custom_settings.data_dir, custom_path)
