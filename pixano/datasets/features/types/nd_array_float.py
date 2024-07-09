# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import numpy as np
from pydantic import model_validator

from pixano.datasets.utils import issubclass_strict

from .base_type import BaseType
from .registry import _register_type_internal


@_register_type_internal
class NDArrayFloat(BaseType):
    """Represents an N-dimensional array of floating-point values.

    Attributes:
        values (list[float]): The list of floating-point values in the array.
        shape (list[int]): The shape of the array, represented as a list of integers.
    """

    values: list[float]
    shape: list[int]

    @model_validator(mode="after")
    def _validate_fields(self):
        if len(self.shape) < 1:
            raise ValueError("Shape must have at least one element.")
        elif any(s < 1 for s in self.shape):
            raise ValueError("Shape elements must be positive.")
        elif len(self.values) != np.prod(self.shape):
            raise ValueError("Number of values must match the product of the shape.")
        return self

    @classmethod
    def none(cls) -> "NDArrayFloat":
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            NDArrayFloat: "None" NDArrayFloat
        """
        return cls(values=[0], shape=[1])

    @staticmethod
    def from_numpy(arr: np.ndarray) -> "NDArrayFloat":
        """Create an instance of the class from a NumPy array.

        Args:
            arr (np.ndarray): The NumPy array to convert.

        Returns:
            NDArrayFloat: An instance of the class with values and shape derived from
                the input array.
        """
        return NDArrayFloat(values=arr.reshape(-1).tolist(), shape=list(arr.shape))


def is_ndarray_float(cls: type, strict: bool = False) -> bool:
    """Check if a class is an NDArrayFloat or a subclass of NDArrayFloat."""
    return issubclass_strict(cls, NDArrayFloat, strict)


def create_ndarray_float(values: list[float], shape: list[int]) -> NDArrayFloat:
    """Create an NDArrayFloat instance.

    Args:
        values (list[float]): The list of floating-point values in the array.
        shape (list[int]): The shape of the array, represented as a list of integers.

    Returns:
        NDArrayFloat: The created NDArrayFloat instance.
    """
    return NDArrayFloat(values=values, shape=shape)
