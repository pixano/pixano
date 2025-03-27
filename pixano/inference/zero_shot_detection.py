# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from typing import Any

import shortuuid
from fastapi.encoders import jsonable_encoder
from pixano_inference.client import PixanoInferenceClient
from pixano_inference.pydantic import ImageZeroShotDetectionRequest, ImageZeroShotDetectionResponse
from pixano_inference.utils import is_url

from pixano.features import BBox, Classification, Image, Source
from pixano.features.schemas.entities.entity import Entity
from pixano.features.types.schema_reference import EntityRef, SourceRef, ViewRef


async def image_zero_shot_detection(
    client: PixanoInferenceClient,
    media_dir: Path,
    image: Image,
    entity: Entity,
    source: Source,
    classes: list[str] | str,
    box_threshold: float = 0.5,
    text_threshold: float = 0.5,
    **client_kwargs: Any,
) -> list[tuple[BBox, Classification]]:
    """Image zero shot task.

    Args:
        client: Pixano inference client.
        media_dir: Media directory.
        image: Image to generate mask for.
        entity: Entity associated with the image.
        source: The source refering to the model.
        classes: List of classes to detect in the image.
        box_threshold: Box threshold for detection in the image.
        text_threshold: Text threshold for detection in the image.
        client_kwargs: Additional kwargs for the client to be passed.

    Returns:
        List of BBoxes and Classifications detected in the image with respect to classes and threshold values.
    """
    image_request = image.url if is_url(image.url) else image.open(media_dir, "base64")

    request = ImageZeroShotDetectionRequest(
        image=image_request,
        classes=classes,
        box_threshold=box_threshold,
        text_threshold=text_threshold,
        model=source.name,
    )

    response: ImageZeroShotDetectionResponse = await client.image_zero_shot_detection(request, **client_kwargs)

    inference_metadata = jsonable_encoder(
        {
            "timestamp": response.timestamp,
            "processing_time": response.processing_time,
            **response.metadata,
        }
    )

    boxes = response.data.boxes
    scores = response.data.scores
    detected_classes = response.data.classes

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
