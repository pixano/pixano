# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel

from pixano.app.models import AnnotationModel, EntityModel, TableInfo, ViewModel
from pixano.app.routers.inference.utils import get_client_from_settings
from pixano.app.routers.utils import get_dataset
from pixano.app.settings import Settings, get_settings
from pixano.features import (
    BBox,
    CompressedRLE,
    Entity,
    Image,
    NDArrayFloat,
    SequenceFrame,
    is_image,
    is_sequence_frame,
)
from pixano.inference import image_mask_generation, video_mask_generation

from .utils import get_model_source


router = APIRouter(prefix="/tasks/mask-generation", tags=["Task", "Mask Generation"])

# keep track of the last image used, to avoid recomputing embeddings if not necessary
store_last_image_id: str = ""


class ImageMaskGenerationOutput(BaseModel):
    """Image mask generation output."""

    mask: AnnotationModel


@router.post(
    "/image",
    response_model=ImageMaskGenerationOutput,
)
async def call_image_mask_generation(
    dataset_id: Annotated[str, Body(embed=True)],
    image: Annotated[ViewModel, Body(embed=True)],
    model: Annotated[str, Body(embed=True)],
    mask_table_name: Annotated[str, Body(embed=True)],
    settings: Annotated[Settings, Depends(get_settings)],
    entity: Annotated[EntityModel | None, Body(embed=True)] = None,
    bbox: Annotated[BBox | None, Body(embed=True)] = None,
    points: Annotated[list[list[int]] | None, Body(embed=True)] = None,
    labels: Annotated[list[int] | None, Body(embed=True)] = None,
) -> ImageMaskGenerationOutput:
    """Perform image mask generation on an image.

    Args:
        dataset_id: The ID of the dataset to use.
        image: The image to use for detection.
        entity: The entity to use for detection.
        model: The name of the model to use.
        mask_table_name: The name of the table to use for masks in dataset.
        settings: App settings.
        bbox: Input bounding box or None.
        points: Input points or None.
        labels: Labels for input points, or None.

    Returns:
        The generated mask.
    """
    global store_last_image_id

    dataset = get_dataset(dataset_id=dataset_id, dir=settings.library_dir, media_dir=settings.media_dir)
    client = get_client_from_settings(settings=settings)

    if not is_image(dataset.schema.schemas[image.table_info.name]):
        raise HTTPException(status_code=400, detail="Image must be an image.")

    image_row: Image = image.to_row(dataset)
    entity_row: Entity | None = entity.to_row(dataset) if entity else None
    source = get_model_source(dataset=dataset, model=model)

    try:
        mask_output: tuple[
            CompressedRLE, float, NDArrayFloat | None, list[NDArrayFloat] | None
        ] = await image_mask_generation(
            client=client,
            source=source,
            media_dir=settings.media_dir,
            image=image_row,
            entity=entity_row,
            image_embedding=None,
            high_resolution_features=None,
            reset_predictor=store_last_image_id != image_row.id,
            bbox=bbox,
            points=points,
            labels=labels,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    # store image_id to check against for next generation
    store_last_image_id = image_row.id

    output: ImageMaskGenerationOutput = ImageMaskGenerationOutput(
        mask=AnnotationModel.from_row(
            row=mask_output[0],  # right now we don't use other ouputs (score, ...)
            table_info=TableInfo(name=mask_table_name, group="annotations", base_schema="CompressedRLE"),
        )
    )
    return output


class VideoMaskGenerationOutput(BaseModel):
    """Video masks generation output."""

    masks: list[AnnotationModel]


@router.post(
    "/video",
    response_model=VideoMaskGenerationOutput,
)
async def call_video_mask_generation(
    dataset_id: Annotated[str, Body(embed=True)],
    video: Annotated[list[ViewModel], Body(embed=True)],
    model: Annotated[str, Body(embed=True)],
    settings: Annotated[Settings, Depends(get_settings)],
    bbox: Annotated[BBox | None, Body(embed=True)] = None,
    points: Annotated[list[list[int]] | None, Body(embed=True)] = None,
    labels: Annotated[list[int] | None, Body(embed=True)] = None,
) -> VideoMaskGenerationOutput:
    """Perform video mask generation on a video.

    Args:
        dataset_id: The ID of the dataset to use.
        video: The video as a list of SequenceFrame (or a subset).
        model: The name of the model to use.
        settings: App settings.
        bbox: Input bounding box or None.
        points: Input points or None.
        labels: Labels for input points, or None.

    Returns:
        The generated masks.
    """
    dataset = get_dataset(dataset_id=dataset_id, dir=settings.library_dir, media_dir=settings.media_dir)
    client = get_client_from_settings(settings=settings)

    if not is_sequence_frame(dataset.schema.schemas[video[0].table_info.name]):
        raise HTTPException(status_code=400, detail="Video must be a list of SequenceFrame.")

    video_row: list[SequenceFrame] = [vm.to_row(dataset) for vm in video]
    source = get_model_source(dataset=dataset, model=model)

    try:
        mask_output: tuple[list[CompressedRLE], list[int], list[int]] = await video_mask_generation(
            client=client,
            source=source,
            media_dir=settings.media_dir,
            video=video_row,
            bbox=bbox,
            points=points,
            labels=labels,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    output: VideoMaskGenerationOutput = VideoMaskGenerationOutput(
        masks=[
            AnnotationModel.from_row(
                row=m,  # only use mask (don't send obj_ids & frame_idx => viewRef has the frame_index info)
                table_info=TableInfo(name="mask_table_name", group="annotations", base_schema="CompressedRLE"),
            )
            for m in mask_output[0]
        ]
    )
    return output
