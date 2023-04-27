import unittest
from io import BytesIO

import pyarrow as pa
import pyarrow.parquet as pq
import requests
from PIL import Image

from pixano.core import arrow_types
from pixano.transforms import encode_png


class TestImageUriType(unittest.TestCase):
    def test_image_uri_type(self):
        uri = "http://farm3.staticflickr.com/2595/3984712091_e82c5ec1ca_z.jpg"
        im_data = requests.get(uri)
        im = Image.open(BytesIO(im_data.content))
        im.thumbnail((128, 128))
        im.save("thumb.png")
        preview = encode_png(im)

        im_uri_type = arrow_types.ImageUriType()
        im_storage = pa.array([{"preview": preview, "uri": uri}])
        arr = pa.ExtensionArray.from_storage(im_uri_type, im_storage)

        schema = pa.schema(
            [
                pa.field("image", arrow_types.ImageUriType()),
            ]
        )
        table = pa.Table.from_arrays([arr], schema=schema)
        pq.write_table(table, "test.parquet", store_schema=True)

        print(table.schema)
        # self.assertTrue(isinstance(im_py, arrow_types.ImageUri))
        # self.assertEqual(im_py.uri, uri)
        # with open("test.jpg", "wb") as f:
        #     f.write(im_py.preview)
        # self.assertFalse(isinstance(im_uri_type, arrow_types.ImageUriType))
