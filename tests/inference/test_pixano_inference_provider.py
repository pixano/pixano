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
from pixano_inference.client import PixanoInferenceClient

from pixano.inference.exceptions import InferenceRequestError
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
async def test_list_models_passes_the_interface_through_in_snake_case():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200,
            json=[
                {
                    "name": "sam2-video",
                    "capability": "tracking",
                    "modelClass": "Sam2VideoModel",
                    "modelPath": "facebook/sam2-hiera-tiny",
                    "status": "RUNNING",
                    "interface": {
                        "capability": "tracking",
                        "prompts": ["points", "box", "mask"],
                        "promptFree": False,
                        "classes": "none",
                        "classNames": None,
                        "thresholds": [],
                        "interval": True,
                        "outputs": ["mask"],
                    },
                },
                {"name": "yolo-bytetrack", "capability": "tracking", "status": "RUNNING"},
            ],
        )

    provider = _provider_with_transport(handler)
    try:
        by_name = {m.name: m for m in await provider.list_models()}
        assert by_name["sam2-video"].interface == {
            "capability": "tracking",
            "prompts": ["points", "box", "mask"],
            "prompt_free": False,
            "classes": "none",
            "class_names": None,
            "thresholds": [],
            "interval": True,
            "outputs": ["mask"],
        }
        assert by_name["sam2-video"].model_class == "Sam2VideoModel"
        assert by_name["sam2-video"].model_path == "facebook/sam2-hiera-tiny"
        # A server that does not publish it (0.7.0) leaves it unknown rather than guessed.
        assert by_name["yolo-bytetrack"].interface is None
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_get_server_info_maps_models_to_tasks():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v1/info":
            return httpx.Response(200, json={"appVersion": "0.7.1"})
        assert request.url.path == "/v1/models"
        return httpx.Response(
            200,
            json=[
                {"name": "sam2-video", "capability": "tracking", "status": "RUNNING"},
                {"name": "clip", "capability": "embedding", "status": "RUNNING"},
                {"name": "mystery", "capability": "not-a-capability", "status": "RUNNING"},
            ],
        )

    provider = _provider_with_transport(handler)
    try:
        info = await provider.get_server_info()
        assert info.version == "0.7.1"
        assert info.models == ["sam2-video", "clip"]
        assert info.models_to_task == {"sam2-video": "video_mask_generation", "clip": "embedding"}
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


_FRAME = "data:image/png;base64,AAAA"
_MASK_WIRE = {"size": [4, 4], "counts": "abcd"}


def _job_wire(status: str, data: dict | None, job_id: str = "job-1") -> dict:
    """A `/v1/jobs` status envelope, keys deliberately camelCase as the server writes them."""
    return {
        "jobId": job_id,
        "status": status,
        "detail": None,
        "data": data,
        "metadata": {"backend": "stub"},
        "timestamp": "2026-07-25T00:00:00",
        "processingTime": 0.2,
    }


@pytest.mark.asyncio
async def test_video_mask_generation_box_is_converted_xyxy_to_xywh():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/inference/tracking"
        captured["body"] = json.loads(request.content)
        # The 0.7 output: for each frame, the objects tracked in it (camelCase on the wire).
        data = {"frames": [{"frameIndex": 0, "objects": [{"trackId": 1, "mask": _MASK_WIRE}]}]}
        return httpx.Response(200, json=_envelope(data))

    provider = _provider_with_transport(handler)
    try:
        result = await provider.video_mask_generation(
            VideoMaskGenerationInput(
                video=[_FRAME, _FRAME],
                model="sam2-video",
                objects_ids=[1],
                frame_indexes=[0],
                boxes=[[100, 100, 400, 300]],
            )
        )
        # xyxy [100,100,400,300] -> xywh {x:100, y:100, width:300, height:200}
        box = captured["body"]["keyframes"][0]["prompts"]["box"]
        assert box == {"x": 100, "y": 100, "width": 300, "height": 200}
        assert captured["body"]["objectsIds"] == [1]
        assert result.status == "SUCCESS"
        assert [frame.frame_index for frame in result.data.frames] == [0]
        tracked = result.data.frames[0].objects[0]
        assert tracked.track_id == 1
        assert tracked.mask is not None
        assert tracked.mask.size == [4, 4]
        assert tracked.mask.counts == b"abcd"
        assert (tracked.box, tracked.score, tracked.class_name) == (None, None, None)
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_video_mask_generation_point_prompt_is_converted():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        data = {"frames": [{"frameIndex": 0, "objects": [{"trackId": 1, "mask": _MASK_WIRE}]}]}
        return httpx.Response(200, json=_envelope(data))

    provider = _provider_with_transport(handler)
    try:
        await provider.video_mask_generation(
            VideoMaskGenerationInput(
                video=[_FRAME],
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
async def test_video_mask_generation_parses_boxes_scores_and_classes():
    def handler(request: httpx.Request) -> httpx.Response:
        # A tracking-by-detection model: boxes with a score and a class, no mask; a frame may be empty.
        data = {
            "frames": [
                {"frameIndex": 0, "objects": [{"trackId": 4, "box": [1, 2, 3, 4], "score": 0.9, "class": "car"}]},
                {"frameIndex": 1, "objects": []},
            ]
        }
        return httpx.Response(200, json=_envelope(data))

    provider = _provider_with_transport(handler)
    try:
        result = await provider.video_mask_generation(
            VideoMaskGenerationInput(video=[_FRAME, _FRAME], model="yolo-bytetrack", classes=["car"])
        )
        tracked = result.data.frames[0].objects[0]
        assert tracked.track_id == 4
        assert tracked.box == [1.0, 2.0, 3.0, 4.0]
        assert tracked.score == 0.9
        assert tracked.class_name == "car"
        assert tracked.mask is None
        assert result.data.frames[1].frame_index == 1
        assert result.data.frames[1].objects == []
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_prompt_free_request_names_no_object_and_passes_classes():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_envelope({"frames": []}))

    provider = _provider_with_transport(handler)
    try:
        await provider.video_mask_generation(
            VideoMaskGenerationInput(video=[_FRAME], model="yolo-bytetrack", classes=["person"], box_threshold=0.4)
        )
        body = captured["body"]
        assert body["objectsIds"] == []
        assert body["frameIndexes"] == []
        assert body["keyframes"] is None  # an empty list would count as prompts
        assert body["classes"] == ["person"]
        assert body["boxThreshold"] == 0.4
    finally:
        await provider.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "input_data",
    [
        pytest.param(
            VideoMaskGenerationInput(
                video=[_FRAME],
                model="sam2-video",
                keyframes=[{"frame_index": 0, "points": [{"x": 1, "y": 2, "label": 1}]}],
            ),
            id="prompts-without-object-ids",
        ),
        pytest.param(
            VideoMaskGenerationInput(
                video=[_FRAME],
                model="sam2-video",
                objects_ids=[1, 2],
                frame_indexes=[0, 0],
                keyframes=[{"frame_index": 0, "points": [{"x": 1, "y": 2, "label": 1}]}],
            ),
            id="one-keyframe-for-two-objects",
        ),
        pytest.param(
            VideoMaskGenerationInput(video=[_FRAME], model="sam2-video", objects_ids=[1], frame_indexes=[0]),
            id="object-without-any-prompt",
        ),
    ],
)
async def test_inconsistent_prompts_are_rejected_before_any_request(input_data: VideoMaskGenerationInput):
    def handler(request: httpx.Request) -> httpx.Response:
        raise AssertionError("an inconsistent request must not be sent")

    provider = _provider_with_transport(handler)
    try:
        with pytest.raises(InferenceRequestError) as excinfo:
            await provider.video_mask_generation(input_data)
        assert excinfo.value.status_code == 422
        assert excinfo.value.code == "invalid_request"
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_video_mask_generation_rejects_unexpected_response_shape():
    def handler(request: httpx.Request) -> httpx.Response:
        legacy = {"objectsIds": [1], "frameIndexes": [0], "masks": [_MASK_WIRE]}  # the 0.6 shape
        return httpx.Response(200, json=_envelope(legacy))

    provider = _provider_with_transport(handler)
    try:
        with pytest.raises(InferenceRequestError) as excinfo:
            await provider.video_mask_generation(
                VideoMaskGenerationInput(
                    video=[_FRAME], model="sam2-video", objects_ids=[1], frame_indexes=[0], boxes=[[0, 0, 2, 2]]
                )
            )
        assert excinfo.value.status_code == 502
        assert excinfo.value.code == "invalid_response"
    finally:
        await provider.close()


@pytest.mark.asyncio
async def test_tracking_job_parses_frame_grouped_data():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            assert request.url.path == "/v1/inference/tracking/jobs"
            return httpx.Response(202, json=_job_wire("running", None))
        assert request.url.path == "/v1/jobs/job-1"
        data = {"frames": [{"frameIndex": 1, "objects": [{"trackId": 7, "mask": _MASK_WIRE}]}]}
        return httpx.Response(200, json=_job_wire("completed", data))

    provider = _provider_with_transport(handler)
    try:
        submitted = await provider.submit_video_mask_generation_job(
            VideoMaskGenerationInput(
                video=[_FRAME, _FRAME], model="sam2-video", objects_ids=[7], frame_indexes=[0], boxes=[[0, 0, 2, 2]]
            )
        )
        assert (submitted.job_id, submitted.status, submitted.data) == ("job-1", "running", None)

        done = await provider.get_video_mask_generation_job("job-1")
        assert done.status == "completed"
        assert [frame.frame_index for frame in done.data.frames] == [1]
        tracked = done.data.frames[0].objects[0]
        assert tracked.track_id == 7
        assert tracked.mask is not None
        assert tracked.mask.counts == b"abcd"
        assert done.metadata == {"backend": "stub"}
        assert done.processing_time == 0.2
    finally:
        await provider.close()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "data",
    [
        pytest.param({"objectsIds": [7], "frameIndexes": [0], "masks": [_MASK_WIRE]}, id="0.6-flat-shape"),
        pytest.param({}, id="no-frames"),
        pytest.param(None, id="completed-without-result"),
    ],
)
async def test_tracking_job_result_in_unexpected_shape_is_an_error(data: dict | None):
    # Before 0.7 support, an unknown job payload was read as an empty result; it must be an error.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_job_wire("completed", data))

    provider = _provider_with_transport(handler)
    try:
        with pytest.raises(InferenceRequestError) as excinfo:
            await provider.get_video_mask_generation_job("job-1")
        assert excinfo.value.status_code == 502
        assert excinfo.value.code == "invalid_response"
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
