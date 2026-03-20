# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import logging
import re
from typing import Annotated, Any
from urllib.parse import urlparse

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


class VideoTrackingRequest(BaseModel):
    model: str
    provider_name: str | None = None
    dataset_id: str
    record_id: str
    view_name: str
    start_frame_index: int = Field(ge=0)
    frame_count: int = Field(ge=1)
    objects_ids: list[int]
    prompt_frame_indexes: list[int]
    points: list[list[list[int]]] | None = None
    labels: list[list[int]] | None = None
    boxes: list[list[int]] | None = None


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
    dataset = _get_dataset(request.dataset_id, settings)
    image_bytes = _resolve_view_binary(dataset, request.view_id)
    provider = _get_provider(settings, request.provider_name)
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
    dataset = _get_dataset(request.dataset_id, settings)
    resolved_frames = _resolve_tracking_frames(
        dataset,
        record_id=request.record_id,
        view_name=request.view_name,
        start_frame_index=request.start_frame_index,
        frame_count=request.frame_count,
    )
    resolved_frame_indexes = [frame_index for frame_index, _ in resolved_frames]
    provider = _get_provider(settings, request.provider_name)
    input_data = TrackingInput(
        model=request.model,
        video=[blob_data for _, blob_data in resolved_frames],
        objects_ids=request.objects_ids,
        frame_indexes=_to_window_relative_indexes(request.prompt_frame_indexes, resolved_frame_indexes),
        points=request.points,
        labels=request.labels,
        boxes=request.boxes,
    )
    try:
        result = await provider.tracking(input_data=input_data)
    except InferenceError as exc:
        _raise_http_from_inference_error(exc)
    result.data.frame_indexes = _to_absolute_frame_indexes(
        result.data.frame_indexes,
        resolved_frame_indexes,
    )
    return _serialize_tracking_result(result)
