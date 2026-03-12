# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

import pytest

from pixano.api.models import serialize_row
from pixano.schemas.annotations.bbox import BBox


@pytest.fixture(scope="session")
def bbox_difficult_for_api():
    class BBoxDifficult(BBox):
        is_difficult: bool

    return BBoxDifficult


@pytest.fixture(scope="session")
def two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image():
    return [
        {
            "table_name": "bbox_image",
            "id": "bbox_image_0",
            "created_at": datetime(2021, 1, 1, 0, 0, 0),
            "updated_at": datetime(2021, 1, 1, 0, 0, 0),
            "record_id": "0",
            "view_id": "image",
            "entity_id": "entity_image_0",
            "source_type": "model",
            "source_name": "source_0",
            "source_metadata": "{}",
            "coords": [0.0, 0.0, 0.0, 0.0],
            "format": "xywh",
            "is_normalized": False,
            "confidence": 1.0,
            "is_difficult": True,
        },
        {
            "table_name": "bbox_image",
            "id": "bbox_image_1",
            "created_at": datetime(2021, 1, 1, 0, 0, 0),
            "updated_at": datetime(2021, 1, 1, 0, 0, 0),
            "record_id": "1",
            "view_id": "image",
            "entity_id": "entity_image_1",
            "source_type": "human",
            "source_name": "source_1",
            "source_metadata": "{}",
            "coords": [1.0, 1.0, 25.0, 25.0],
            "format": "xywh",
            "is_normalized": False,
            "confidence": 0.8,
            "is_difficult": False,
        },
    ]
