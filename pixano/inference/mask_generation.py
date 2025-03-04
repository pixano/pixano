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
from pixano_inference.pydantic.tasks import ImageMaskGenerationRequest, ImageMaskGenerationResponse
from pixano_inference.utils import is_url

from pixano.features import BBox, CompressedRLE, Image, NDArrayFloat, Source, ViewEmbedding
from pixano.features.schemas.entities.entity import Entity
from pixano.features.types.schema_reference import EntityRef, SourceRef, ViewRef


async def image_mask_generation(
    client: PixanoInferenceClient,
    media_dir: Path,
    image: Image,
    entity: Entity,
    source: Source,
    image_embedding: ViewEmbedding | NDArrayFloat | LanceVector | None = None,
    high_resolution_features: list[ViewEmbedding] | list[NDArrayFloat] | list[LanceVector] | None = None,
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

    return_image_embedding = image_embedding is None

    request = ImageMaskGenerationRequest(
        image=image_request,
        image_embedding=image_embedding_request,
        high_resolution_features=high_resolution_features_request,
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
        entity_ref=EntityRef(name=entity.table_name, id=entity.id),
        source_ref=SourceRef(id=source.id),
        inference_metadata=inference_metadata,
        **mask_inference.model_dump(),
    )
    score = response.data.scores.values[0]

    return mask, score, response.data.image_embedding, response.data.high_resolution_features
