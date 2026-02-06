# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from typing import Any

import shortuuid
from fastapi.encoders import jsonable_encoder

from pixano.features import BBox, CompressedRLE, Image, NDArrayFloat, SequenceFrame, Source, ViewEmbedding
from pixano.features.schemas.entities.entity import Entity
from pixano.features.types.schema_reference import EntityRef, SourceRef, ViewRef

from .provider import InferenceProvider
from .types import (
    CompressedRLEData,
    ImageMaskGenerationInput,
    NDArrayData,
    VideoMaskGenerationInput,
)


def _is_url(value: str) -> bool:
    """Check if a string is a URL."""
    return value.startswith(("http://", "https://", "s3://"))


async def image_mask_generation(
    provider: InferenceProvider,
    media_dir: Path,
    image: Image,
    entity: Entity | None,
    source: Source,
    image_embedding: ViewEmbedding | NDArrayFloat | NDArrayData | None = None,
    high_resolution_features: list[ViewEmbedding] | list[NDArrayFloat] | list[NDArrayData] | None = None,
    reset_predictor: bool = True,
    bbox: BBox | None = None,
    points: list[list[int]] | None = None,
    labels: list[int] | None = None,
    **provider_kwargs: Any,
) -> tuple[CompressedRLE, float, NDArrayFloat | None, list[NDArrayFloat] | None]:
    """Image mask generation task.

    Args:
        provider: Inference provider.
        media_dir: Media directory.
        image: Image to generate mask for.
        entity: Entity associated with the image.
        source: The source refering to the model.
        image_embedding: Image embedding.
        high_resolution_features: High resolution features.
        reset_predictor: True (default) if it's a new image.
        bbox: Bounding box of the object in the original image.
        points: Points to generate mask for.
        labels: Labels of the points. If 0, the point is background else the point is foreground.
        provider_kwargs: Additional kwargs for the provider.

    Returns:
        tuple of the compressed RLE mask, its score, the image embeddings and the high
        resolution features. The features are returned if not provided in the arguments otherwise None is returned.
    """
    image_request = image.url if _is_url(image.url) else image.open(media_dir, "base64")

    # Convert image embedding to NDArrayData
    image_embedding_request: NDArrayData | None = None
    if image_embedding is not None:
        if isinstance(image_embedding, NDArrayData):
            image_embedding_request = image_embedding
        elif isinstance(image_embedding, NDArrayFloat):
            image_embedding_request = NDArrayData(values=image_embedding.values, shape=image_embedding.shape)
        else:
            # ViewEmbedding
            image_embedding_request = NDArrayData(values=image_embedding.vector, shape=image_embedding.shape)

    # Convert high resolution features
    high_resolution_features_request: list[NDArrayData] | None = None
    if high_resolution_features is not None:
        high_resolution_features_request = []
        for feature in high_resolution_features:
            if isinstance(feature, NDArrayData):
                high_resolution_features_request.append(feature)
            elif isinstance(feature, NDArrayFloat):
                high_resolution_features_request.append(NDArrayData(values=feature.values, shape=feature.shape))
            else:
                # ViewEmbedding
                high_resolution_features_request.append(NDArrayData(values=feature.vector, shape=feature.shape))

    # Format points and labels
    points_request: list[list[list[int]]] | None = None
    if points is not None:
        points_request = [points]

    labels_request: list[list[int]] | None = None
    if labels is not None:
        labels_request = [labels]

    # Format bbox
    boxes_request: list[list[int]] | None = None
    if bbox is not None:
        if bbox.is_normalized:
            bbox = bbox.denormalize(height=image.height, width=image.width)
        boxes_request = [[int(c) for c in bbox.xyxy_coords]]

    # Note: As long as we don't store embeddings somewhere, no need to return them
    # More, it is VERY costly (around 13 sec) as it means to shape them and transfer them via HTTP.
    return_image_embedding = False

    input_data = ImageMaskGenerationInput(
        image=image_request,
        model=source.name,
        image_embedding=image_embedding_request,
        high_resolution_features=high_resolution_features_request,
        reset_predictor=reset_predictor,
        points=points_request,
        labels=labels_request,
        boxes=boxes_request,
        num_multimask_outputs=1,
        multimask_output=False,
        return_image_embedding=return_image_embedding,
    )

    result = await provider.image_mask_generation(input_data, **provider_kwargs)

    inference_metadata = jsonable_encoder(
        {
            "timestamp": result.timestamp.isoformat(),
            "processing_time": result.processing_time,
            **result.metadata,
        }
    )

    # Get first mask from first prompt
    mask_data: CompressedRLEData = result.data.masks[0][0]
    mask = CompressedRLE(
        id=shortuuid.uuid(),
        item_ref=image.item_ref,
        view_ref=ViewRef(name=image.table_name, id=image.id),
        entity_ref=EntityRef(name=entity.table_name, id=entity.id) if entity else EntityRef(name="", id=""),
        source_ref=SourceRef(id=source.id),
        inference_metadata=inference_metadata,
        size=mask_data.size,
        counts=mask_data.counts,
    )
    score = result.data.scores.values[0]

    # Convert embeddings back to NDArrayFloat if they were returned
    returned_embedding: NDArrayFloat | None = None
    if result.data.image_embedding is not None:
        returned_embedding = NDArrayFloat(
            values=result.data.image_embedding.values,
            shape=result.data.image_embedding.shape,
        )

    returned_features: list[NDArrayFloat] | None = None
    if result.data.high_resolution_features is not None:
        returned_features = [
            NDArrayFloat(values=f.values, shape=f.shape) for f in result.data.high_resolution_features
        ]

    return mask, score, returned_embedding, returned_features


async def video_mask_generation(
    provider: InferenceProvider,
    media_dir: Path,
    video: list[SequenceFrame],
    source: Source,
    entity: Entity | None = None,
    bbox: BBox | None = None,
    points: list[list[int]] | None = None,
    labels: list[int] | None = None,
    **provider_kwargs: Any,
) -> tuple[list[CompressedRLE], list[int], list[int]]:
    """Video mask generation task.

    Args:
        provider: Inference provider.
        media_dir: Media directory.
        video: Video as list of SequenceFrame.
        source: The source refering to the model.
        entity: Entity to put objects in, if provided.
        bbox: Bounding box of the object in the original image.
        points: Points to generate mask for.
        labels: Labels of the points. If 0, the point is background else the point is foreground.
        provider_kwargs: Additional kwargs for the provider.

    Returns:
        tuple of the compressed RLE masks, object IDs, and frame indexes.
    """
    if not isinstance(video, list):
        raise ValueError("Video format not currently supported, please use sequence frames.")

    video_request = [sf.url if _is_url(sf.url) else sf.open(media_dir, "base64") for sf in video]

    # Format points and labels
    points_request: list[list[list[int]]] | None = None
    if points is not None:
        points_request = [points]

    labels_request: list[list[int]] | None = None
    if labels is not None:
        labels_request = [labels]

    # Format bbox
    boxes_request: list[list[int]] | None = None
    if bbox is not None:
        if bbox.is_normalized:
            bbox = bbox.denormalize(height=video[0].height, width=video[0].width)
        boxes_request = [[int(c) for c in bbox.xyxy_coords]]

    input_data = VideoMaskGenerationInput(
        video=video_request,
        model=source.name,
        objects_ids=list(range(len(video))),
        frame_indexes=list(range(len(video))),
        points=points_request,
        labels=labels_request,
        boxes=boxes_request,
    )

    result = await provider.video_mask_generation(input_data, **provider_kwargs)

    inference_metadata = jsonable_encoder(
        {
            "timestamp": result.timestamp.isoformat(),
            "processing_time": result.processing_time,
            **result.metadata,
        }
    )

    masks: list[CompressedRLE] = []
    objects_ids: list[int] = []
    frame_indexes: list[int] = []

    if result.status == "SUCCESS":
        entity_ref_id = shortuuid.uuid()  # used to check masks are from same generation when no entity in input

        for mask_data, obj_id, frame_idx in zip(result.data.masks, result.data.objects_ids, result.data.frame_indexes):
            frame_image = video[frame_idx]
            mask = CompressedRLE(
                id=shortuuid.uuid(),
                item_ref=frame_image.item_ref,
                view_ref=ViewRef(name=frame_image.table_name, id=frame_image.id),
                entity_ref=EntityRef(name=entity.table_name, id=entity.id)
                if entity
                else EntityRef(name="", id=entity_ref_id),
                source_ref=SourceRef(id=source.id),
                inference_metadata=inference_metadata,
                size=mask_data.size,
                counts=mask_data.counts,
            )
            masks.append(mask)
            objects_ids.append(obj_id)
            frame_indexes.append(frame_idx)

    return masks, objects_ids, frame_indexes
