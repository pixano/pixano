# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from pixano.datasets.features.types.bbox import BBox
from pixano.datasets.features.types.bbox3d import BBox3D
from pixano.datasets.features.utils import create_pixano_object, create_row

@pytest.mark.parametrize(
    "cls, kwargs",
    [
        (BBox, {"coords": [0, 0, 1, 1], "format": "xywh", "is_normalized": True, "confidence": 0.5}),
        BBox3D, {"position": [0, 0, 0, 0, 1, 1], "size": [1, 1, 1], "heading": 0.5},
        (CamCalibration)
    ]
)
def test_create_pixano_object(cls, kwargs):
    pixano_object = create_pixano_object(cls, **kwargs)
    assert isinstance(pixano_object, cls)
    for key, value in kwargs.items():
        assert getattr(pixano_object, key) == value
    assert isinstance(pixano_object.id, str)