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
from io import BytesIO

import numpy as np
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import requests
from .image import Image, ImageArray, ImageType
from PIL import Image as pilImage

from pixano.transforms import image_to_binary


class ImageTestCase(unittest.TestCase):
    pass


class TestParquetImage(unittest.TestCase):
    def test_image_table(self):
        uri = "http://farm3.staticflickr.com/2595/3984712091_e82c5ec1ca_z.jpg"
        im_data = requests.get(uri)
        im = pilImage.open(BytesIO(im_data.content))
        im.thumbnail((128, 128))
        im.save("thumb.png")
        preview = image_to_binary(im)
        image = Image(uri, None, preview)
        image_array = ImageArray.from_Image_list([image])

        schema = pa.schema(
            [
                pa.field("image", ImageType()),
            ]
        )
        table = pa.Table.from_arrays([image_array], schema=schema)
        pq.write_table(table, "test_image.parquet", store_schema=True)
        re_table = pq.read_table("test_image.parquet")

        self.assertEqual(re_table.column_names, ["image"])
        image0 = re_table.take([0])["image"][0].as_py()
        self.assertTrue(isinstance(image0, Image))