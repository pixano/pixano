# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.encoders import jsonable_encoder
from lancedb.pydantic import Vector
from pixano_inference.client import PixanoInferenceClient
from pixano_inference.pydantic import (
    CompressedRLE as PixanoInferenceCompressedRLE,
)
from pixano_inference.pydantic import (
    ImageZeroShotDetectionOutput,
    ImageZeroShotDetectionRequest,
    ImageZeroShotDetectionResponse,
)

from pixano.features import (
    BBox,
    Classification,
    Entity,
    EntityRef,
    Image,
    ItemRef,
    Source,
    SourceRef,
    ViewEmbedding,
    ViewRef,
)
from pixano.inference.zero_shot_detection import image_zero_shot_detection


FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))
ASSETS_PATH = FILE_PATH.parent / "assets"


@pytest.fixture(scope="module")
def image_url() -> Image:
    image = Image(
        id="image",
        item_ref=ItemRef(id="test_item"),
        url="http://www.fake_url.com/coco_dataset/image/val/000000000139.png",
        width=640,
        height=426,
        format="png",
    )
    image.table_name = "image"
    return image


@pytest.mark.asyncio
@patch("pixano_inference.client.PixanoInferenceClient.image_zero_shot_detection")
async def test_image_zero_shot_detection(
    mock_image_zero_shot_detection,
    simple_pixano_inference_client: PixanoInferenceClient,
    image_url: Image,
):
    response = ImageZeroShotDetectionResponse(
        id="id",
        status="SUCCESS",
        timestamp=datetime(year=2025, month=2, day=19),
        processing_time=1.0,
        metadata={"metadata": "value"},
        data=ImageZeroShotDetectionOutput(boxes=[[1, 2, 3, 4]], scores=[0.5], classes=["a cat"]),
    )

    expected_box = BBox(
        entity_ref=EntityRef(id="test_entity", name="entity"),
        view_ref=ViewRef(id="image", name="image"),
        item_ref=ItemRef(id="test_item"),
        source_ref=SourceRef(id="test_source"),
        coords=[1, 2, 3, 4],
        format="xyxy",
        is_normalized=False,
        confidence=0.5,
        inference_metadata={"timestamp": "2025-02-19T00:00:00", "processing_time": 1.0, "metadata": "value"},
    )
    expected_classif = Classification(
        entity_ref=EntityRef(id="test_entity", name="entity"),
        view_ref=ViewRef(id="image", name="image"),
        item_ref=ItemRef(id="test_item"),
        source_ref=SourceRef(id="test_source"),
        labels=["a cat"],
        confidences=[0.5],
        inference_metadata={"timestamp": "2025-02-19T00:00:00", "processing_time": 1.0, "metadata": "value"},
    )

    mock_image_zero_shot_detection.return_value = response

    entity = Entity(id="test_entity")
    entity.table_name = "entity"

    output = await image_zero_shot_detection(
        client=simple_pixano_inference_client,
        media_dir=Path("."),
        image=image_url,
        entity=entity,
        source=Source(id="test_source", name="test_source", kind="model"),
        classes=["a cat", "a dog"],
    )

    exclude_keys = ["id", "created_at", "updated_at"]
    assert len(output) == 1
    assert len(output[0]) == 2
    assert output[0][0].model_dump(exclude=exclude_keys) == expected_box.model_dump(exclude=exclude_keys)
    assert output[0][1].model_dump(exclude=exclude_keys) == expected_classif.model_dump(exclude=exclude_keys)
