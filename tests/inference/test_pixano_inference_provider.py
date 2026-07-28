# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Unit tests for the pixano-inference provider's boundary converters.

The pixano-inference server is stubbed with an in-process httpx `MockTransport`, so these run
with no network and no live model.
"""

import json

import httpx
import numpy as np
import pytest
from pixano_inference_client import PixanoInferenceClient

from pixano.inference.providers.pixano_inference import PixanoInferenceProvider
from pixano.inference.types import (
    EmbeddingInput,
    ImageMaskGenerationInput,
    InferenceTask,
    VideoMaskGenerationInput,
)


def _envelope(data: dict) -> dict:
    return {
        "id": "req-1",
        "status": "success",
        "timestamp": "2026-07-25T00:00:00",
        "processingTime": 0.5,
        "metadata": {},
        "data": data,
    }


def _ndarray_wire(arr: np.ndarray) -> dict:
    import base64

    contiguous = np.ascontiguousarray(arr.astype(np.float32))
    return {
        "shape": list(arr.shape),
        "dtype": "float32",
        "data": base64.b64encode(contiguous.tobytes()).decode("ascii"),
    }


def _provider_with_transport(handler) -> PixanoInferenceProvider:
    provider = PixanoInferenceProvider("http://test-server")
    provider._client = PixanoInferenceClient("http://test-server", transport=httpx.MockTransport(handler))
    return provider


@pytest.mark.asyncio
async def test_list_models_maps_capability_to_task():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200,
            json=[
                {"name": "sam2", "capability": "segmentation", "status": "RUNNING"},
                {"name": "clip", "capability": "embedding", "status": "RUNNING"},
            ],
        )

    provider = _provider_with_transport(handler)
    try:
        models = await provider.list_models()
        by_name = {m.name: m for m in models}
        assert by_name["sam2"].task == InferenceTask.MASK_GENERATION.value
        assert by_name["clip"].task == InferenceTask.EMBEDDING.value

        only_embed = await provider.list_models(task=InferenceTask.EMBEDDING)
        assert [m.name for m in only_embed] == ["clip"]
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_image_mask_generation_converts_payloads():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/inference/segmentation"
        data = {
            "masks": [[{"size": [4, 4], "counts": "abcd"}]],
            "scores": _ndarray_wire(np.array([0.9], dtype=np.float32)),
            "imageEmbedding": _ndarray_wire(np.zeros((2, 3), dtype=np.float32)),
        }
        return httpx.Response(200, json=_envelope(data))

    provider = _provider_with_transport(handler)
    try:
        result = await provider.image_mask_generation(
            ImageMaskGenerationInput(image="data:image/png;base64,AAAA", model="sam2", points=[[[1, 2]]], labels=[[1]])
        )
        assert result.status == "SUCCESS"
        assert len(result.data.masks) == 1 and len(result.data.masks[0]) == 1
        assert result.data.masks[0][0].size == [4, 4]
        assert result.data.scores.values == [pytest.approx(0.9)]
        assert result.data.image_embedding is not None
        assert result.data.image_embedding.shape == [2, 3]
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_video_mask_generation_box_is_converted_xyxy_to_xywh():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/inference/tracking"
        captured["body"] = json.loads(request.content)
        data = {"objectsIds": [1], "frameIndexes": [0], "masks": [{"size": [4, 4], "counts": "abcd"}]}
        return httpx.Response(200, json=_envelope(data))

    provider = _provider_with_transport(handler)
    try:
        result = await provider.video_mask_generation(
            VideoMaskGenerationInput(
                video=["data:image/png;base64,AAAA", "data:image/png;base64,AAAA"],
                model="sam2-video",
                objects_ids=[1],
                frame_indexes=[0],
                boxes=[[100, 100, 400, 300]],
            )
        )
        # xyxy [100,100,400,300] -> xywh {x:100, y:100, width:300, height:200}
        box = captured["body"]["keyframes"][0]["prompts"]["box"]
        assert box == {"x": 100, "y": 100, "width": 300, "height": 200}
        assert result.status == "SUCCESS"
        assert result.data.objects_ids == [1]
        assert result.data.frame_indexes == [0]
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_video_mask_generation_point_prompt_is_converted():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        data = {"objectsIds": [1], "frameIndexes": [0], "masks": [{"size": [4, 4], "counts": "abcd"}]}
        return httpx.Response(200, json=_envelope(data))

    provider = _provider_with_transport(handler)
    try:
        await provider.video_mask_generation(
            VideoMaskGenerationInput(
                video=["data:image/png;base64,AAAA"],
                model="sam2-video",
                objects_ids=[1],
                frame_indexes=[0],
                points=[[[320, 213]]],
                labels=[[1]],
            )
        )
        points = captured["body"]["keyframes"][0]["prompts"]["points"]
        assert points == [{"x": 320, "y": 213, "label": 1}]
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_embedding_returns_vector():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/inference/embedding"
        body = json.loads(request.content)
        assert body["text"] == "a photo of a cat"
        data = {"embeddings": _ndarray_wire(np.ones((1, 512), dtype=np.float32)), "dim": 512}
        return httpx.Response(200, json=_envelope(data))

    provider = _provider_with_transport(handler)
    try:
        result = await provider.embedding(EmbeddingInput(model="clip", text="a photo of a cat"))
        assert result.data.dim == 512
        assert result.data.embedding.shape == [1, 512]
        assert len(result.data.embedding.values) == 512
    finally:
        await provider.close()
