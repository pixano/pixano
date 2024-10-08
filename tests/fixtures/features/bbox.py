# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.dataset import Dataset
from pixano.features.schemas.annotations.bbox import BBox
from tests.utils.schema import register_schema


@pytest.fixture(scope="session")
def height_width():
    return 4, 6


@pytest.fixture(scope="session")
def coords():
    return {
        "xyxy": [1, 1, 3, 3],
        "xywh": [1, 1, 2, 2],
        "normalized_xyxy": [1 / 6, 1 / 4, 3 / 6, 3 / 4],
        "normalized_xywh": [1 / 6, 1 / 4, 2 / 6, 2 / 4],
    }


@pytest.fixture()
def bbox_xyxy(coords):
    return BBox.from_xyxy(coords["xyxy"], confidence=0.5, is_normalized=False)


@pytest.fixture()
def bbox_xywh(coords):
    return BBox.from_xywh(coords["xywh"], confidence=0.0, is_normalized=False)


@pytest.fixture(scope="session")
def bbox_difficult():
    class BBoxDifficult(BBox):
        is_difficult: bool

    register_schema(BBoxDifficult)
    return BBoxDifficult


@pytest.fixture(scope="session")
def two_difficult_bboxes_from_dataset_multiview_tracking_and_image(dataset_multi_view_tracking_and_image: Dataset):
    return dataset_multi_view_tracking_and_image.get_data("bbox_image", limit=2)
