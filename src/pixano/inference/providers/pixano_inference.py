# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Provider backed by a pixano-inference `/v1` server, via `pixano-inference-client`.

Translates between Pixano's inference types and the client's wire models. The ML models run on
the pixano-inference server; this process only speaks HTTP through the client.
"""

from typing import Any

import numpy as np
from pixano_inference_client import (
    CompressedRLE,
    DetectionRequest,
    EmbeddingRequest,
    NDArrayFloat,
    PixanoInferenceClient,
    PixanoInferenceError,
    SegmentationRequest,
    TrackingBoxPrompt,
    TrackingInterval,
    TrackingKeyframeV1,
    TrackingPointPrompt,
    TrackingPrompts,
    TrackingRequestV1,
    VLMRequest,
)

from ..exceptions import InferenceRequestError, ProviderConnectionError
from ..media import bytes_to_data_uri
from ..provider import InferenceProvider
from ..registry import register_provider
from ..types import (
    CAPABILITY_TO_TASK,
    CompressedRLEData,
    DetectionInput,
    DetectionOutput,
    DetectionResult,
    EmbeddingInput,
    EmbeddingOutput,
    EmbeddingResult,
    ImageMaskGenerationInput,
    ImageMaskGenerationOutput,
    ImageMaskGenerationResult,
    InferenceTask,
    ModelInfo,
    NDArrayData,
    ServerInfo,
    UsageInfo,
    VideoMaskGenerationInput,
    VideoMaskGenerationJobStatus,
    VideoMaskGenerationOutput,
    VideoMaskGenerationResult,
    VLMInput,
    VLMOutput,
    VLMResult,
)


# --- Boundary converters -----------------------------------------------------


def _ndarray_to_data(array: NDArrayFloat) -> NDArrayData:
    arr = array.to_numpy()
    return NDArrayData(values=arr.ravel().tolist(), shape=list(arr.shape))


def _data_to_ndarray(data: NDArrayData) -> NDArrayFloat:
    arr = np.asarray(data.values, dtype=np.float32).reshape(data.shape)
    return NDArrayFloat.from_numpy(arr)


def _rle_to_data(rle: CompressedRLE) -> CompressedRLEData:
    counts = rle.counts
    if isinstance(counts, str):
        counts = counts.encode("utf-8")
    elif not isinstance(counts, bytes):
        # A numeric-array RLE is compressed to bytes by CompressedRLE's validator, so this
        # is defensive only.
        counts = str(counts).encode("utf-8")
    return CompressedRLEData(size=list(rle.size), counts=counts)


def _frame_to_str(frame: str | bytes) -> str:
    return bytes_to_data_uri(frame) if isinstance(frame, bytes) else frame


# --- Provider ----------------------------------------------------------------


@register_provider("pixano-inference")
class PixanoInferenceProvider(InferenceProvider):
    """Provider for a pixano-inference `/v1` server.

    Example:
        ```python
        provider = await PixanoInferenceProvider.connect("http://localhost:7463")
        models = await provider.list_models()
        await provider.close()
        ```
    """

    def __init__(self, url: str, *, api_key: str | None = None) -> None:
        """Create the provider (does not connect).

        Args:
            url: Base URL of the pixano-inference server.
            api_key: Optional API key.
        """
        self.url = url.rstrip("/")
        self._api_key = api_key
        self._client = PixanoInferenceClient(self.url, api_key=api_key)

    @property
    def name(self) -> str:
        """Provider name."""
        return "pixano-inference"

    @classmethod
    async def connect(cls, url: str, *, api_key: str | None = None) -> "PixanoInferenceProvider":
        """Connect to a pixano-inference server, verifying readiness.

        Args:
            url: The URL of the pixano-inference server.
            api_key: Optional API key.

        Returns:
            A connected `PixanoInferenceProvider`.

        Raises:
            ProviderConnectionError: If the server is unreachable or not ready.
        """
        provider = cls(url, api_key=api_key)
        try:
            await provider._client.ready()
        except Exception as exc:
            await provider.close()
            raise ProviderConnectionError(f"Failed to connect to pixano-inference at {url}: {exc}") from exc
        return provider

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        await self._client.aclose()

    # --- Discovery ---

    async def list_models(self, task: InferenceTask | None = None) -> list[ModelInfo]:
        """List available models, optionally filtered by Pixano task."""
        try:
            models = await self._client.list_models()
        except PixanoInferenceError as exc:
            raise self._request_error(exc) from exc
        infos: list[ModelInfo] = []
        for model in models:
            model_task = CAPABILITY_TO_TASK.get(model.capability)
            if model_task is None:
                continue
            if task is not None and model_task != task:
                continue
            infos.append(
                ModelInfo(
                    name=model.name,
                    task=model_task.value,
                    model_class=model.model_class,
                    model_path=model.model_path,
                    status=getattr(model, "status", None),
                )
            )
        return infos

    async def get_server_info(self) -> ServerInfo:
        """Get server version + loaded models mapped to Pixano tasks."""
        try:
            info = await self._client.info()
            models = await self._client.list_models()
        except PixanoInferenceError as exc:
            raise self._request_error(exc) from exc
        version = str(info.get("appVersion") or info.get("version") or "unknown")
        names: list[str] = []
        models_to_task: dict[str, str] = {}
        for model in models:
            model_task = CAPABILITY_TO_TASK.get(model.capability)
            if model_task is None:
                continue
            names.append(model.name)
            models_to_task[model.name] = model_task.value
        return ServerInfo(version=version, models=names, models_to_task=models_to_task)

    # --- Image mask generation ---

    async def image_mask_generation(
        self,
        input_data: ImageMaskGenerationInput,
        timeout: float = 60.0,
    ) -> ImageMaskGenerationResult:
        """Generate masks for an image."""
        request = SegmentationRequest(
            model=input_data.model,
            image=_frame_to_str(input_data.image),
            image_embedding=(
                _data_to_ndarray(input_data.image_embedding) if input_data.image_embedding is not None else None
            ),
            high_resolution_features=(
                [_data_to_ndarray(f) for f in input_data.high_resolution_features]
                if input_data.high_resolution_features is not None
                else None
            ),
            mask_input=_data_to_ndarray(input_data.mask_input) if input_data.mask_input is not None else None,
            reset_predictor=input_data.reset_predictor,
            points=input_data.points,
            labels=input_data.labels,
            boxes=input_data.boxes,
            num_multimask_outputs=input_data.num_multimask_outputs,
            multimask_output=input_data.multimask_output,
            return_image_embedding=input_data.return_image_embedding,
            return_logits=input_data.return_logits,
        )
        try:
            response = await self._client.segmentation(request, timeout=timeout)
        except PixanoInferenceError as exc:
            raise self._request_error(exc) from exc

        data = response.data
        output = ImageMaskGenerationOutput(
            masks=[[_rle_to_data(m) for m in prompt_masks] for prompt_masks in data.masks],
            scores=_ndarray_to_data(data.scores),
            image_embedding=_ndarray_to_data(data.image_embedding) if data.image_embedding is not None else None,
            high_resolution_features=(
                [_ndarray_to_data(f) for f in data.high_resolution_features]
                if data.high_resolution_features is not None
                else None
            ),
            mask_logits=_ndarray_to_data(data.mask_logits) if data.mask_logits is not None else None,
        )
        return ImageMaskGenerationResult(
            data=output,
            timestamp=response.timestamp,
            processing_time=response.processing_time,
            metadata=response.metadata,
            id=response.id,
            status=response.status.upper(),
        )

    # --- Video mask generation ---

    def _build_tracking_request(self, input_data: VideoMaskGenerationInput) -> TrackingRequestV1:
        """Build a `/v1` tracking request, converting flat prompts to keyframes.

        Keyframe i is associated positionally with ``objects_ids[i]`` / ``frame_indexes[i]``;
        boxes are converted from xyxy to x,y,width,height.
        """
        keyframes: list[TrackingKeyframeV1] = []
        for i, _obj_id in enumerate(input_data.objects_ids):
            frame_index = input_data.frame_indexes[i] if i < len(input_data.frame_indexes) else 0

            point_prompts: list[TrackingPointPrompt] | None = None
            if input_data.points is not None and i < len(input_data.points):
                obj_points = input_data.points[i]
                obj_labels = (
                    input_data.labels[i]
                    if input_data.labels is not None and i < len(input_data.labels)
                    else [1] * len(obj_points)
                )
                point_prompts = [
                    TrackingPointPrompt(x=int(p[0]), y=int(p[1]), label=int(obj_labels[j]))
                    for j, p in enumerate(obj_points)
                ]

            box_prompt: TrackingBoxPrompt | None = None
            if input_data.boxes is not None and i < len(input_data.boxes):
                x1, y1, x2, y2 = (int(c) for c in input_data.boxes[i])
                box_prompt = TrackingBoxPrompt(x=x1, y=y1, width=x2 - x1, height=y2 - y1)

            keyframes.append(
                TrackingKeyframeV1(
                    frame_index=frame_index,
                    prompts=TrackingPrompts(points=point_prompts, box=box_prompt),
                )
            )

        interval = None
        if input_data.interval is not None:
            interval = TrackingInterval(**input_data.interval)

        return TrackingRequestV1(
            model=input_data.model,
            video=[_frame_to_str(f) for f in input_data.video]
            if isinstance(input_data.video, list)
            else _frame_to_str(input_data.video),
            objects_ids=list(input_data.objects_ids),
            frame_indexes=list(input_data.frame_indexes),
            propagate=input_data.propagate,
            interval=interval,
            keyframes=keyframes,
        )

    async def video_mask_generation(
        self,
        input_data: VideoMaskGenerationInput,
        timeout: float = 120.0,
    ) -> VideoMaskGenerationResult:
        """Generate masks for video frames (synchronous)."""
        request = self._build_tracking_request(input_data)
        try:
            response = await self._client.tracking(request, timeout=timeout)
        except PixanoInferenceError as exc:
            raise self._request_error(exc) from exc
        data = response.data
        output = VideoMaskGenerationOutput(
            objects_ids=list(data.objects_ids),
            frame_indexes=list(data.frame_indexes),
            masks=[_rle_to_data(m) for m in data.masks],
        )
        return VideoMaskGenerationResult(
            data=output,
            status=response.status.upper(),
            timestamp=response.timestamp,
            processing_time=response.processing_time,
            metadata=response.metadata,
            id=response.id,
        )

    async def submit_video_mask_generation_job(
        self,
        input_data: VideoMaskGenerationInput,
        timeout: float = 30.0,
    ) -> VideoMaskGenerationJobStatus:
        """Submit an asynchronous video mask generation job."""
        request = self._build_tracking_request(input_data)
        try:
            job = await self._client.submit_tracking_job(request, timeout=timeout)
        except PixanoInferenceError as exc:
            raise self._request_error(exc) from exc
        return self._job_status(job)

    async def get_video_mask_generation_job(
        self,
        job_id: str,
        timeout: float = 30.0,
    ) -> VideoMaskGenerationJobStatus:
        """Fetch the status of a video mask generation job."""
        try:
            job = await self._client.get_job(job_id)
        except PixanoInferenceError as exc:
            raise self._request_error(exc) from exc
        return self._job_status(job)

    async def cancel_video_mask_generation_job(
        self,
        job_id: str,
        timeout: float = 30.0,
    ) -> VideoMaskGenerationJobStatus:
        """Cancel a video mask generation job."""
        try:
            job = await self._client.cancel_job(job_id)
        except PixanoInferenceError as exc:
            raise self._request_error(exc) from exc
        return self._job_status(job)

    def _job_status(self, job: Any) -> VideoMaskGenerationJobStatus:
        """Convert a client `JobStatus` (camelCase `data` dict) to Pixano's type."""
        output: VideoMaskGenerationOutput | None = None
        payload = job.data
        if payload:
            output = VideoMaskGenerationOutput(
                objects_ids=list(payload.get("objectsIds", [])),
                frame_indexes=list(payload.get("frameIndexes", [])),
                masks=[CompressedRLEData.from_dict(m) for m in payload.get("masks", [])],
            )
        return VideoMaskGenerationJobStatus(
            job_id=job.job_id,
            status=job.status,
            detail=job.detail,
            data=output,
            metadata=job.metadata,
            processing_time=job.processing_time,
        )

    # --- Detection ---

    async def detection(
        self,
        input_data: DetectionInput,
        timeout: float = 60.0,
    ) -> DetectionResult:
        """Detect objects in an image using zero-shot detection."""
        request = DetectionRequest(
            model=input_data.model,
            image=_frame_to_str(input_data.image),
            classes=input_data.classes,
            box_threshold=input_data.box_threshold,
            text_threshold=input_data.text_threshold,
        )
        try:
            response = await self._client.detection(request, timeout=timeout)
        except PixanoInferenceError as exc:
            raise self._request_error(exc) from exc
        data = response.data
        output = DetectionOutput(boxes=data.boxes, scores=data.scores, classes=data.classes)
        return DetectionResult(
            data=output,
            timestamp=response.timestamp,
            processing_time=response.processing_time,
            metadata=response.metadata,
            id=response.id,
            status=response.status.upper(),
        )

    # --- VLM ---

    async def vlm(
        self,
        input_data: VLMInput,
        timeout: float = 60.0,
    ) -> VLMResult:
        """Generate text conditioned on images."""
        request = VLMRequest(
            model=input_data.model,
            prompt=input_data.prompt,
            images=input_data.images,
            max_new_tokens=input_data.max_new_tokens if input_data.max_new_tokens is not None else 512,
            temperature=input_data.temperature,
        )
        try:
            response = await self._client.vlm(request, timeout=timeout)
        except PixanoInferenceError as exc:
            raise self._request_error(exc) from exc
        data = response.data
        usage = data.usage
        output = VLMOutput(
            generated_text=data.generated_text,
            usage=UsageInfo(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                total_tokens=usage.total_tokens,
            ),
            generation_config=data.generation_config,
        )
        return VLMResult(
            data=output,
            timestamp=response.timestamp,
            processing_time=response.processing_time,
            metadata=response.metadata,
            id=response.id,
            status=response.status.upper(),
        )

    # --- Embedding ---

    async def embedding(
        self,
        input_data: EmbeddingInput,
        timeout: float = 60.0,
    ) -> EmbeddingResult:
        """Embed an image or text into a shared vector space (CLIP-style)."""
        request = EmbeddingRequest(
            model=input_data.model,
            image=input_data.image,
            text=input_data.text,
            normalize=input_data.normalize,
        )
        try:
            response = await self._client.embedding(request, timeout=timeout)
        except PixanoInferenceError as exc:
            raise self._request_error(exc) from exc
        data = response.data
        return EmbeddingResult(
            data=EmbeddingOutput(embedding=_ndarray_to_data(data.embeddings), dim=data.dim),
            timestamp=response.timestamp,
            processing_time=response.processing_time,
            metadata=response.metadata,
            id=response.id,
            status=response.status.upper(),
        )

    # --- Errors ---

    @staticmethod
    def _request_error(exc: PixanoInferenceError) -> InferenceRequestError:
        return InferenceRequestError(
            status_code=exc.status_code,
            code=getattr(exc, "code", ""),
            message=str(exc),
            request_id=getattr(exc, "request_id", None),
        )
