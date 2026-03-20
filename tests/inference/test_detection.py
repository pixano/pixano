# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os
from datetime import datetime
from pathlib import Path

import pytest

from pixano.features import (
    BBox,
    Classification,
    Entity,
    Image,
)
from pixano.inference.detection import detection
from pixano.inference.provider import InferenceProvider
from pixano.inference.types import (
    DetectionOutput,
    DetectionResult,
)


FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))
ASSETS_PATH = FILE_PATH.parent / "assets"


@pytest.fixture(scope="module")
def image_url() -> Image:
    image = Image(
        id="image",
        record_id="test_item",
        logical_name="image",
        uri="http://www.fake_url.com/coco_dataset/image/val/000000000139.png",
        width=640,
        height=426,
        format="png",
    )
    return image


@pytest.mark.asyncio
async def test_detection(
    simple_inference_provider: InferenceProvider,
    image_url: Image,
):
    response = DetectionResult(
        timestamp=datetime(year=2025, month=2, day=19),
        processing_time=1.0,
        metadata={"metadata": "value"},
        data=DetectionOutput(boxes=[[1, 2, 3, 4]], scores=[0.5], classes=["a cat"]),
    )

    expected_box = BBox(
        entity_id="test_entity",
        view_id="image",
        record_id="test_item",
        frame_id="image",
        source_type="model",
        source_name="test_source",
        coords=[1, 2, 3, 4],
        format="xyxy",
        is_normalized=False,
        confidence=0.5,
    )
    expected_classif = Classification(
        entity_id="test_entity",
        view_id="image",
        record_id="test_item",
        source_type="model",
        source_name="test_source",
        labels=["a cat"],
        confidences=[0.5],
    )

    simple_inference_provider.detection.return_value = response

    entity = Entity(id="test_entity")

    output = await detection(
        provider=simple_inference_provider,
        image=image_url,
        entity=entity,
        source_name="test_source",
        classes=["a cat", "a dog"],
    )

    exclude_keys = ["id", "created_at", "updated_at"]
    assert len(output) == 1
    assert len(output[0]) == 2
    assert output[0][0].model_dump(exclude=exclude_keys) == expected_box.model_dump(exclude=exclude_keys)
    assert output[0][1].model_dump(exclude=exclude_keys) == expected_classif.model_dump(exclude=exclude_keys)
