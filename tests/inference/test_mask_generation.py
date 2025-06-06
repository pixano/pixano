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
    ImageMaskGenerationOutput,
    ImageMaskGenerationResponse,
    VideoMaskGenerationOutput,
    VideoMaskGenerationResponse,
)

from pixano.features import (
    BBox,
    CompressedRLE,
    Entity,
    EntityRef,
    Image,
    ItemRef,
    NDArrayFloat,
    Source,
    SourceRef,
    ViewEmbedding,
    ViewRef,
)
from pixano.inference.mask_generation import image_mask_generation, video_mask_generation


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


class ViewEmbedding8(ViewEmbedding):
    vector: Vector(8)  # type: ignore
    shape: list[int] = [2, 4]


@pytest.mark.asyncio
@patch("pixano_inference.client.PixanoInferenceClient.image_mask_generation")
@pytest.mark.parametrize(
    "response, expected_output, image_embedding, high_resolution_features, bbox, points, labels",
    [
        (
            ImageMaskGenerationResponse(
                id="id",
                status="SUCCESS",
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={"metadata": "value"},
                data=ImageMaskGenerationOutput(
                    masks=[[PixanoInferenceCompressedRLE(size=[10, 2], counts=bytes([3, 4]))]],
                    scores=NDArrayFloat(values=[0.9], shape=[1]),
                    image_embedding=NDArrayFloat(values=[1], shape=[1]),
                    high_resolution_features=[NDArrayFloat(values=[1], shape=[1])],
                ),
            ),
            (
                CompressedRLE(
                    size=[10, 2],
                    counts=bytes([3, 4]),
                    entity_ref=EntityRef(id="test_entity", name="entity"),
                    view_ref=ViewRef(id="image", name="image"),
                    item_ref=ItemRef(id="test_item"),
                    source_ref=SourceRef(id="test_source"),
                    inference_metadata=jsonable_encoder(
                        {
                            "timestamp": datetime(year=2025, month=2, day=19),
                            "processing_time": 1.0,
                            "metadata": "value",
                        }
                    ),
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
            ImageMaskGenerationResponse(
                id="id",
                status="SUCCESS",
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={"metadata": "value"},
                data=ImageMaskGenerationOutput(
                    masks=[[PixanoInferenceCompressedRLE(size=[10, 2], counts=bytes([3, 4]))]],
                    scores=NDArrayFloat(values=[0.9], shape=[1]),
                    image_embedding=None,
                    high_resolution_features=None,
                ),
            ),
            (
                CompressedRLE(
                    size=[10, 2],
                    counts=bytes([3, 4]),
                    entity_ref=EntityRef(id="test_entity", name="entity"),
                    view_ref=ViewRef(id="image", name="image"),
                    item_ref=ItemRef(id="test_item"),
                    source_ref=SourceRef(id="test_source"),
                    inference_metadata=jsonable_encoder(
                        {
                            "timestamp": datetime(year=2025, month=2, day=19),
                            "processing_time": 1.0,
                            "metadata": "value",
                        }
                    ),
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
async def test_image_mask_generation(
    mock_image_mask_generation,
    simple_pixano_inference_client: PixanoInferenceClient,
    response: ImageMaskGenerationResponse,
    expected_output: tuple[CompressedRLE, float, NDArrayFloat | None, list[NDArrayFloat] | None],
    image_embedding: ViewEmbedding | None,
    high_resolution_features: list[ViewEmbedding] | None,
    bbox: BBox | None,
    points: list[list[int]] | None,
    labels: list[int],
    image_url: Image,
):
    mock_image_mask_generation.return_value = response

    entity = Entity(id="test_entity")
    entity.table_name = "entity"

    mask, score, out_image_embedding, out_high_resolution_features = await image_mask_generation(
        client=simple_pixano_inference_client,
        media_dir=Path("."),
        image=image_url,
        entity=entity,
        source=Source(id="test_source", name="test_source", kind="model"),
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
@patch("pixano_inference.client.PixanoInferenceClient.video_mask_generation")
@pytest.mark.parametrize(
    "response, expected_output, bbox, points, labels",
    [
        (
            VideoMaskGenerationResponse(
                id="id",
                status="SUCCESS",
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={"metadata": "value"},
                data=VideoMaskGenerationOutput(
                    masks=[PixanoInferenceCompressedRLE(size=[10, 2], counts=bytes([3, 4]))],
                    objects_ids=[0],
                    frame_indexes=[0],
                ),
            ),
            (
                CompressedRLE(
                    size=[10, 2],
                    counts=bytes([3, 4]),
                    entity_ref=EntityRef(id="test_entity", name="entity"),
                    view_ref=ViewRef(id="image", name="image"),
                    item_ref=ItemRef(id="test_item"),
                    source_ref=SourceRef(id="test_source"),
                    inference_metadata=jsonable_encoder(
                        {
                            "timestamp": datetime(year=2025, month=2, day=19),
                            "processing_time": 1.0,
                            "metadata": "value",
                        }
                    ),
                ),
                [0],
                [0],
            ),
            None,
            None,
            None,
        ),
        (
            VideoMaskGenerationResponse(
                id="id",
                status="SUCCESS",
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={"metadata": "value"},
                data=VideoMaskGenerationOutput(
                    masks=[PixanoInferenceCompressedRLE(size=[10, 2], counts=bytes([3, 4]))],
                    objects_ids=[0],
                    frame_indexes=[0],
                ),
            ),
            (
                CompressedRLE(
                    size=[10, 2],
                    counts=bytes([3, 4]),
                    entity_ref=EntityRef(id="test_entity", name="entity"),
                    view_ref=ViewRef(id="image", name="image"),
                    item_ref=ItemRef(id="test_item"),
                    source_ref=SourceRef(id="test_source"),
                    inference_metadata=jsonable_encoder(
                        {
                            "timestamp": datetime(year=2025, month=2, day=19),
                            "processing_time": 1.0,
                            "metadata": "value",
                        }
                    ),
                ),
                [0],
                [0],
            ),
            BBox(coords=[1, 2, 3, 4], is_normalized=False, format="xyxy"),
            [[1, 2]],
            [0],
        ),
        (
            VideoMaskGenerationResponse(
                id="id",
                status="SUCCESS",
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={"metadata": "value"},
                data=VideoMaskGenerationOutput(
                    masks=[PixanoInferenceCompressedRLE(size=[10, 2], counts=bytes([3, 4]))],
                    objects_ids=[0],
                    frame_indexes=[0],
                ),
            ),
            (
                CompressedRLE(
                    size=[10, 2],
                    counts=bytes([3, 4]),
                    entity_ref=EntityRef(id="test_entity", name="entity"),
                    view_ref=ViewRef(id="image", name="image"),
                    item_ref=ItemRef(id="test_item"),
                    source_ref=SourceRef(id="test_source"),
                    inference_metadata=jsonable_encoder(
                        {
                            "timestamp": datetime(year=2025, month=2, day=19),
                            "processing_time": 1.0,
                            "metadata": "value",
                        }
                    ),
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
async def test_video_mask_generation(
    mock_video_mask_generation,
    simple_pixano_inference_client: PixanoInferenceClient,
    response: ImageMaskGenerationResponse,
    expected_output: tuple[CompressedRLE, float, NDArrayFloat | None, list[NDArrayFloat] | None],
    bbox: BBox | None,
    points: list[list[int]] | None,
    labels: list[int],
    image_url: Image,
):
    mock_video_mask_generation.return_value = response

    entity = Entity(id="test_entity")
    entity.table_name = "entity"

    masks, objects_ids, frame_indexes = await video_mask_generation(
        client=simple_pixano_inference_client,
        media_dir=Path("."),
        video=[image_url],
        entity=entity,
        source=Source(id="test_source", name="test_source", kind="model"),
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
@patch("pixano_inference.client.PixanoInferenceClient.video_mask_generation")
async def test_error_video_mask_generation(
    simple_pixano_inference_client: PixanoInferenceClient,
):
    with pytest.raises(ValueError, match="Video format not currently supported, please use sequence frames."):
        await video_mask_generation(
            client=simple_pixano_inference_client,
            media_dir=Path("."),
            video="not a list",
            source=Source(id="test_source", name="test_source", kind="model"),
            bbox=None,
            points=None,
            labels=None,
        )
