# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Pixano's inference types.

This module defines Pixano's own types for inference operations,
independent of any specific inference backend.
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
        app_name: Application name.
        app_version: Application version string.
        app_description: Application description.
        num_cpus: Number of CPUs available (None if unknown).
        num_gpus: Number of GPUs available.
        num_nodes: Number of nodes in the cluster.
        gpus_used: List of GPU indices currently in use.
        gpu_to_model: Mapping of GPU index to model name.
        models: List of loaded model names.
        models_to_task: Mapping of model names to their tasks.
    """

    app_name: str
    app_version: str
    app_description: str
    num_cpus: int | None
    num_gpus: int
    num_nodes: int
    gpus_used: list[int]
    gpu_to_model: dict[str, str]
    models: list[str]
    models_to_task: dict[str, str]


class InferenceTask(str, Enum):
    """Tasks supported by Pixano inference providers."""

    MASK_GENERATION = "image_mask_generation"
    VIDEO_MASK_GENERATION = "video_mask_generation"
    OBJECT_DETECTION = "image_zero_shot_detection"
    TEXT_GENERATION = "text_image_conditional_generation"


@dataclass
class ModelConfig:
    """Configuration for instantiating a model.

    Attributes:
        name: Name of the model.
        task: Task of the model.
        path: Path to the model dump.
        config: Configuration of the model.
        processor_config: Configuration of the processor.
    """

    name: str
    task: str
    path: Path | str | None = None
    config: dict[str, Any] = field(default_factory=dict)
    processor_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "task": self.task,
            "path": str(self.path) if self.path else None,
            "config": self.config,
            "processor_config": self.processor_config,
        }


@dataclass
class ModelInfo:
    """Information about an available model.

    Attributes:
        name: Name of the model.
        task: Task the model can perform.
        model_path: Path to the model weights (optional).
        model_class: Class name of the model (optional).
        provider: Provider backend for the model (optional).
    """

    name: str
    task: str
    model_path: str | None = None
    model_class: str | None = None
    provider: str | None = None


@dataclass
class ProviderCapabilities:
    """What a provider can do.

    Attributes:
        tasks: List of supported inference tasks.
        supports_batching: Whether the provider supports batch processing.
        supports_streaming: Whether the provider supports streaming responses.
        max_image_size: Maximum supported image size (optional).
    """

    tasks: list[InferenceTask]
    supports_batching: bool = False
    supports_streaming: bool = False
    max_image_size: int | None = None


# --- Mask Generation Types ---


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


@dataclass
class ImageMaskGenerationInput:
    """Input for image mask generation.

    Attributes:
        image: Image as base64 string or URL.
        model: Model name to use.
        image_embedding: Pre-computed image embedding (optional).
        high_resolution_features: Pre-computed high-res features (optional).
        reset_predictor: Whether to reset predictor state for new image.
        points: Points for mask generation [num_prompts, num_points, 2].
        labels: Labels for points [num_prompts, num_points].
        boxes: Bounding boxes [num_prompts, 4].
        num_multimask_outputs: Number of masks to generate per prompt.
        multimask_output: Whether to return multiple masks per prompt.
        return_image_embedding: Whether to return computed embeddings.
    """

    image: str
    model: str
    image_embedding: NDArrayData | None = None
    high_resolution_features: list[NDArrayData] | None = None
    reset_predictor: bool = True
    points: list[list[list[int]]] | None = None
    labels: list[list[int]] | None = None
    boxes: list[list[int]] | None = None
    num_multimask_outputs: int = 3
    multimask_output: bool = True
    return_image_embedding: bool = False


@dataclass
class ImageMaskGenerationOutput:
    """Output for image mask generation.

    Attributes:
        masks: Generated masks [num_prompts, num_masks].
        scores: Confidence scores.
        image_embedding: Computed image embedding (if requested).
        high_resolution_features: Computed features (if requested).
    """

    masks: list[list[CompressedRLEData]]
    scores: NDArrayData
    image_embedding: NDArrayData | None = None
    high_resolution_features: list[NDArrayData] | None = None


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


# --- Video Mask Generation Types ---


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
    """

    video: list[str]
    model: str
    objects_ids: list[int]
    frame_indexes: list[int]
    points: list[list[list[int]]] | None = None
    labels: list[list[int]] | None = None
    boxes: list[list[int]] | None = None


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


# --- Zero-Shot Detection Types ---


@dataclass
class ImageZeroShotDetectionInput:
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
class ImageZeroShotDetectionOutput:
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
class ImageZeroShotDetectionResult:
    """Complete result of zero-shot object detection.

    Attributes:
        data: The output data.
        timestamp: When the inference completed.
        processing_time: Time taken in seconds.
        metadata: Additional metadata from the model.
        id: Unique identifier for the inference request.
        status: Status of the inference ("SUCCESS", "FAILURE").
    """

    data: ImageZeroShotDetectionOutput
    timestamp: datetime
    processing_time: float
    metadata: dict[str, Any]
    id: str = ""
    status: str = "SUCCESS"


# --- Text-Image Conditional Generation Types ---


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
class TextImageConditionalGenerationInput:
    """Input for text-image conditional generation.

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
    max_new_tokens: int = 100
    temperature: float = 1.0


@dataclass
class TextImageConditionalGenerationOutput:
    """Output for text-image conditional generation.

    Attributes:
        generated_text: The generated text response.
        usage: Token usage information.
        generation_config: Generation configuration used.
    """

    generated_text: str
    usage: UsageInfo
    generation_config: dict[str, Any] = field(default_factory=dict)


@dataclass
class TextImageConditionalGenerationResult:
    """Complete result of text-image conditional generation.

    Attributes:
        data: The output data.
        timestamp: When the inference completed.
        processing_time: Time taken in seconds.
        metadata: Additional metadata from the model.
        id: Unique identifier for the inference request.
        status: Status of the inference ("SUCCESS", "FAILURE").
    """

    data: TextImageConditionalGenerationOutput
    timestamp: datetime
    processing_time: float
    metadata: dict[str, Any]
    id: str = ""
    status: str = "SUCCESS"
