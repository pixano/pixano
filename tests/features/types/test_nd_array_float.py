# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import numpy as np

from pixano.features.types.nd_array_float import NDArrayFloat, create_ndarray_float, is_ndarray_float
from tests.features.utils import make_tests_is_sublass_strict


class TestNDArrayFloat:
    def test_none(self):
        none_ndarray_float = NDArrayFloat.none()
        assert none_ndarray_float.values == [0.0]
        assert none_ndarray_float.shape == [1]

    def test_from_numpy(self):
        ndarray_float = NDArrayFloat.from_numpy(np.array([[1.0, 2.0], [3.0, 4.0]]))
        assert ndarray_float.values == [1.0, 2.0, 3.0, 4.0]
        assert ndarray_float.shape == [2, 2]


def test_is_ndarray_float():
    make_tests_is_sublass_strict(is_ndarray_float, NDArrayFloat)


def test_create_ndarray_float():
    ndarray_float = create_ndarray_float(values=[1.0, 2.0, 3.0, 4.0], shape=[2, 2])
    assert isinstance(ndarray_float, NDArrayFloat)
    assert ndarray_float.values == [1.0, 2.0, 3.0, 4.0]
    assert ndarray_float.shape == [2, 2]
