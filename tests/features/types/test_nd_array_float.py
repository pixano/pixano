# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features.types.nd_array_float import NDArrayFloat, create_ndarray_float, is_ndarray_float
from tests.features.utils import make_tests_is_sublass_strict


def test_is_ndarray_float():
    make_tests_is_sublass_strict(is_ndarray_float, NDArrayFloat)


def test_create_ndarray_float():
    ndarray_float = create_ndarray_float(values=[1.0, 2.0, 3.0, 4.0], shape=[2, 2])
    assert isinstance(ndarray_float, NDArrayFloat)
    assert ndarray_float.values == [1.0, 2.0, 3.0, 4.0]
    assert ndarray_float.shape == [2, 2]
