# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from abc import ABC
from typing import ClassVar, Generic, TypeVar

import numpy as np
from pydantic import BaseModel, field_validator
from typing_extensions import Self

from pixano.utils import issubclass_strict


T = TypeVar("T")


class NDArray(BaseModel, Generic[T], ABC):
    """Represents an N-dimensional array.

    Attributes:
        values: The list of values.
        shape: The shape of the array, represented as a list of integers.
        np_dtype: The NumPy data type of the array.
    """

    values: list[T]
    shape: list[int]
    np_dtype: ClassVar[np.dtype]

    @field_validator("shape", mode="after")
    @classmethod
    def _validate_shape(cls, v: list[int]) -> list[int]:
        if len(v) < 1:
            raise ValueError("Shape must have at least one element.")
        elif any(s < 1 for s in v):
            raise ValueError("Shape elements must be positive.")
        return v

    @classmethod
    def from_numpy(cls, arr: np.ndarray) -> Self:
        """Create an instance from a NumPy array."""
        shape = list(arr.shape)
        arr = arr.astype(dtype=cls.np_dtype)
        return cls(values=arr.reshape(-1).tolist(), shape=shape)

    def to_numpy(self) -> np.ndarray:
        """Convert to a NumPy array."""
        return np.array(self.values, dtype=self.np_dtype).reshape(self.shape)


class NDArrayFloat(NDArray[float]):
    """N-dimensional array of 32-bit floating-point values."""

    np_dtype: ClassVar[np.dtype] = np.float32


def is_ndarray_float(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `NDArrayFloat` or a subclass of `NDArrayFloat`."""
    return issubclass_strict(cls, NDArrayFloat, strict)


def create_ndarray_float(values: list[float], shape: list[int]) -> NDArrayFloat:
    """Create a `NDArrayFloat` instance.

    Args:
        values: The list of floating-point values in the array.
        shape: The shape of the array, represented as a list of integers.

    Returns:
        The created `NDArrayFloat` instance.
    """
    return NDArrayFloat(values=values, shape=shape)
