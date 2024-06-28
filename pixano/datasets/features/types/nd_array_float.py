# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import numpy as np
from pydantic import BaseModel

from pixano.datasets.utils import is_obj_of_type

from .registry import _register_type_internal


@_register_type_internal
class NDArrayFloat(BaseModel):
    """Represents an N-dimensional array of floating-point values.

    Attributes:
        values (list[float]): The list of floating-point values in the array.
        shape (list[int]): The shape of the array, represented as a list of integers.
    """

    values: list[float]
    shape: list[int]

    @staticmethod
    def none():
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            NDArrayFloat: "None" NDArrayFloat
        """
        return NDArrayFloat(values=[0, 0], shape=[1, 1])

    @classmethod
    def from_numpy(cls, arr: np.ndarray) -> "NDArrayFloat":
        """Create an instance of the class from a NumPy array.

        Args:
            arr (np.ndarray): The NumPy array to convert.

        Returns:
            cls: An instance of the class with values and shape derived from
                the input array.
        """
        return cls(values=arr.reshape(-1).tolist(), shape=list(arr.shape))


def is_ndarray_float(cls: type) -> bool:
    """Check if a class is an NDArrayFloat or a subclass of NDArrayFloat."""
    return is_obj_of_type(cls, NDArrayFloat)


def create_ndarray_float(values: list[float], shape: list[int]) -> NDArrayFloat:
    """Create an NDArrayFloat instance.

    Args:
        values (list[float]): The list of floating-point values in the array.
        shape (list[int]): The shape of the array, represented as a list of integers.

    Returns:
        NDArrayFloat: The created NDArrayFloat instance.
    """
    return NDArrayFloat(values=values, shape=shape)
