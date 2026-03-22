# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os
from datetime import datetime
from pathlib import Path

import pytest
from lancedb.pydantic import Vector

from pixano.features import (
    BBox,
    CompressedRLE,
    Entity,
    Image,
    NDArrayFloat,
    ViewEmbedding,
)
from pixano.inference.provider import InferenceProvider
from pixano.inference.segmentation import segmentation, tracking
from pixano.inference.types import (
    CompressedRLEData,
    NDArrayData,
    SegmentationOutput,
    SegmentationResult,
    TrackingOutput,
    TrackingResult,
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


class ViewEmbedding8(ViewEmbedding):
    vector: Vector(8)  # type: ignore
    shape: list[int] = [2, 4]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response, expected_output, image_embedding, high_resolution_features, bbox, points, labels",
    [
        (
            SegmentationResult(
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={"metadata": "value"},
                data=SegmentationOutput(
                    masks=[[CompressedRLEData(size=[10, 2], counts=bytes([3, 4]))]],
                    scores=NDArrayData(values=[0.9], shape=[1]),
                    image_embedding=NDArrayData(values=[1], shape=[1]),
                    high_resolution_features=[NDArrayData(values=[1], shape=[1])],
                ),
            ),
            (
                CompressedRLE(
                    size=[10, 2],
                    counts=bytes([3, 4]),
                    entity_id="test_entity",
                    view_id="image",
                    record_id="test_item",
                    frame_id="image",
                    source_type="model",
                    source_name="test_source",
                ),
                0.9,
                NDArrayFloat(values=[1], shape=[1]),
                [NDArrayFloat(values=[1], shape=[1])],
            ),
            None,
            None,
            None,
            None,
            None,
        ),
        (
            SegmentationResult(
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={"metadata": "value"},
                data=SegmentationOutput(
                    masks=[[CompressedRLEData(size=[10, 2], counts=bytes([3, 4]))]],
                    scores=NDArrayData(values=[0.9], shape=[1]),
                    image_embedding=None,
                    high_resolution_features=None,
                ),
            ),
            (
                CompressedRLE(
                    size=[10, 2],
                    counts=bytes([3, 4]),
                    entity_id="test_entity",
                    view_id="image",
                    record_id="test_item",
                    frame_id="image",
                    source_type="model",
                    source_name="test_source",
                ),
                0.9,
                None,
                None,
            ),
            ViewEmbedding8(vector=list(range(8))),
            [ViewEmbedding8(vector=list(range(8)))],
            BBox(coords=[1, 2, 3, 4], is_normalized=False, format="xyxy"),
            [[1, 2]],
            [0],
        ),
    ],
)
async def test_segmentation(
    simple_inference_provider: InferenceProvider,
    response: SegmentationResult,
    expected_output: tuple[CompressedRLE, float, NDArrayFloat | None, list[NDArrayFloat] | None],
    image_embedding: ViewEmbedding | None,
    high_resolution_features: list[ViewEmbedding] | None,
    bbox: BBox | None,
    points: list[list[int]] | None,
    labels: list[int],
    image_url: Image,
):
    simple_inference_provider.segmentation.return_value = response

    entity = Entity(id="test_entity")

    mask, score, out_image_embedding, out_high_resolution_features = await segmentation(
        provider=simple_inference_provider,
        image=image_url,
        entity=entity,
        source_name="test_source",
        image_embedding=image_embedding,
        high_resolution_features=high_resolution_features,
        bbox=bbox,
        points=points,
        labels=labels,
    )

    expected_mask, expected_score, expected_image_embedding, expected_high_resolution_features = expected_output

    exclude_keys = ["id", "created_at", "updated_at"]
    assert mask.model_dump(exclude=exclude_keys) == expected_mask.model_dump(exclude=exclude_keys)
    assert score == expected_score
    assert out_image_embedding == expected_image_embedding
    assert out_high_resolution_features == expected_high_resolution_features


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response, expected_output, bbox, points, labels",
    [
        (
            TrackingResult(
                status="SUCCESS",
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={"metadata": "value"},
                data=TrackingOutput(
                    masks=[CompressedRLEData(size=[10, 2], counts=bytes([3, 4]))],
                    objects_ids=[0],
                    frame_indexes=[0],
                ),
            ),
            (
                CompressedRLE(
                    size=[10, 2],
                    counts=bytes([3, 4]),
                    entity_id="test_entity",
                    view_id="image",
                    record_id="test_item",
                    frame_id="image",
                    source_type="model",
                    source_name="test_source",
                ),
                [0],
                [0],
            ),
            None,
            None,
            None,
        ),
        (
            TrackingResult(
                status="SUCCESS",
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={"metadata": "value"},
                data=TrackingOutput(
                    masks=[CompressedRLEData(size=[10, 2], counts=bytes([3, 4]))],
                    objects_ids=[0],
                    frame_indexes=[0],
                ),
            ),
            (
                CompressedRLE(
                    size=[10, 2],
                    counts=bytes([3, 4]),
                    entity_id="test_entity",
                    view_id="image",
                    record_id="test_item",
                    frame_id="image",
                    source_type="model",
                    source_name="test_source",
                ),
                [0],
                [0],
            ),
            BBox(coords=[1, 2, 3, 4], is_normalized=False, format="xyxy"),
            [[1, 2]],
            [0],
        ),
        (
            TrackingResult(
                status="SUCCESS",
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={"metadata": "value"},
                data=TrackingOutput(
                    masks=[CompressedRLEData(size=[10, 2], counts=bytes([3, 4]))],
                    objects_ids=[0],
                    frame_indexes=[0],
                ),
            ),
            (
                CompressedRLE(
                    size=[10, 2],
                    counts=bytes([3, 4]),
                    entity_id="test_entity",
                    view_id="image",
                    record_id="test_item",
                    frame_id="image",
                    source_type="model",
                    source_name="test_source",
                ),
                [0],
                [0],
            ),
            BBox(coords=[0.1, 0.2, 0.3, 0.4], is_normalized=True, format="xyxy"),
            [[1, 2]],
            [0],
        ),
    ],
)
async def test_tracking(
    simple_inference_provider: InferenceProvider,
    response: TrackingResult,
    expected_output: tuple[CompressedRLE, float, NDArrayFloat | None, list[NDArrayFloat] | None],
    bbox: BBox | None,
    points: list[list[int]] | None,
    labels: list[int],
    image_url: Image,
):
    simple_inference_provider.tracking.return_value = response

    entity = Entity(id="test_entity")

    masks, objects_ids, frame_indexes = await tracking(
        provider=simple_inference_provider,
        video=[image_url],
        entity=entity,
        source_name="test_source",
        bbox=bbox,
        points=points,
        labels=labels,
    )

    expected_mask, expected_objects_ids, expected_frame_indexes = expected_output

    exclude_keys = ["id", "created_at", "updated_at"]
    assert masks[0].model_dump(exclude=exclude_keys) == expected_mask.model_dump(exclude=exclude_keys)
    assert objects_ids == expected_objects_ids
    assert frame_indexes == expected_frame_indexes


@pytest.mark.asyncio
async def test_error_tracking(
    simple_inference_provider: InferenceProvider,
):
    with pytest.raises(ValueError, match="Video format not currently supported, please use sequence frames."):
        await tracking(
            provider=simple_inference_provider,
            video="not a list",
            source_name="test_source",
            bbox=None,
            points=None,
            labels=None,
        )
