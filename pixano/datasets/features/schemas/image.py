# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info
import typing

from .registry import _register_schema_internal
from .view import View


@_register_schema_internal()
class Image(View):
    """Image Lance Model."""

    url: str
    width: int
    height: int
    format: str


def is_image(cls: typing.Any) -> bool:
    """Check if the given class is a subclass of Image.

    Args:
        cls (typing.Any): The class to check.

    Returns:
        bool: True if the class is a subclass of Image, False otherwise.
    """
    return cls is Image
