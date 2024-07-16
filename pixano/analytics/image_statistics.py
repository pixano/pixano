# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from fractions import Fraction

import pyarrow as pa
from PIL import Image as PILImage

from pixano.datasets import Dataset


def compute_image_stats(ds: Dataset):
    """Compute image stats, save them to stats.json.

    Args:
        ds (Dataset): Dataset
    """
    tables = ds.open_tables()

    for view in tables["media"]:
        # will be flattened, so don't treat it as a real loop (only one elem)
        # tt = tables["media"][view].to_lance()
        # print(duckdb.sql("select * from tt"))
        data_table = tables["media"][view].to_arrow()

        # Take a subset of table without image columns
        # (which can't be converted to pandas)
        if not all(p in data_table.column_names for p in ["width", "height"]):
            print("INFO: 'width' and 'height' not found in media table, get it from image")
            images = data_table.select([view]).to_pylist()
            sizes = []
            for image in images:
                # im = image[view].as_pillow() ne marche plus car
                # uri_prefix vide (pb avec Image.get_uri())
                im = PILImage.open(ds.media_dir / image[view].uri)
                sizes.append({"width": im.width, "height": im.height})
            data = pa.Table.from_pylist(sizes).to_pandas()
        else:
            print("INFO: 'width' and 'height' found in media table, use it")
            data = data_table.select(["width", "height"]).to_pandas()

        # Compute additional data
        data["resolution"] = data.apply(lambda x: str(x["width"]) + "x" + str(x["height"]), axis=1)
        data["aspect_ratio"] = data.apply(lambda x: str(Fraction(x["width"], x["height"])).replace("/", ":"), axis=1)
        return data
