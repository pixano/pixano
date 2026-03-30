# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Pre-annotation engine.

Runs an inference model over all items in a dataset and writes
the predictions back as annotation rows (Entity + BBox, etc.).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable

import shortuuid

from pixano.datasets.dataset import Dataset
from pixano.schemas import BBox, Image
from pixano.schemas.entities.entity import Entity
from pixano.schemas.views.image import is_image

from .provider import InferenceProvider
from .types import DetectionInput, DetectionResult, InferenceTask


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public data types
# ---------------------------------------------------------------------------


@dataclass
class PreannotationConfig:
    """Configuration for a pre-annotation run.

    Attributes:
        task: The inference task to perform.
        model: Model name on the inference provider.
        source_name: Value stored in the ``source_name`` field of created annotations.
        classes: Target classes (required for detection).
        class_field: Entity field name to write the detected class into (e.g. ``"category"``).
            Must match a field on the dataset's Entity schema.  When ``None`` the class is
            stored only in ``source_metadata`` on the BBox.
        box_threshold: Box confidence threshold (detection).
        text_threshold: Text matching threshold (detection).
        batch_write_size: Number of records to process before flushing to the DB.
        view_name: Logical view name to process.  ``None`` means all image views.
    """

    task: InferenceTask
    model: str
    source_name: str = ""
    classes: list[str] | None = None
    class_field: str | None = None
    box_threshold: float = 0.5
    text_threshold: float = 0.5
    batch_write_size: int = 50
    view_name: str | None = None

    def __post_init__(self) -> None:
        if not self.source_name:
            self.source_name = self.model


@dataclass
class PreannotationProgress:
    """Live progress of a pre-annotation run.

    Attributes:
        total: Total number of records to process.
        processed: Records processed so far.
        succeeded: Records that produced annotations successfully.
        failed: Records that encountered an error.
        status: Overall status string.
        errors: Per-record error details.
    """

    total: int = 0
    processed: int = 0
    succeeded: int = 0
    failed: int = 0
    status: str = "pending"
    errors: list[dict[str, str]] = field(default_factory=list)


ProgressCallback = Callable[[PreannotationProgress], None]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _is_url(value: str) -> bool:
    return value.startswith(("http://", "https://", "s3://"))


def _image_to_request(image: Image) -> str:
    """Return a base64 data-URI or URL suitable for provider input."""
    if image.uri and _is_url(image.uri):
        return image.uri
    return image.open(as_base64=True)  # type: ignore[return-value]


def _map_detection_output(
    result: DetectionResult,
    image: Image,
    config: PreannotationConfig,
    entity_cls: type[Entity] = Entity,
) -> tuple[list[Entity], list[BBox]]:
    """Convert a DetectionResult into Entity + BBox rows for one image."""
    entities: list[Entity] = []
    bboxes: list[BBox] = []

    boxes = result.data.boxes
    scores = result.data.scores
    detected_classes = result.data.classes

    for box, score, cls_name in zip(boxes, scores, detected_classes, strict=True):
        entity_kwargs: dict[str, Any] = {
            "id": shortuuid.uuid(),
            "record_id": image.record_id,
        }
        if config.class_field is not None:
            entity_kwargs[config.class_field] = cls_name

        entity = entity_cls(**entity_kwargs)
        bbox = BBox(
            id=shortuuid.uuid(),
            record_id=image.record_id,
            frame_id=image.id,
            view_id=image.logical_name or "image",
            entity_id=entity.id,
            source_type="model",
            source_name=config.source_name,
            source_metadata=json.dumps({"class": cls_name}),
            coords=box,
            format="xyxy",
            is_normalized=False,
            confidence=score,
        )
        entities.append(entity)
        bboxes.append(bbox)

    return entities, bboxes


def _find_image_table(dataset: Dataset, view_name: str | None) -> str:
    """Return the physical table name that stores Image views.

    If *view_name* is given, find the table that the logical view maps to.
    Otherwise, return the first Image-typed table.
    """
    # If a specific logical view name is requested, resolve it.
    if view_name is not None:
        for logical, schema_cls in dataset.info.views.items():
            if logical == view_name:
                if not is_image(schema_cls):
                    raise ValueError(f"View '{view_name}' is not an Image view.")
                # Find its physical table name
                from pixano.schemas import canonical_table_name_for_schema

                return canonical_table_name_for_schema(schema_cls)
        raise ValueError(f"Logical view '{view_name}' not found in dataset.")

    # Fall back: first Image-typed table.
    for table_name, schema_cls in dataset.info.tables.items():
        if isinstance(schema_cls, type) and is_image(schema_cls):
            return table_name

    raise ValueError("Dataset has no Image view table.")


def _validate_config(dataset: Dataset, config: PreannotationConfig) -> None:
    """Validate that the dataset and config are compatible. Raises on failure."""
    if config.task == InferenceTask.DETECTION:
        if not config.classes:
            raise ValueError("Detection task requires at least one target class (config.classes).")
        if "entities" not in dataset.info.tables:
            raise ValueError("Dataset has no 'entities' table. Cannot write detection results.")
        if "bboxes" not in dataset.info.tables:
            raise ValueError("Dataset has no 'bboxes' table. Cannot write detection results.")
        if config.class_field is not None:
            entity_schema = dataset.info.tables["entities"]
            if config.class_field not in entity_schema.model_fields:
                available = [
                    f for f in entity_schema.model_fields
                    if f not in ("id", "record_id", "parent_id", "created_at", "updated_at")
                ]
                raise ValueError(
                    f"Entity schema has no field '{config.class_field}'. "
                    f"Available custom fields: {available}"
                )
    else:
        raise ValueError(f"Task '{config.task.value}' is not supported in v1. Only 'detection' is supported.")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def run_preannotation(
    dataset: Dataset,
    provider: InferenceProvider,
    config: PreannotationConfig,
    progress_callback: ProgressCallback | None = None,
    cancel_event: asyncio.Event | None = None,
) -> PreannotationProgress:
    """Run pre-annotation on an entire dataset.

    Args:
        dataset: The dataset to annotate.
        provider: Inference provider to use.
        config: Pre-annotation configuration.
        progress_callback: Called after each record with updated progress.
        cancel_event: Set this event to cancel the job between records.

    Returns:
        Final progress state.
    """
    _validate_config(dataset, config)
    image_table = _find_image_table(dataset, config.view_name)
    entity_cls: type[Entity] = dataset.info.tables["entities"]  # type: ignore[assignment]

    # Enumerate all records.
    records = dataset.get_data("records")
    progress = PreannotationProgress(total=len(records), status="running")

    if progress_callback:
        progress_callback(progress)

    entity_buf: list[Entity] = []
    bbox_buf: list[BBox] = []

    for record in records:
        # Check cancellation.
        if cancel_event is not None and cancel_event.is_set():
            progress.status = "cancelled"
            break

        record_id: str = record.id  # type: ignore[attr-defined]

        try:
            images: list[Any] = dataset.get_data(image_table, record_ids=[record_id])
            if not images:
                progress.processed += 1
                progress.succeeded += 1
                if progress_callback:
                    progress_callback(progress)
                continue

            for image in images:
                image_data = _image_to_request(image)
                input_data = DetectionInput(
                    image=image_data,
                    model=config.model,
                    classes=config.classes,  # type: ignore[arg-type]
                    box_threshold=config.box_threshold,
                    text_threshold=config.text_threshold,
                )
                result = await provider.detection(input_data)
                entities, bboxes = _map_detection_output(result, image, config, entity_cls)
                entity_buf.extend(entities)
                bbox_buf.extend(bboxes)

            progress.processed += 1
            progress.succeeded += 1

        except Exception as exc:
            logger.warning("Pre-annotation failed for record '%s': %s", record_id, exc)
            progress.processed += 1
            progress.failed += 1
            progress.errors.append({"record_id": record_id, "error": str(exc)})

        # Flush buffer periodically.
        if progress.processed % config.batch_write_size == 0:
            _flush_buffers(dataset, entity_buf, bbox_buf)
            entity_buf.clear()
            bbox_buf.clear()

        if progress_callback:
            progress_callback(progress)

    # Final flush.
    if entity_buf or bbox_buf:
        _flush_buffers(dataset, entity_buf, bbox_buf)

    if progress.status == "running":
        progress.status = "completed"

    if progress_callback:
        progress_callback(progress)

    return progress


def _flush_buffers(
    dataset: Dataset,
    entity_buf: list[Entity],
    bbox_buf: list[BBox],
) -> None:
    """Write buffered annotations to the dataset (entities first for FK order)."""
    if entity_buf:
        dataset.add_data("entities", entity_buf, raise_or_warn="warn")
    if bbox_buf:
        dataset.add_data("bboxes", bbox_buf, raise_or_warn="warn")
