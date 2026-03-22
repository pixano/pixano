# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Any, Literal
from urllib.parse import urlparse
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from pixano.api.settings import Settings, get_settings
from pixano.datasets import Dataset
from pixano.datasets.utils.errors import DatasetAccessError
from pixano.inference.exceptions import InferenceError, ProviderConnectionError
from pixano.inference.provider import InferenceProvider
from pixano.inference.providers.pixano_inference import PixanoInferenceProvider
from pixano.inference.types import (
    DetectionInput,
    InferenceTask,
    NDArrayData,
    SegmentationInput,
    TrackingInput,
    VLMInput,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inference", tags=["Inference"])
app_router = APIRouter(prefix="/app/inference", tags=["Inference"])
IMAGE_TABLE = "images"
SFRAME_TABLE = "sequence_frames"
TRACKING_JOB_TERMINAL_STATES = {"completed", "failed", "canceled"}


@dataclass
class TrackingJobRecord:
    provider_name: str
    provider_job_id: str
    resolved_frame_indexes: list[int]
    terminal_payload: dict[str, Any] | None = None


TRACKING_JOB_REGISTRY: dict[str, TrackingJobRecord] = {}


class ConnectedProviderResponse(BaseModel):
    name: str
    url: str | None = None


class InferenceRegistryResponse(BaseModel):
    connected: bool
    providers: list[ConnectedProviderResponse]
    default_provider: str | None = None


class ModelInfoResponse(BaseModel):
    name: str
    task: str
    provider_name: str
    model_path: str | None = None
    model_class: str | None = None


class RegisterServerRequest(BaseModel):
    url: str


class VLMRequest(BaseModel):
    model: str
    provider_name: str | None = None
    prompt: str | list[dict[str, Any]]
    images: list[str] | None = None
    max_new_tokens: int = 100
    temperature: float = 1.0


class DetectionRequest(BaseModel):
    model: str
    provider_name: str | None = None
    image: str
    classes: list[str] | str
    box_threshold: float = 0.5
    text_threshold: float = 0.5


class NDArrayRequest(BaseModel):
    values: list[float]
    shape: list[int]


class ImageSegmentationRequest(BaseModel):
    model: str
    provider_name: str | None = None
    dataset_id: str
    view_id: str
    image_embedding: NDArrayRequest | None = None
    high_resolution_features: list[NDArrayRequest] | None = None
    mask_input: NDArrayRequest | None = None
    reset_predictor: bool = True
    points: list[list[list[int]]] | None = None
    labels: list[list[int]] | None = None
    boxes: list[list[int]] | None = None
    num_multimask_outputs: int = 1
    multimask_output: bool = False
    return_image_embedding: bool = False
    return_logits: bool = False


class VideoTrackingIntervalRequest(BaseModel):
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    direction: Literal["forward", "backward"] = "forward"


class VideoTrackingPointPromptRequest(BaseModel):
    x: int
    y: int
    label: int = Field(ge=0, le=1)


class VideoTrackingBoxPromptRequest(BaseModel):
    x: int
    y: int
    width: int
    height: int


class VideoTrackingMaskPromptRequest(BaseModel):
    size: list[int]
    counts: str | list[int]


class VideoTrackingKeyframeRequest(BaseModel):
    frame_index: int = Field(ge=0)
    points: list[VideoTrackingPointPromptRequest] | None = None
    box: VideoTrackingBoxPromptRequest | None = None
    mask: VideoTrackingMaskPromptRequest | None = None


class VideoTrackingRequest(BaseModel):

    model: str
    provider_name: str | None = None
    dataset_id: str
    record_id: str
    view_name: str
    start_frame_index: int = Field(ge=0)
    frame_count: int = Field(ge=1)
    objects_ids: list[int]
    prompt_frame_indexes: list[int] = Field(default_factory=list)
    points: list[list[list[int]]] | None = None
    labels: list[list[int]] | None = None
    boxes: list[list[int]] | None = None
    propagate: bool = True
    interval: VideoTrackingIntervalRequest | None = None
    keyframes: list[VideoTrackingKeyframeRequest] | None = None


class VideoTrackingTaskOutputResponse(BaseModel):
    objects_ids: list[int]
    frame_indexes: list[int]
    masks: list[VideoTrackingMaskPromptRequest]


class VideoTrackingJobStatusResponse(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed", "canceled"]
    detail: str | None = None
    data: VideoTrackingTaskOutputResponse | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    timestamp: str | None = None
    processing_time: float = 0.0


def _normalize_provider_url(url: str) -> str:
    normalized_url = url.strip()
    parsed = urlparse(normalized_url)

    if not normalized_url or parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise HTTPException(status_code=400, detail="Invalid inference server URL")

    try:
        parsed.port
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid inference server URL") from exc

    return normalized_url


def _build_provider_name(url: str) -> str:
    parsed = urlparse(_normalize_provider_url(url))
    port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
    return f"pixano-inference@{parsed.hostname}:{port}"


def _list_connected_providers(settings: Settings) -> list[ConnectedProviderResponse]:
    providers: list[ConnectedProviderResponse] = []
    for name, provider in settings.inference_providers.items():
        providers.append(ConnectedProviderResponse(name=name, url=getattr(provider, "url", None)))
    return providers


def _get_default_provider(settings: Settings) -> InferenceProvider:
    if not settings.inference_providers or not settings.default_inference_provider:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    provider = settings.inference_providers.get(settings.default_inference_provider)
    if provider is None:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    return provider


def _get_provider(
    settings: Settings,
    provider_name: str | None = None,
) -> InferenceProvider:
    if provider_name:
        provider = settings.inference_providers.get(provider_name)
        if provider is None:
            raise HTTPException(status_code=404, detail=f"Unknown inference provider '{provider_name}'")
        return provider
    return _get_default_provider(settings)


def _get_provider_name(settings: Settings, provider_name: str | None = None) -> str:
    if provider_name:
        return provider_name
    if not settings.default_inference_provider:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    return settings.default_inference_provider


def _get_dataset(dataset_id: str, settings: Settings) -> Dataset:
    try:
        return Dataset.find(dataset_id, settings.library_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.") from exc


def _resolve_view_binary(dataset: Dataset, view_id: str) -> bytes:
    for table_name in (IMAGE_TABLE, SFRAME_TABLE):
        try:
            result = dataset.get_view_binary(table_name, view_id)
        except DatasetAccessError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if result is not None:
            blob_data, _ = result
            return blob_data

    raise HTTPException(
        status_code=404,
        detail=f"View '{view_id}' was not found or has no embedded binary content.",
    )


def _resolve_tracking_frames(
    dataset: Dataset,
    record_id: str,
    view_name: str,
    start_frame_index: int,
    frame_count: int,
) -> list[tuple[int, bytes]]:
    try:
        frames = dataset.get_temporal_view_batch(
            SFRAME_TABLE,
            record_id=record_id,
            view_name=view_name,
            start_frame=start_frame_index,
            batch_size=frame_count,
        )
    except DatasetAccessError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not frames:
        raise HTTPException(status_code=404, detail="No sequence frames found for the requested window.")

    resolved_frames = [(frame_index, blob_data) for frame_index, blob_data, _ in frames]
    if not all(blob_data for _, blob_data in resolved_frames):
        raise HTTPException(status_code=404, detail="One or more sequence frames have no embedded binary content.")
    return resolved_frames


def _to_window_relative_indexes(
    prompt_frame_indexes: list[int],
    resolved_frame_indexes: list[int],
) -> list[int]:
    index_lookup = {frame_index: offset for offset, frame_index in enumerate(resolved_frame_indexes)}
    missing = [frame_index for frame_index in prompt_frame_indexes if frame_index not in index_lookup]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Prompt frame indexes are outside the requested frame window: {missing}",
        )
    return [index_lookup[frame_index] for frame_index in prompt_frame_indexes]


def _to_absolute_frame_indexes(
    provider_frame_indexes: list[int],
    resolved_frame_indexes: list[int],
) -> list[int]:
    if all(0 <= frame_index < len(resolved_frame_indexes) for frame_index in provider_frame_indexes):
        return [resolved_frame_indexes[frame_index] for frame_index in provider_frame_indexes]

    if all(frame_index in resolved_frame_indexes for frame_index in provider_frame_indexes):
        return provider_frame_indexes

    raise HTTPException(
        status_code=500,
        detail=f"Tracking provider returned frame indexes outside the resolved window: {provider_frame_indexes}",
    )


def _serialize_tracking_keyframes(
    keyframes: list[VideoTrackingKeyframeRequest] | None,
    resolved_frame_indexes: list[int],
) -> tuple[list[int], list[dict[str, Any]] | None]:
    if not keyframes:
        return [], None

    absolute_indexes = [keyframe.frame_index for keyframe in keyframes]
    relative_indexes = _to_window_relative_indexes(absolute_indexes, resolved_frame_indexes)
    serialized: list[dict[str, Any]] = []

    for keyframe, relative_index in zip(keyframes, relative_indexes, strict=False):
        serialized_keyframe: dict[str, Any] = {"frame_index": relative_index}
        if keyframe.points is not None:
            serialized_keyframe["points"] = [point.model_dump() for point in keyframe.points]
        if keyframe.box is not None:
            serialized_keyframe["box"] = keyframe.box.model_dump()
        if keyframe.mask is not None:
            serialized_keyframe["mask"] = keyframe.mask.model_dump()
        serialized.append(serialized_keyframe)

    return absolute_indexes, serialized


def _derive_legacy_tracking_prompts(
    request: VideoTrackingRequest,
) -> tuple[list[list[list[int]]] | None, list[list[int]] | None, list[list[int]] | None]:
    if request.points is not None or request.labels is not None or request.boxes is not None:
        return request.points, request.labels, request.boxes

    if not request.keyframes:
        return None, None, None

    for keyframe in request.keyframes:
        points = (
            [[ [point.x, point.y] for point in keyframe.points ]]
            if keyframe.points
            else None
        )
        labels = ([[point.label for point in keyframe.points]] if keyframe.points else None)
        boxes = (
            [[
                keyframe.box.x,
                keyframe.box.y,
                keyframe.box.x + keyframe.box.width,
                keyframe.box.y + keyframe.box.height,
            ]]
            if keyframe.box is not None
            else None
        )
        if points is not None or boxes is not None or keyframe.mask is not None:
            return points, labels, boxes

    return None, None, None


def _serialize_tracking_interval(
    interval: VideoTrackingIntervalRequest | None,
    resolved_frame_indexes: list[int],
) -> dict[str, Any] | None:
    if interval is None:
        return None

    relative_start, relative_end = _to_window_relative_indexes(
        [interval.start_frame, interval.end_frame],
        resolved_frame_indexes,
    )
    return {
        "start_frame": relative_start,
        "end_frame": relative_end,
        "direction": interval.direction,
    }


def _parse_ndarray_request(array: NDArrayRequest | None) -> NDArrayData | None:
    if array is None:
        return None
    return NDArrayData(values=array.values, shape=array.shape)


def _parse_ndarray_request_list(
    arrays: list[NDArrayRequest] | None,
) -> list[NDArrayData] | None:
    if arrays is None:
        return None
    return [_parse_ndarray_request(array) for array in arrays if array is not None]


def _serialize_model_info(model: Any, provider_name: str) -> dict[str, Any]:
    return {
        "name": model.name,
        "task": model.capability,
        "provider_name": provider_name,
        "model_path": model.model_path,
        "model_class": model.model_class,
    }


async def _get_model_capability(
    provider: InferenceProvider,
    model_name: str,
) -> str | None:
    try:
        models = await provider.list_models()
    except Exception:
        models = []

    for model in models:
        if getattr(model, "name", None) == model_name:
            return getattr(model, "capability", None)

    try:
        server_info = await provider.get_server_info()
    except Exception:
        return None

    return server_info.models_to_capability.get(model_name)


async def _ensure_model_capability(
    provider: InferenceProvider,
    model_name: str,
    expected_capability: InferenceTask,
) -> None:
    actual_capability = await _get_model_capability(provider, model_name)
    if actual_capability is None or actual_capability == expected_capability.value:
        return

    raise HTTPException(
        status_code=400,
        detail=(
            f"Model '{model_name}' is {actual_capability}-only; "
            f"use /inference/{actual_capability}"
        ),
    )


def _serialize_segmentation_result(result: Any) -> dict[str, Any]:
    return {
        "data": {
            "masks": [[mask.to_dict() for mask in prompt_masks] for prompt_masks in result.data.masks],
            "scores": result.data.scores.to_dict(),
            "image_embedding": result.data.image_embedding.to_dict()
            if result.data.image_embedding is not None
            else None,
            "high_resolution_features": [feature.to_dict() for feature in result.data.high_resolution_features]
            if result.data.high_resolution_features is not None
            else None,
            "mask_logits": result.data.mask_logits.to_dict() if result.data.mask_logits is not None else None,
        },
        "timestamp": result.timestamp.isoformat(),
        "processing_time": result.processing_time,
        "metadata": result.metadata,
        "id": result.id,
        "status": result.status,
    }


def _serialize_tracking_result(result: Any) -> dict[str, Any]:
    return {
        "data": {
            "objects_ids": result.data.objects_ids,
            "frame_indexes": result.data.frame_indexes,
            "masks": [mask.to_dict() for mask in result.data.masks],
        },
        "timestamp": result.timestamp.isoformat(),
        "processing_time": result.processing_time,
        "metadata": result.metadata,
        "id": result.id,
        "status": result.status,
    }


def _serialize_tracking_job_status(
    result: Any,
    *,
    job_id: str,
    resolved_frame_indexes: list[int] | None = None,
) -> dict[str, Any]:
    data = None
    if getattr(result, "data", None) is not None:
        frame_indexes = result.data.frame_indexes
        if resolved_frame_indexes is not None:
            frame_indexes = _to_absolute_frame_indexes(frame_indexes, resolved_frame_indexes)
        data = {
            "objects_ids": result.data.objects_ids,
            "frame_indexes": frame_indexes,
            "masks": [mask.to_dict() for mask in result.data.masks],
        }

    timestamp = getattr(result, "timestamp", None)
    return {
        "job_id": job_id,
        "status": result.status,
        "detail": getattr(result, "detail", None),
        "data": data,
        "metadata": getattr(result, "metadata", {}) or {},
        "timestamp": timestamp.isoformat() if isinstance(timestamp, datetime) else None,
        "processing_time": getattr(result, "processing_time", 0.0),
    }


def _serialize_vlm_result(result: Any) -> dict[str, Any]:
    return {
        "data": {
            "generated_text": result.data.generated_text,
            "usage": {
                "prompt_tokens": result.data.usage.prompt_tokens,
                "completion_tokens": result.data.usage.completion_tokens,
                "total_tokens": result.data.usage.total_tokens,
            },
            "generation_config": result.data.generation_config,
        },
        "timestamp": result.timestamp.isoformat(),
        "processing_time": result.processing_time,
        "metadata": result.metadata,
        "id": result.id,
        "status": result.status,
    }


def _serialize_detection_result(result: Any) -> dict[str, Any]:
    return {
        "data": {
            "boxes": result.data.boxes,
            "scores": result.data.scores,
            "classes": result.data.classes,
        },
        "timestamp": result.timestamp.isoformat(),
        "processing_time": result.processing_time,
        "metadata": result.metadata,
        "id": result.id,
        "status": result.status,
    }


def _raise_http_from_inference_error(exc: InferenceError) -> None:
    message = str(exc)
    status_match = re.match(r"HTTP (\d{3}): .*?(?: - (?P<detail>.*))?$", message)
    if status_match:
        detail = status_match.group("detail") or message
        raise HTTPException(status_code=int(status_match.group(1)), detail=detail) from exc
    raise HTTPException(status_code=502, detail=message) from exc


def _build_tracking_input(
    request: VideoTrackingRequest,
    settings: Settings,
) -> tuple[TrackingInput, list[int]]:
    dataset = _get_dataset(request.dataset_id, settings)
    resolved_frames = _resolve_tracking_frames(
        dataset,
        record_id=request.record_id,
        view_name=request.view_name,
        start_frame_index=request.start_frame_index,
        frame_count=request.frame_count,
    )
    resolved_frame_indexes = [frame_index for frame_index, _ in resolved_frames]
    prompt_frame_indexes = request.prompt_frame_indexes
    serialized_keyframes: list[dict[str, Any]] | None = None
    if request.keyframes:
        prompt_frame_indexes, serialized_keyframes = _serialize_tracking_keyframes(
            request.keyframes,
            resolved_frame_indexes,
        )
    points, labels, boxes = _derive_legacy_tracking_prompts(request)
    input_data = TrackingInput(
        model=request.model,
        video=[blob_data for _, blob_data in resolved_frames],
        objects_ids=request.objects_ids,
        frame_indexes=_to_window_relative_indexes(prompt_frame_indexes, resolved_frame_indexes),
        points=points,
        labels=labels,
        boxes=boxes,
        propagate=request.propagate,
        interval=_serialize_tracking_interval(request.interval, resolved_frame_indexes),
        keyframes=serialized_keyframes,
    )
    return input_data, resolved_frame_indexes


@app_router.get("/servers/", response_model=InferenceRegistryResponse, operation_id="list_inference_servers")
def list_inference_servers(
    settings: Annotated[Settings, Depends(get_settings)],
) -> InferenceRegistryResponse:
    providers = _list_connected_providers(settings)
    return InferenceRegistryResponse(
        connected=len(providers) > 0,
        providers=providers,
        default_provider=settings.default_inference_provider,
    )


@app_router.post("/servers/", operation_id="register_inference_server")
async def register_inference_server(
    request: RegisterServerRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    normalized_url = _normalize_provider_url(request.url)

    try:
        provider = await PixanoInferenceProvider.connect(normalized_url)
    except ProviderConnectionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    provider_name = _build_provider_name(normalized_url)
    settings.inference_providers[provider_name] = provider
    settings.default_inference_provider = provider_name

    return {
        "status": "ok",
        "provider": ConnectedProviderResponse(name=provider_name, url=getattr(provider, "url", None)).model_dump(),
        "default_provider": settings.default_inference_provider,
    }


@app_router.get("/models/", response_model=list[ModelInfoResponse], operation_id="list_inference_models")
async def list_inference_models(
    settings: Annotated[Settings, Depends(get_settings)],
    task: Annotated[str | None, Query()] = None,
) -> list[dict[str, Any]]:
    if not settings.inference_providers:
        return []

    try:
        inference_task = InferenceTask(task) if task else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Unsupported inference task '{task}'") from exc
    result: list[dict[str, Any]] = []
    for provider_name, provider in settings.inference_providers.items():
        try:
            models = await provider.list_models(task=inference_task)
            result.extend(_serialize_model_info(model, provider_name) for model in models)
        except TypeError:
            # Some test doubles do not expose the optional enum filtering; fall back to no filtering.
            models = await provider.list_models()
            filtered_models = [model for model in models if task is None or model.capability == task]
            result.extend(_serialize_model_info(model, provider_name) for model in filtered_models)
        except Exception:
            logger.warning("Failed to list models from provider %s", provider_name, exc_info=True)
    return result


@router.post("/vlm", operation_id="vlm")
async def vlm(
    request: VLMRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    provider = _get_provider(settings, request.provider_name)
    input_data = VLMInput(
        model=request.model,
        prompt=request.prompt,
        images=request.images,
        max_new_tokens=request.max_new_tokens,
        temperature=request.temperature,
    )
    result = await provider.vlm(input_data=input_data)
    return _serialize_vlm_result(result)


@router.post("/detection", operation_id="detect")
async def detect(
    request: DetectionRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    provider = _get_provider(settings, request.provider_name)
    input_data = DetectionInput(
        model=request.model,
        image=request.image,
        classes=request.classes,
        box_threshold=request.box_threshold,
        text_threshold=request.text_threshold,
    )
    result = await provider.detection(input_data=input_data)
    return _serialize_detection_result(result)


@router.post("/segmentation", operation_id="segment_image")
async def segment_image(
    request: ImageSegmentationRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    provider = _get_provider(settings, request.provider_name)
    await _ensure_model_capability(provider, request.model, InferenceTask.SEGMENTATION)
    dataset = _get_dataset(request.dataset_id, settings)
    image_bytes = _resolve_view_binary(dataset, request.view_id)
    input_data = SegmentationInput(
        model=request.model,
        image=image_bytes,
        image_embedding=_parse_ndarray_request(request.image_embedding),
        high_resolution_features=_parse_ndarray_request_list(request.high_resolution_features),
        mask_input=_parse_ndarray_request(request.mask_input),
        reset_predictor=request.reset_predictor,
        points=request.points,
        labels=request.labels,
        boxes=request.boxes,
        num_multimask_outputs=request.num_multimask_outputs,
        multimask_output=request.multimask_output,
        return_image_embedding=request.return_image_embedding,
        return_logits=request.return_logits,
    )
    try:
        result = await provider.segmentation(input_data=input_data)
    except InferenceError as exc:
        _raise_http_from_inference_error(exc)
    return _serialize_segmentation_result(result)


@router.post("/tracking", operation_id="track_video")
async def track_video(
    request: VideoTrackingRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    provider = _get_provider(settings, request.provider_name)
    await _ensure_model_capability(provider, request.model, InferenceTask.TRACKING)
    input_data, resolved_frame_indexes = _build_tracking_input(request, settings)
    try:
        result = await provider.tracking(input_data=input_data)
    except InferenceError as exc:
        _raise_http_from_inference_error(exc)
    result.data.frame_indexes = _to_absolute_frame_indexes(
        result.data.frame_indexes,
        resolved_frame_indexes,
    )
    return _serialize_tracking_result(result)


@router.post(
    "/tracking/jobs",
    response_model=VideoTrackingJobStatusResponse,
    operation_id="submit_tracking_job",
)
async def submit_tracking_job(
    request: VideoTrackingRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    provider_name = _get_provider_name(settings, request.provider_name)
    provider = _get_provider(settings, provider_name)
    await _ensure_model_capability(provider, request.model, InferenceTask.TRACKING)
    input_data, resolved_frame_indexes = _build_tracking_input(request, settings)

    try:
        provider_status = await provider.submit_tracking_job(input_data=input_data)
    except InferenceError as exc:
        _raise_http_from_inference_error(exc)

    job_id = f"tracking-job-{uuid4().hex}"
    payload = _serialize_tracking_job_status(
        provider_status,
        job_id=job_id,
        resolved_frame_indexes=resolved_frame_indexes,
    )
    record = TrackingJobRecord(
        provider_name=provider_name,
        provider_job_id=provider_status.job_id,
        resolved_frame_indexes=resolved_frame_indexes,
        terminal_payload=payload if provider_status.status in TRACKING_JOB_TERMINAL_STATES else None,
    )
    TRACKING_JOB_REGISTRY[job_id] = record
    return payload


@router.get(
    "/tracking/jobs/{job_id}",
    response_model=VideoTrackingJobStatusResponse,
    operation_id="get_tracking_job",
)
async def get_tracking_job_status(
    job_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    record = TRACKING_JOB_REGISTRY.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Tracking job '{job_id}' was not found.")

    if record.terminal_payload is not None:
        return record.terminal_payload

    provider = _get_provider(settings, record.provider_name)
    try:
        provider_status = await provider.get_tracking_job(record.provider_job_id)
    except InferenceError as exc:
        _raise_http_from_inference_error(exc)

    payload = _serialize_tracking_job_status(
        provider_status,
        job_id=job_id,
        resolved_frame_indexes=record.resolved_frame_indexes,
    )
    if provider_status.status in TRACKING_JOB_TERMINAL_STATES:
        record.terminal_payload = payload
    return payload


@router.delete(
    "/tracking/jobs/{job_id}",
    response_model=VideoTrackingJobStatusResponse,
    operation_id="cancel_tracking_job",
)
async def cancel_tracking_job_status(
    job_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    record = TRACKING_JOB_REGISTRY.get(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Tracking job '{job_id}' was not found.")

    if record.terminal_payload is not None:
        return record.terminal_payload

    provider = _get_provider(settings, record.provider_name)
    canceled_payload = {
        "job_id": job_id,
        "status": "canceled",
        "detail": "Tracking job canceled.",
        "data": None,
        "metadata": {},
        "timestamp": None,
        "processing_time": 0.0,
    }

    try:
        provider_status = await provider.cancel_tracking_job(record.provider_job_id)
    except InferenceError:
        logger.warning("Failed to cancel provider tracking job %s", record.provider_job_id, exc_info=True)
    else:
        canceled_payload = _serialize_tracking_job_status(provider_status, job_id=job_id)
        canceled_payload["status"] = "canceled"
        canceled_payload["data"] = None

    record.terminal_payload = canceled_payload
    return canceled_payload
