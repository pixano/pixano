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

import base64
import imageio
import io
import numpy as np
import pyarrow as pa
import pandas as pd
from PIL import Image as PILImage

from abc import ABC
from typing import IO, Optional
from pixano.transforms.image import depth_array_to_gray

# ------------------------------------------------
#             Python type
# ------------------------------------------------


class DepthMap(ABC):
    """DepthMap stored as uint16 images

    Args:
        abc (_type_): _description_
    """

    def __init__(self, bytes: bytes):
        self._bytes = bytes

    @property
    def bytes(self):
        return self._bytes

    def open(self) -> IO:
        return io.BytesIO(self.bytes)

    def display(self, size=None):
        with self.open() as f:
            values = imageio.imread(f)
        scaled_values = depth_array_to_gray(values.astype(np.float32))

        with io.BytesIO() as output_bytes:
            depth_rgb = PILImage.fromarray(scaled_values)
            if size:
                depth_rgb.thumbnail((size, size))
            depth_rgb.save(output_bytes, "PNG")
            encoded = output_bytes.getvalue()

        b64_png = base64.b64encode(encoded).decode("utf-8")
        return f"data:image/png;base64,{b64_png}"

    def __repr__(self):
        return "DepthMap(<embedded>)"

    def _repr_mimebundle_(self, include=None, exclude=None):
        from IPython.display import Image as IPyImage

        im = IPyImage(url=self.display(), format="png")
        return im._repr_mimebundle_(include=include, exclude=exclude)
    

# ------------------------------------------------
#             Py arrow integration
# ------------------------------------------------



class DepthMapType(pa.ExtensionType):
    """Depth map extension types"""

    def __init__(self):
        super(DepthMapType, self).__init__(pa.binary(), "depthmap")

    def __arrow_ext_serialize__(self):
        return b""

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return DepthMapType()

    def __arrow_ext_scalar_class__(self):
        return DepthMapScalar


class DepthMapScalar(pa.ExtensionScalar):
    """Used by ExtensionArray.to_pylist()"""

    def as_py(self) -> Optional[DepthMap]:
        if pd.isna(self.value):
            return None
        return DepthMap(self.value.as_py())


def is_depthMap_type(t: pa.DataType) -> bool:
    """Returns True if the type is an image type"""
    return isinstance(t, DepthMapType)
