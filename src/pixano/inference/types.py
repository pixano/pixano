# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Pixano's inference types.

This module defines Pixano's own types for inference operations, independent of any specific
inference backend. Task names use Pixano's vocabulary (``image_mask_generation`` etc.); the
`CAPABILITY_TO_TASK` map bridges the pixano-inference server's capability strings.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


@dataclass
class ServerInfo:
    """Information about the inference server.

    Attributes:
        version: Server application version string.
        models: List of loaded model names.
        models_to_task: Mapping of model name to its Pixano task value.
    """

    version: str
    models: list[str]
    models_to_task: dict[str, str]


class InferenceTask(str, Enum):
    """Tasks supported by Pixano inference providers (Pixano vocabulary)."""

    MASK_GENERATION = "image_mask_generation"
    VIDEO_MASK_GENERATION = "video_mask_generation"
    DETECTION = "detection"
    VLM = "vlm"
    NER = "ner"
    EMBEDDING = "embedding"


# The pixano-inference server reports a model's ability as a "capability" string; Pixano exposes
# it as a task. These two maps bridge the vocabularies at the provider boundary.
CAPABILITY_TO_TASK: dict[str, InferenceTask] = {
    "segmentation": InferenceTask.MASK_GENERATION,
    "tracking": InferenceTask.VIDEO_MASK_GENERATION,
    "detection": InferenceTask.DETECTION,
    "vlm": InferenceTask.VLM,
    "ner": InferenceTask.NER,
    "embedding": InferenceTask.EMBEDDING,
}
TASK_TO_CAPABILITY: dict[InferenceTask, str] = {task: cap for cap, task in CAPABILITY_TO_TASK.items()}


@dataclass
class ModelInfo:
    """Information about an available model.

    Attributes:
        name: Name of the model.
        task: Pixano task the model performs (an `InferenceTask` value).
        model_path: Path to the model weights (optional).
        model_class: Class name of the model (optional).
        status: Deployment status on the server (optional).
    """

    name: str
    task: str
    model_path: str | None = None
    model_class: str | None = None
    status: str | None = None


# --- Shared array / mask payloads (frontend wire shape — DO NOT change fields) ---


@dataclass
class CompressedRLEData:
    """Compressed RLE mask data.

    Attributes:
        size: Mask size as [height, width].
        counts: Mask RLE encoding as bytes.
    """

    size: list[int]
    counts: bytes

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CompressedRLEData":
        """Create from dictionary."""
        counts = data["counts"]
        if isinstance(counts, str):
            counts = counts.encode("utf-8")
        return cls(size=data["size"], counts=counts)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "size": self.size,
            "counts": self.counts.decode("utf-8") if isinstance(self.counts, bytes) else self.counts,
        }


@dataclass
class NDArrayData:
    """N-dimensional array data.

    Attributes:
        values: Flat list of values.
        shape: Shape of the array.
    """

    values: list[float]
    shape: list[int]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "NDArrayData":
        """Create from dictionary."""
        return cls(values=data["values"], shape=data["shape"])

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {"values": self.values, "shape": self.shape}


# --- Image mask generation (SAM-style) ---


@dataclass
class ImageMaskGenerationInput:
    """Input for image mask generation.

    Attributes:
        image: Image as base64 string or URL.
        model: Model name to use.
        image_embedding: Pre-computed image embedding (optional).
        high_resolution_features: Pre-computed high-res features (optional).
        mask_input: Previous low-resolution mask logits for iterative refinement.
        reset_predictor: Whether to reset predictor state for new image.
        points: Points for mask generation [num_prompts, num_points, 2].
        labels: Labels for points [num_prompts, num_points].
        boxes: Bounding boxes [num_prompts, 4].
        num_multimask_outputs: Number of masks to generate per prompt.
        multimask_output: Whether to return multiple masks per prompt.
        return_image_embedding: Whether to return computed embeddings.
        return_logits: Whether to return low-resolution mask logits.
    """

    image: str | bytes
    model: str
    image_embedding: NDArrayData | None = None
    high_resolution_features: list[NDArrayData] | None = None
    mask_input: NDArrayData | None = None
    reset_predictor: bool = True
    points: list[list[list[int]]] | None = None
    labels: list[list[int]] | None = None
    boxes: list[list[int]] | None = None
    num_multimask_outputs: int = 3
    multimask_output: bool = True
    return_image_embedding: bool = False
    return_logits: bool = False


@dataclass
class ImageMaskGenerationOutput:
    """Output for image mask generation.

    Attributes:
        masks: Generated masks [num_prompts, num_masks].
        scores: Confidence scores.
        image_embedding: Computed image embedding (if requested).
        high_resolution_features: Computed features (if requested).
        mask_logits: Low-resolution logits for iterative refinement (if requested).
    """

    masks: list[list[CompressedRLEData]]
    scores: NDArrayData
    image_embedding: NDArrayData | None = None
    high_resolution_features: list[NDArrayData] | None = None
    mask_logits: NDArrayData | None = None


@dataclass
class ImageMaskGenerationResult:
    """Complete result of image mask generation.

    Attributes:
        data: The output data.
        timestamp: When the inference completed.
        processing_time: Time taken in seconds.
        metadata: Additional metadata from the model.
        id: Unique identifier for the inference request.
        status: Status of the inference ("SUCCESS", "FAILURE").
    """

    data: ImageMaskGenerationOutput
    timestamp: datetime
    processing_time: float
    metadata: dict[str, Any]
    id: str = ""
    status: str = "SUCCESS"


# --- Video mask generation (SAM2 video tracking) ---


@dataclass
class VideoMaskGenerationInput:
    """Input for video mask generation.

    Attributes:
        video: List of frame images as base64 or URLs.
        model: Model name to use.
        objects_ids: IDs for each object to track.
        frame_indexes: Frame indices for prompts.
        points: Points for mask generation.
        labels: Labels for points.
        boxes: Bounding boxes.
        propagate: Whether to propagate masks beyond the prompted frames.
        interval: Optional propagation interval (window-relative).
        keyframes: Optional structured prompt payloads.
    """

    video: list[str | bytes] | str | bytes
    model: str
    objects_ids: list[int]
    frame_indexes: list[int]
    points: list[list[list[int]]] | None = None
    labels: list[list[int]] | None = None
    boxes: list[list[int]] | None = None
    propagate: bool = True
    interval: dict[str, Any] | None = None
    keyframes: list[dict[str, Any]] | None = None


@dataclass
class VideoMaskGenerationOutput:
    """Output for video mask generation.

    Attributes:
        objects_ids: IDs of tracked objects.
        frame_indexes: Frame indices for each mask.
        masks: Generated masks for each frame.
    """

    objects_ids: list[int]
    frame_indexes: list[int]
    masks: list[CompressedRLEData]


@dataclass
class VideoMaskGenerationResult:
    """Complete result of video mask generation.

    Attributes:
        data: The output data.
        status: Status of the inference ("SUCCESS", "FAILURE").
        timestamp: When the inference completed.
        processing_time: Time taken in seconds.
        metadata: Additional metadata from the model.
        id: Unique identifier for the inference request.
    """

    data: VideoMaskGenerationOutput
    status: str
    timestamp: datetime
    processing_time: float
    metadata: dict[str, Any]
    id: str = ""


@dataclass
class VideoMaskGenerationJobStatus:
    """Status of an asynchronous video mask generation job."""

    job_id: str
    status: str
    detail: str | None = None
    data: VideoMaskGenerationOutput | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime | None = None
    processing_time: float = 0.0


# --- Detection ---


@dataclass
class DetectionInput:
    """Input for zero-shot object detection.

    Attributes:
        image: Image as base64 string or URL.
        model: Model name to use.
        classes: List of class names to detect.
        box_threshold: Confidence threshold for boxes.
        text_threshold: Confidence threshold for text matching.
    """

    image: str
    model: str
    classes: list[str] | str
    box_threshold: float = 0.5
    text_threshold: float = 0.5


@dataclass
class DetectionOutput:
    """Output for zero-shot object detection.

    Attributes:
        boxes: Detected bounding boxes as [x1, y1, x2, y2].
        scores: Confidence scores for each detection.
        classes: Class names for each detection.
    """

    boxes: list[list[int]]
    scores: list[float]
    classes: list[str]


@dataclass
class DetectionResult:
    """Complete result of zero-shot object detection.

    Attributes:
        data: The output data.
        timestamp: When the inference completed.
        processing_time: Time taken in seconds.
        metadata: Additional metadata from the model.
        id: Unique identifier for the inference request.
        status: Status of the inference ("SUCCESS", "FAILURE").
    """

    data: DetectionOutput
    timestamp: datetime
    processing_time: float
    metadata: dict[str, Any]
    id: str = ""
    status: str = "SUCCESS"


# --- Embedding (CLIP-style, image XOR text into a shared space) ---


@dataclass
class EmbeddingInput:
    """Input for embedding computation.

    Exactly one of ``image`` or ``text`` must be provided (single value or a batch list).

    Attributes:
        model: Model name to use.
        image: Image(s) to embed (path, URL, or base64).
        text: Text(s) to embed.
        normalize: Whether to L2-normalize the output vectors.
    """

    model: str
    image: list[str] | str | None = None
    text: list[str] | str | None = None
    normalize: bool = True


@dataclass
class EmbeddingOutput:
    """Output for embedding computation.

    Attributes:
        embedding: Embedding vectors as an ``[num_inputs, dim]`` array.
        dim: Dimensionality of each embedding vector.
    """

    embedding: NDArrayData
    dim: int


@dataclass
class EmbeddingResult:
    """Complete result of embedding computation.

    Attributes:
        data: The output data.
        timestamp: When the inference completed.
        processing_time: Time taken in seconds.
        metadata: Additional metadata from the model.
        id: Unique identifier for the inference request.
        status: Status of the inference ("SUCCESS", "FAILURE").
    """

    data: EmbeddingOutput
    timestamp: datetime
    processing_time: float
    metadata: dict[str, Any]
    id: str = ""
    status: str = "SUCCESS"


# --- VLM ---


@dataclass
class UsageInfo:
    """Token usage information.

    Attributes:
        prompt_tokens: Number of tokens in the prompt.
        completion_tokens: Number of tokens generated.
        total_tokens: Total tokens used.
    """

    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class VLMInput:
    """Input for VLM (vision-language model) inference.

    Attributes:
        model: Model name to use.
        prompt: Prompt as string or list of message dicts.
        images: Optional list of image paths/base64 strings.
        max_new_tokens: Maximum tokens to generate.
        temperature: Sampling temperature.
    """

    model: str
    prompt: str | list[dict[str, Any]]
    images: list[str | Path] | None = None
    max_new_tokens: int | None = None
    temperature: float = 1.0


@dataclass
class VLMOutput:
    """Output for VLM inference.

    Attributes:
        generated_text: The generated text response.
        usage: Token usage information.
        generation_config: Generation configuration used.
    """

    generated_text: str
    usage: UsageInfo
    generation_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class VLMResult:
    """Complete result of VLM inference.

    Attributes:
        data: The output data.
        timestamp: When the inference completed.
        processing_time: Time taken in seconds.
        metadata: Additional metadata from the model.
        id: Unique identifier for the inference request.
        status: Status of the inference ("SUCCESS", "FAILURE").
    """

    data: VLMOutput
    timestamp: datetime
    processing_time: float
    metadata: dict[str, Any]
    id: str = ""
    status: str = "SUCCESS"
