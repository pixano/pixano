# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any

import shortuuid

from pixano.features.types.nd_array_float import NDArrayFloat
from pixano.schemas import BBox, CompressedRLE, Image, SequenceFrame, ViewEmbedding
from pixano.schemas.entities.entity import Entity

from .provider import InferenceProvider
from .types import (
    CompressedRLEData,
    NDArrayData,
    SegmentationInput,
    TrackingInput,
)


def _is_url(value: str) -> bool:
    """Check if a string is a URL."""
    return value.startswith(("http://", "https://", "s3://"))


def _resolved_view_id(image: Image | SequenceFrame) -> str:
    return image.logical_name or "image"


async def segmentation(
    provider: InferenceProvider,
    image: Image,
    entity: Entity | None,
    source_name: str,
    source_type: str = "model",
    image_embedding: ViewEmbedding | NDArrayFloat | NDArrayData | None = None,
    high_resolution_features: list[ViewEmbedding] | list[NDArrayFloat] | list[NDArrayData] | None = None,
    reset_predictor: bool = True,
    bbox: BBox | None = None,
    points: list[list[int]] | None = None,
    labels: list[int] | None = None,
    **provider_kwargs: Any,
) -> tuple[CompressedRLE, float, NDArrayFloat | None, list[NDArrayFloat] | None]:
    """Image segmentation task.

    Args:
        provider: Inference provider.
        image: Image to generate mask for.
        entity: Entity associated with the image.
        source_name: Name of the model source.
        source_type: Kind of source (default "model").
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
    image_request = image.uri if _is_url(image.uri) else image.open(as_base64=True)

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

    input_data = SegmentationInput(
        image=image_request,
        model=source_name,
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

    result = await provider.segmentation(input_data, **provider_kwargs)

    # Get first mask from first prompt
    mask_data: CompressedRLEData = result.data.masks[0][0]
    mask = CompressedRLE(
        id=shortuuid.uuid(),
        record_id=image.record_id,
        frame_id=image.id,
        view_id=_resolved_view_id(image),
        entity_id=entity.id if entity else "",
        source_type=source_type,
        source_name=source_name,
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


async def tracking(
    provider: InferenceProvider,
    video: list[SequenceFrame],
    source_name: str,
    source_type: str = "model",
    entity: Entity | None = None,
    bbox: BBox | None = None,
    points: list[list[int]] | None = None,
    labels: list[int] | None = None,
    **provider_kwargs: Any,
) -> tuple[list[CompressedRLE], list[int], list[int]]:
    """Video tracking task.

    Args:
        provider: Inference provider.
        video: Video as list of SequenceFrame.
        source_name: Name of the model source.
        source_type: Kind of source (default "model").
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

    video_request = [sf.uri if _is_url(sf.uri) else sf.open(as_base64=True) for sf in video]

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

    input_data = TrackingInput(
        video=video_request,
        model=source_name,
        objects_ids=list(range(len(video))),
        frame_indexes=list(range(len(video))),
        points=points_request,
        labels=labels_request,
        boxes=boxes_request,
    )

    result = await provider.tracking(input_data, **provider_kwargs)

    masks: list[CompressedRLE] = []
    objects_ids: list[int] = []
    frame_indexes: list[int] = []

    if result.status == "SUCCESS":
        generated_entity_id = shortuuid.uuid()  # used to group masks from one generation when no entity in input

        for mask_data, obj_id, frame_idx in zip(result.data.masks, result.data.objects_ids, result.data.frame_indexes):
            frame_image = video[frame_idx]
            mask = CompressedRLE(
                id=shortuuid.uuid(),
                record_id=frame_image.record_id,
                frame_id=frame_image.id,
                view_id=_resolved_view_id(frame_image),
                entity_id=entity.id if entity else generated_entity_id,
                source_type=source_type,
                source_name=source_name,
                size=mask_data.size,
                counts=mask_data.counts,
            )
            masks.append(mask)
            objects_ids.append(obj_id)
            frame_indexes.append(frame_idx)

    return masks, objects_ids, frame_indexes
