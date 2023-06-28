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
    def load_npy(path: str) -> "DepthImage":
        """Load depth image from npy file

        Args:
            path (str): path of file .npy. The file must contains an array of depth image.

        Returns:
            DepthImage: Instance of DepthImage
        """
        map = np.load(path)
        return DepthImage(depth_map=map, shape=map.shape)

    @staticmethod
    def load(path: str) -> "DepthImage":
        """Load depth image (16 bit) to instance DepthImage.

        Args:
            path (str): path of the file to load. Work with .png and .npy

        Returns:
            DepthImage: instance of DepthImage
        """
        map = imageio.imread(path).astype(np.uint16)
        return DepthImage(depth_map=map, shape=map.shape)

    def save(self, path):
        """Save depth image in png format.

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
        """Transform image to gray levels in 8 bit.

        Returns:
            DepthImage: new DepthImage in 8 bit
        """

        depth = self.depth_map

        min, max = depth.min(), depth.max()

        depth_n: np.ndarray = ((depth - min) / (max - min)) * 255

        return DepthImage(depth_map=depth_n.astype(np.uint8))

    def to_dict(self) -> dict:
        return {"bytes": self.bytes, "shape": self._shape}

    def display(self):
        """display image as plt.figure object"""
        plt.imshow(self.depth_map, cmap="gray", vmin=0, vmax=255)
        plt.axis("off")
        if self._shape is not None:
            plt.figure(figsize=self._shape)
        plt.show()


# ------------------------------------------------
#             Py arrow integration
# ------------------------------------------------


class DepthImageType(pa.ExtensionType):
    """Depth image extension types"""

    def __init__(self):
        super(DepthImageType, self).__init__(
            pa.struct(
                [
                    pa.field("bytes", pa.binary()),
                    pa.field("shape", pa.list_(pa.int32(), list_size=2)),
                ]
            ),
            "DepthImage",
        )

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
        return DepthImage(
            bytes_data=self.value["bytes"].as_py(), shape=self.value["shape"].as_py()
        )


class DepthImageArray(pa.ExtensionArray):
    """Class to use pa.array for DepthImage instance"""

    @classmethod
    def from_list(cls, depth_image_list: list[DepthImage]) -> pa.Array:
        """Create DepthImage pa.array from DepthImage list

        Args:
            depth_image_list (list[DepthImage]): list of DepthImage

        Returns:
            pa.Array: pa.array of DepthImage
        """
        depth_image_dicts = [depth_image.to_dict() for depth_image in depth_image_list]

        return pa.array(depth_image_dicts, DepthImageType())


def is_depth_image_type(t: pa.DataType) -> bool:
    """Returns True if the type is an Depthimage type"""
    return isinstance(t, DepthImageType)
