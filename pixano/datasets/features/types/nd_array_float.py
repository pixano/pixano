import numpy as np
import pydantic

from .registry import _register_type_internal


@_register_type_internal
class NDArrayFloat(pydantic.BaseModel):
    """Represents an N-dimensional array of floating-point values.

    Attributes:
        values (list[float]): The list of floating-point values in the array.
        shape (list[int]): The shape of the array, represented as a list of integers.
    """

    values: list[float]
    shape: list[int]

    @classmethod
    def from_numpy(cls, arr: np.ndarray):
        """Create an instance of the class from a NumPy array.

        Args:
            arr (np.ndarray): The NumPy array to convert.

        Returns:
            cls: An instance of the class with values and shape derived from
                the input array.
        """
        return cls(values=arr.reshape(-1).tolist(), shape=list(arr.shape))
