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
from pixano_inference.pydantic import LanceVector
from pixano_inference.pydantic.tasks import CompressedRLE as PixanoInferenceCompressedRLE
from pixano_inference.pydantic.tasks import (
    ImageMaskGenerationRequest,
    ImageMaskGenerationResponse,
    VideoMaskGenerationOutput,
    VideoMaskGenerationRequest,
    VideoMaskGenerationResponse,
)
from pixano_inference.utils import is_url

from pixano.features import BBox, CompressedRLE, Image, NDArrayFloat, SequenceFrame, Source, ViewEmbedding
from pixano.features.schemas.entities.entity import Entity
from pixano.features.types.schema_reference import EntityRef, SourceRef, ViewRef


async def image_mask_generation(
    client: PixanoInferenceClient,
    media_dir: Path,
    image: Image,
    entity: Entity | None,
    source: Source,
    image_embedding: ViewEmbedding | NDArrayFloat | LanceVector | None = None,
    high_resolution_features: list[ViewEmbedding] | list[NDArrayFloat] | list[LanceVector] | None = None,
    reset_predictor: bool = True,
    bbox: BBox | None = None,
    points: list[list[int]] | None = None,
    labels: list[int] | None = None,
    **client_kwargs: Any,
) -> tuple[CompressedRLE, float, NDArrayFloat | None, list[NDArrayFloat] | None]:
    """Image mask generation task.

    Args:
        client: Pixano inference client.
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
        client_kwargs: Additional kwargs for the client to be passed.

    Returns:
        tuple of the compressed RLE mask, its score, the source of the image, the image embeddings and the high
        resolution features The features are returned if not provided in the arguments otherwise None is returned.
    """
    image_request = image.url if is_url(image.url) else image.open(media_dir, "base64")
    if image_embedding is None or isinstance(image_embedding, (LanceVector, NDArrayFloat)):
        image_embedding_request = image_embedding
    else:
        image_embedding_request = NDArrayFloat(values=image_embedding.vector, shape=image_embedding.shape)
    if high_resolution_features is None:
        high_resolution_features_request = None
    else:
        high_resolution_features_request = []
        for feature in high_resolution_features:
            if isinstance(feature, (LanceVector, NDArrayFloat)):
                high_resolution_features_request.append(feature)
            else:
                high_resolution_features_request.append(NDArrayFloat(values=feature.vector, shape=feature.shape))

    if points is not None:
        points_request = [points]
    else:
        points_request = None
    if labels is not None:
        labels_request = [labels]
    else:
        labels_request = None
    if bbox is not None:
        if bbox.is_normalized:
            bbox = bbox.denormalize(height=image.height, width=image.width)
        bbox_request = [[int(c) for c in bbox.xyxy_coords]]
    else:
        bbox_request = None

    # Note: As long as we don't store pixano-inference embeddings somewhere, no need to return them
    # More, it is VERY costly (around 13 sec) as it means to shape them and transfer them via HTTP.
    return_image_embedding = False  # reset_predictor and image_embedding is None

    request = ImageMaskGenerationRequest(
        image=image_request,
        image_embedding=image_embedding_request,
        high_resolution_features=high_resolution_features_request,
        reset_predictor=reset_predictor,
        boxes=bbox_request,
        points=points_request,
        labels=labels_request,
        num_multimask_outputs=1,
        multimask_output=False,
        return_image_embedding=return_image_embedding,
        model=source.name,
    )

    response: ImageMaskGenerationResponse = await client.image_mask_generation(request, **client_kwargs)

    inference_metadata = jsonable_encoder(
        {
            "timestamp": response.timestamp,
            "processing_time": response.processing_time,
            **response.metadata,
        }
    )

    mask_inference: PixanoInferenceCompressedRLE = response.data.masks[0][0]
    mask = CompressedRLE(
        id=shortuuid.uuid(),
        item_ref=image.item_ref,
        view_ref=ViewRef(name=image.table_name, id=image.id),
        entity_ref=EntityRef(name=entity.table_name, id=entity.id) if entity else EntityRef(name="", id=""),
        source_ref=SourceRef(id=source.id),
        inference_metadata=inference_metadata,
        **mask_inference.model_dump(),
    )
    score = response.data.scores.values[0]

    return mask, score, response.data.image_embedding, response.data.high_resolution_features


async def video_mask_generation(
    client: PixanoInferenceClient,
    media_dir: Path,
    video: list[SequenceFrame],
    source: Source,
    entity: Entity | None = None,
    bbox: BBox | None = None,
    points: list[list[int]] | None = None,
    labels: list[int] | None = None,
    **client_kwargs: Any,
) -> tuple[list[CompressedRLE], list[int], list[int]]:
    """Image mask generation task.

    Args:
        client: Pixano inference client.
        media_dir: Media directory.
        video: Video as list of SequenceFrame.
        source: The source refering to the model.
        entity: Entity to put objects in, if provided.
        bbox: Bounding box of the object in the original image.
        points: Points to generate mask for.
        labels: Labels of the points. If 0, the point is background else the point is foreground.
        client_kwargs: Additional kwargs for the client to be passed.

    Returns:
        tuple of the compressed RLE mask, its score, the source of the image, the image embeddings and the high
        resolution features The features are returned if not provided in the arguments otherwise None is returned.
    """
    if not isinstance(video, list):
        raise ValueError("Video format not currently supported, please use sequence frames.")
    video_request = [sf.url if is_url(sf.url) else sf.open(media_dir, "base64") for sf in video]

    if points is not None:
        points_request = [points]
    else:
        points_request = None
    if labels is not None:
        labels_request = [labels]
    else:
        labels_request = None
    if bbox is not None:
        if bbox.is_normalized:
            bbox = bbox.denormalize(height=video[0].height, width=video[0].width)
        bbox_request = [[int(c) for c in bbox.xyxy_coords]]
    else:
        bbox_request = None

    request = VideoMaskGenerationRequest(
        video=video_request,
        objects_ids=range(len(video)),
        frame_indexes=range(len(video)),
        boxes=bbox_request,
        points=points_request,
        labels=labels_request,
        model=source.name,
    )

    response: VideoMaskGenerationResponse = await client.video_mask_generation(request, **client_kwargs)

    inference_metadata = jsonable_encoder(
        {
            "timestamp": response.timestamp,
            "processing_time": response.processing_time,
            **response.metadata,
        }
    )

    masks: list[CompressedRLE] = []
    objects_ids: list[int] = []
    frame_indexes: list[int] = []

    if response.status == "SUCCESS":
        output: VideoMaskGenerationOutput = response.data
        entity_ref_id = shortuuid.uuid()  # used to check masks are from same generation when no entity in input

        for o_mask, obj_id, frame_idx in zip(output.masks, output.objects_ids, output.frame_indexes):
            image = video[frame_idx]
            mask_inference: PixanoInferenceCompressedRLE = o_mask
            mask = CompressedRLE(
                id=shortuuid.uuid(),
                item_ref=image.item_ref,
                view_ref=ViewRef(name=image.table_name, id=image.id),
                entity_ref=EntityRef(name=entity.table_name, id=entity.id)
                if entity
                else EntityRef(name="", id=entity_ref_id),
                source_ref=SourceRef(id=source.id),
                inference_metadata=inference_metadata,
                **mask_inference.model_dump(),
            )
            masks.append(mask)
            objects_ids.append(obj_id)
            frame_indexes.append(frame_idx)

    return masks, objects_ids, frame_indexes
