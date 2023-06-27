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

import io
from typing import IO, Optional


import imageio
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pyarrow as pa

# ------------------------------------------------
#             Python type
# ------------------------------------------------


class DepthImage:
    """DepthImage stored as uint16 images"""

    def __init__(
        self,
        depth_map: np.ndarray = None,
        bytes_data: bytes = None,
        shape: list[int] = None,
    ):
        self._bytes = bytes_data
        self._depth_map = depth_map
        self._shape = shape

    @property
    def bytes(self) -> bytes:
        if self._bytes is not None:
            return self._bytes
        return self._depth_map.tobytes()

    @property
    def depth_map(self) -> np.ndarray:
        if self._depth_map is not None:
            return self._depth_map
        return np.frombuffer(self._bytes, dtype=np.uint16).reshape(self._shape)

    @staticmethod
    def load(path: str) -> "DepthImage":
        """load depth image (16 bit) to instance DepthImage

        Args:
            path (str): path of the file to load

        Returns:
            DepthImage: instance of DepthImage
        """
        map = imageio.imread(path).astype(np.uint16)
        return DepthImage(depth_map=map, shape=map.shape)

    def save(self, path):
        """save depth image in png format

        Args:
            path (str): name of file
        """
        depth_image = self.depth_map.astype(np.uint16)
        imageio.imwrite(path, depth_image)

    def open(self) -> IO:
        return io.BytesIO(self.bytes)

    def to_gray_levels(
        self,
    ) -> "DepthImage":
        """Transform image to gray levels in 8 bit

        Returns:
            DepthImage: new DepthImage in 8 bit
        """

        depth = self.depth_map

        min, max = depth.min(), depth.max()

        depth_n: np.ndarray = ((depth - min) / (max - min)) * 255

        return DepthImage(depth_map=depth_n.astype(np.uint8))

    def display(self):
        plt.imshow(self.depth_map, cmap="gray", vmin=0, vmax=255)
        plt.axis("off")
        if self._shape is not None:
            plt.figure(figsize=self._shape)
        plt.show()


# ------------------------------------------------
#             Py arrow integration
# ------------------------------------------------


class DepthImageType(pa.ExtensionType):
    """Depth map extension types"""

    def __init__(self):
        super(DepthImageType, self).__init__(pa.binary(), "depthmap")

    def __arrow_ext_serialize__(self):
        return b""

    @classmethod
    def __arrow_ext_deserialize__(cls, storage_type, serialized):
        return DepthImageType()

    def __arrow_ext_scalar_class__(self):
        return DepthImageScalar


class DepthImageScalar(pa.ExtensionScalar):
    """Used by ExtensionArray.to_pylist()"""

    def as_py(self) -> Optional[DepthImage]:
        if pd.isna(self.value):
            return None
        return DepthImage(self.value.as_py())


def is_depthMap_type(t: pa.DataType) -> bool:
    """Returns True if the type is an image type"""
    return isinstance(t, DepthImageType)
