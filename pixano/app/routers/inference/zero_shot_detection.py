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
from pixano.features import BBox, Classification, Entity, Image, is_image
from pixano.inference import image_zero_shot_detection

from .utils import get_model_source


router = APIRouter(prefix="/tasks/zero-shot-detection", tags=["Task", "Zero Shot Detection"])


class ZeroShotOutput(BaseModel):
    """Zero shot output."""

    bbox: AnnotationModel
    classification: AnnotationModel


@router.post(
    "/image",
    response_model=list[ZeroShotOutput],
)
async def call_image_zero_shot_detection(
    dataset_id: Annotated[str, Body(embed=True)],
    image: Annotated[ViewModel, Body(embed=True)],
    entity: Annotated[EntityModel, Body(embed=True)],
    classes: Annotated[list[str] | str, Body(embed=True)],
    model: Annotated[str, Body(embed=True)],
    box_table_name: Annotated[str, Body(embed=True)],
    class_table_name: Annotated[str, Body(embed=True)],
    settings: Annotated[Settings, Depends(get_settings)],
    box_threshold: Annotated[float, Body(embed=True)] = 0.3,
    text_threshold: Annotated[float, Body(embed=True)] = 0.2,
) -> list[ZeroShotOutput]:
    """Perform zero shot detection on an image.

    Args:
        dataset_id: The ID of the dataset to use.
        image: The image to use for detection.
        entity: The entity to use for detection.
        classes: Labels to detect.
        model: The name of the model to use.
        box_table_name: The name of the table to use for boxes in dataset.
        class_table_name: The name of the table to use for classifications in dataset.
        settings: App settings.
        box_threshold: Box threshold for detection in the image.
        text_threshold: Text threshold for detection in the image.

    Returns:
        The predicted bboxes and classifications.
    """
    dataset = get_dataset(dataset_id=dataset_id, dir=settings.library_dir, media_dir=settings.media_dir)
    client = get_client_from_settings(settings=settings)

    if not is_image(dataset.schema.schemas[image.table_info.name]):
        raise HTTPException(status_code=400, detail="Image must be an image.")

    image_row: Image = image.to_row(dataset)
    entity_row: Entity = entity.to_row(dataset)
    source = get_model_source(dataset=dataset, model=model)

    try:
        bboxes_and_classifications: list[tuple[BBox, Classification]] = await image_zero_shot_detection(
            client=client,
            source=source,
            media_dir=settings.media_dir,
            image=image_row,
            entity=entity_row,
            classes=classes,
            box_threshold=box_threshold,
            text_threshold=text_threshold,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    output: list[ZeroShotOutput] = []
    for bbox, classification in bboxes_and_classifications:
        bbox_model = AnnotationModel.from_row(
            row=bbox, table_info=TableInfo(name=box_table_name, group="annotations", base_schema="BBox")
        )
        classification_model = AnnotationModel.from_row(
            row=classification,
            table_info=TableInfo(name=class_table_name, group="annotations", base_schema="Classification"),
        )
        output.append(ZeroShotOutput(bbox=bbox_model, classification=classification_model))
    return output
