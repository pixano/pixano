# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any

import shortuuid

from pixano.schemas import BBox, Classification, Image
from pixano.schemas.entities.entity import Entity

from .provider import InferenceProvider
from .types import DetectionInput


def _is_url(value: str) -> bool:
    """Check if a string is a URL."""
    return value.startswith(("http://", "https://", "s3://"))


def _resolved_view_id(image: Image) -> str:
    return image.logical_name or "image"


async def detection(
    provider: InferenceProvider,
    image: Image,
    entity: Entity,
    source_name: str,
    source_type: str = "model",
    classes: list[str] | str = "",
    box_threshold: float = 0.5,
    text_threshold: float = 0.5,
    **provider_kwargs: Any,
) -> list[tuple[BBox, Classification]]:
    """Image detection task.

    Args:
        provider: Inference provider.
        image: Image to detect objects in.
        entity: Entity associated with the image.
        source_name: Name of the model source.
        source_type: Kind of source (default "model").
        classes: List of classes to detect in the image.
        box_threshold: Box threshold for detection in the image.
        text_threshold: Text threshold for detection in the image.
        provider_kwargs: Additional kwargs for the provider.

    Returns:
        List of BBoxes and Classifications detected in the image with respect to classes and threshold values.
    """
    image_request = image.uri if _is_url(image.uri) else image.open(as_base64=True)

    input_data = DetectionInput(
        image=image_request,
        model=source_name,
        classes=classes,
        box_threshold=box_threshold,
        text_threshold=text_threshold,
    )

    result = await provider.detection(input_data, **provider_kwargs)

    boxes = result.data.boxes
    scores = result.data.scores
    detected_classes = result.data.classes

    output: list[tuple[BBox, Classification]] = []

    for b, s, c in zip(boxes, scores, detected_classes, strict=True):
        output.append(
            (
                BBox(
                    id=shortuuid.uuid(),
                    record_id=image.record_id,
                    frame_id=image.id,
                    view_id=_resolved_view_id(image),
                    entity_id=entity.id,
                    source_type=source_type,
                    source_name=source_name,
                    coords=b,
                    format="xyxy",
                    is_normalized=False,
                    confidence=s,
                ),
                Classification(
                    id=shortuuid.uuid(),
                    record_id=image.record_id,
                    view_id=_resolved_view_id(image),
                    entity_id=entity.id,
                    source_type=source_type,
                    source_name=source_name,
                    labels=[c],
                    confidences=[s],
                ),
            )
        )

    return output
