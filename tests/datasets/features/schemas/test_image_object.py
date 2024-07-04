# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.datasets.features.schemas.image_object import ImageObject, create_image_object, is_image_object
from pixano.datasets.features.types.bbox import create_bbox
from pixano.datasets.features.types.compressed_rle import create_compressed_rle
from pixano.datasets.features.types.keypoints import create_keypoints
from tests.datasets.features.utils import make_tests_is_sublass_strict


def test_is_embedding():
    make_tests_is_sublass_strict(is_image_object, ImageObject)


def test_create_image_object():
    # Test 1: Default values
    image_object = create_image_object(
        item_id="item_id",
        view_id="view_id",
    )

    assert isinstance(image_object, ImageObject)
    assert image_object.item_id == "item_id"
    assert image_object.view_id == "view_id"
    assert isinstance(image_object.id, str)
    assert image_object.bbox.coords == [0, 0, 0, 0]
    assert image_object.bbox.confidence == -1.0
    assert image_object.bbox.format == "xywh"
    assert image_object.bbox.is_normalized
    assert image_object.mask.size == [0.0, 0.0]
    assert image_object.mask.counts == b""
    assert image_object.keypoints.template_id == "N/A"
    assert image_object.keypoints.coords == [0, 0]
    assert image_object.keypoints.states == ["invisible"]

    # Test 2: Custom values
    image_object = create_image_object(
        item_id="item_id",
        view_id="view_id",
        id="id",
        bbox=create_bbox(coords=[1, 1, 3, 3], confidence=0.5, format="xyxy", is_normalized=False),
        mask=create_compressed_rle(size=[4, 6], counts=b""),
        keypoints=create_keypoints(template_id="template_id", coords=[1, 1], states=["visible"]),
    )

    assert isinstance(image_object, ImageObject)
    assert image_object.item_id == "item_id"
    assert image_object.view_id == "view_id"
    assert image_object.id == "id"
    assert image_object.bbox.coords == [1, 1, 3, 3]
    assert image_object.bbox.confidence == 0.5
    assert image_object.bbox.format == "xyxy"
    assert not image_object.bbox.is_normalized
    assert image_object.mask.size == [4, 6]
    assert image_object.mask.counts == b""
    assert image_object.keypoints.template_id == "template_id"
    assert image_object.keypoints.coords == [1, 1]
    assert image_object.keypoints.states == ["visible"]
