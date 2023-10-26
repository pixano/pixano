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
import pyarrow as pa
from pydantic import BaseModel, PrivateAttr

from pixano.core.pixano_type import PixanoType, create_pyarrow_type


class DepthImage(PixanoType, BaseModel):
    """Depth image type

    Attributes:
        _depth_map (np.ndarray, optional): Depth image as NumPy array
        _bytes (bytes, optional): Depth image as bytes
        _shape (list[int], optional): Depth image shape
    """

    _depth_map: Optional[np.ndarray] = PrivateAttr()
    _bytes: Optional[bytes] = PrivateAttr()
    _shape: Optional[list[int]] = PrivateAttr()

    def __init__(
        self,
        depth_map: np.ndarray = None,
        bytes: bytes = None,
        shape: list[int] = None,
    ):
        """Initialize Depth image

        Args:
            depth_map (np.ndarray, optional): Depth image as NumPy array. Defaults to None.
            bytes (bytes, optional): Depth image as bytes. Defaults to None.
            shape (list[int], optional): Depth image shape. Defaults to None.
        """

        # Define public attributes through Pydantic BaseModel
        super().__init__()

        # Define private attributes manually
        self._depth_map = depth_map
        self._bytes = bytes
        self._shape = shape

    @property
    def shape(self) -> list[int]:
        """Return Depth image shape

        Returns:
            list[int]: Depth image shape
        """

        return self._shape

    @property
    def bytes(self) -> bytes:
        """Return Depth image as bytes

        Returns:
            bytes: Depth image as bytes
        """

        if self._bytes is not None:
            return self._bytes
        return self._depth_map.tobytes()

    @property
    def depth_map(self) -> np.ndarray:
        """Returns Depth image as NumPy array

        Returns:
            np.ndarray: Depth image as NumPy array
        """

        if self._depth_map is not None:
            return self._depth_map
        return np.frombuffer(self._bytes, dtype=np.float32).reshape(self._shape)

    @staticmethod
    def load_npy(path: str) -> "DepthImage":
        """Create depth image from .npy file

        Args:
            path (str): Path to .npy file containing depth image as NumPy Array.

        Returns:
            DepthImage: Depth image
        """

        map = np.load(path)
        return DepthImage(depth_map=map, shape=map.shape)

    @staticmethod
    def load(path: str) -> "DepthImage":
        """Create depth image from 16-bit .png file

        Args:
            path (str): Path of .png file of depth image

        Returns:
            DepthImage: Depth image
        """

        map = imageio.v3.imread(path).astype(np.uint16)
        return DepthImage(depth_map=map, shape=map.shape)

    def save(self, path):
        """Save depth image to .png file.

        Args:
            path (str): Path to .png file to save
        """

        depth_image = self.depth_map.astype(np.uint16)
        imageio.v3.imwrite(path, depth_image)

    def open(self) -> IO:
        return io.BytesIO(self.bytes)

    def to_grayscale(
        self,
    ) -> "DepthImage":
        """Transform Depth image to 8-bit grayscale depth image

        Returns:
            DepthImage: 8-bit grayscale depth image
        """

        depth = self.depth_map
        min, max = depth.min(), depth.max()
        depth_n: np.ndarray = ((depth - min) / (max - min)) * 255
        return DepthImage(depth_map=depth_n.astype(np.uint8), shape=depth.shape)

    def display(self):
        """Display Depth image with matplotlib"""

        plt.imshow(self.depth_map.astype(np.int8), cmap="gray", vmin=0, vmax=255)
        plt.axis("off")
        if self._shape is not None:
            plt.figure(figsize=self._shape)
        plt.show()

    @staticmethod
    def to_struct() -> pa.StructType:
        """Return DepthImage type as PyArrow Struct

        Returns:
            pa.StructType: Custom type corresponding PyArrow Struct
        """

        return pa.struct(
            [
                pa.field("bytes", pa.binary()),
                pa.field("shape", pa.list_(pa.int32(), list_size=2)),
            ]
        )


DepthImageType = create_pyarrow_type(DepthImage.to_struct(), "DepthImage", DepthImage)
