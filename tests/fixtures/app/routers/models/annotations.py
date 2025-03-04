# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

import pytest

from pixano.app.models.annotations import AnnotationModel


@pytest.fixture(scope="session")
def two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image():
    return [
        AnnotationModel.model_validate(
            {
                "id": "bbox_image_0",
                "table_info": {"name": "bbox_image", "group": "annotations", "base_schema": "BBox"},
                "created_at": datetime(2021, 1, 1, 0, 0, 0),
                "updated_at": datetime(2021, 1, 1, 0, 0, 0),
                "data": {
                    "item_ref": {"name": "item", "id": "0"},
                    "view_ref": {"name": "image", "id": "image_0"},
                    "entity_ref": {"name": "entity_image", "id": "entity_image_0"},
                    "source_ref": {"id": "source_0", "name": "source"},
                    "coords": [0.0, 0.0, 0.0, 0.0],
                    "format": "xywh",
                    "is_normalized": False,
                    "confidence": 1.0,
                    "is_difficult": True,
                    "inference_metadata": {},
                },
            }
        ),
        AnnotationModel.model_validate(
            {
                "id": "bbox_image_1",
                "table_info": {"name": "bbox_image", "group": "annotations", "base_schema": "BBox"},
                "created_at": datetime(2021, 1, 1, 0, 0, 0),
                "updated_at": datetime(2021, 1, 1, 0, 0, 0),
                "data": {
                    "item_ref": {"name": "item", "id": "1"},
                    "view_ref": {"name": "image", "id": "image_1"},
                    "entity_ref": {"name": "entity_image", "id": "entity_image_1"},
                    "source_ref": {"id": "source_1", "name": "source"},
                    "coords": [1.0, 1.0, 25.0, 25.0],
                    "format": "xywh",
                    "is_normalized": False,
                    "confidence": 0.8,
                    "is_difficult": False,
                    "inference_metadata": {},
                },
            }
        ),
    ]
