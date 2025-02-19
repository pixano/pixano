# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pixano_inference.pydantic import NDArrayFloat

from pixano.utils import issubclass_strict


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
