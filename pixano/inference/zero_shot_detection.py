# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from typing import Any

import shortuuid
from fastapi.encoders import jsonable_encoder

from pixano.features import BBox, Classification, Image, Source
from pixano.features.schemas.entities.entity import Entity
from pixano.features.types.schema_reference import EntityRef, SourceRef, ViewRef

from .provider import InferenceProvider
from .types import ImageZeroShotDetectionInput


def _is_url(value: str) -> bool:
    """Check if a string is a URL."""
    return value.startswith(("http://", "https://", "s3://"))


async def image_zero_shot_detection(
    provider: InferenceProvider,
    media_dir: Path,
    image: Image,
    entity: Entity,
    source: Source,
    classes: list[str] | str,
    box_threshold: float = 0.5,
    text_threshold: float = 0.5,
    **provider_kwargs: Any,
) -> list[tuple[BBox, Classification]]:
    """Image zero shot detection task.

    Args:
        provider: Inference provider.
        media_dir: Media directory.
        image: Image to generate mask for.
        entity: Entity associated with the image.
        source: The source refering to the model.
        classes: List of classes to detect in the image.
        box_threshold: Box threshold for detection in the image.
        text_threshold: Text threshold for detection in the image.
        provider_kwargs: Additional kwargs for the provider.

    Returns:
        List of BBoxes and Classifications detected in the image with respect to classes and threshold values.
    """
    image_request = image.url if _is_url(image.url) else image.open(media_dir, "base64")

    input_data = ImageZeroShotDetectionInput(
        image=image_request,
        model=source.name,
        classes=classes,
        box_threshold=box_threshold,
        text_threshold=text_threshold,
    )

    result = await provider.image_zero_shot_detection(input_data, **provider_kwargs)

    inference_metadata = jsonable_encoder(
        {
            "timestamp": result.timestamp.isoformat(),
            "processing_time": result.processing_time,
            **result.metadata,
        }
    )

    boxes = result.data.boxes
    scores = result.data.scores
    detected_classes = result.data.classes

    output: list[tuple[BBox, Classification]] = []

    for b, s, c in zip(boxes, scores, detected_classes, strict=True):
        view_ref = ViewRef(name=image.table_name, id=image.id)
        entity_ref = EntityRef(name=entity.table_name, id=entity.id)
        source_ref = SourceRef(id=source.id)
        output.append(
            (
                BBox(
                    id=shortuuid.uuid(),
                    item_ref=image.item_ref,
                    view_ref=view_ref,
                    entity_ref=entity_ref,
                    source_ref=source_ref,
                    inference_metadata=inference_metadata,
                    coords=b,
                    format="xyxy",
                    is_normalized=False,
                    confidence=s,
                ),
                Classification(
                    id=shortuuid.uuid(),
                    item_ref=image.item_ref,
                    view_ref=view_ref,
                    entity_ref=entity_ref,
                    source_ref=source_ref,
                    inference_metadata=inference_metadata,
                    labels=[c],
                    confidences=[s],
                ),
            )
        )

    return output
