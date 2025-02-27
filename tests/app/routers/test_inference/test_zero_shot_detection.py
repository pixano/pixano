# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import patch

from fastapi.applications import FastAPI
from fastapi.encoders import jsonable_encoder
from starlette.testclient import TestClient

from pixano.app.models import AnnotationModel, EntityModel, TableInfo, ViewModel
from pixano.app.routers.inference.zero_shot_detection import ZeroShotOutput
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.features import BBox, Classification, Entity, EntityRef, Image, SchemaGroup
from pixano.features.types.schema_reference import ViewRef


@patch("pixano.app.routers.inference.zero_shot_detection.image_zero_shot_detection")
def test_call_text_image_conditional_generation(
    mock_zero_shot_detection,
    app_and_settings_with_client_copy: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client_copy

    image = ViewModel.from_row(
        Image(id="image", url="coco/1.jpg", format="jpg", width=100, height=100),
        TableInfo(name="image", group=SchemaGroup.VIEW.value, base_schema="Image"),
    )

    entity = EntityModel.from_row(
        Entity(id="entity"),
        TableInfo(name="entities", group=SchemaGroup.ENTITY.value, base_schema="Entity"),
    )

    expected_output = [
        ZeroShotOutput(
            bbox=AnnotationModel.from_row(
                BBox(
                    view_ref=ViewRef(id="image", name="image"),
                    entity_ref=EntityRef(id="entity", name="conversations"),
                    coords=[1, 2, 3, 4],
                    format="xyxy",
                    is_normalized=False,
                    confidence=0.5,
                ),
                TableInfo(name="box", group=SchemaGroup.ANNOTATION.value, base_schema="BBox"),
            ),
            classification=AnnotationModel.from_row(
                Classification(
                    view_ref=ViewRef(id="image", name="image"),
                    entity_ref=EntityRef(id="entity", name="conversations"),
                    labels=["a cat"],
                    confidences=[0.5],
                ),
                TableInfo(name="classes", group=SchemaGroup.ANNOTATION.value, base_schema="Classification"),
            ),
        )
    ]

    mock_zero_shot_detection.return_value = [
        (
            BBox(
                view_ref=ViewRef(id="image", name="image"),
                entity_ref=EntityRef(id="entity", name="conversations"),
                coords=[1, 2, 3, 4],
                format="xyxy",
                is_normalized=False,
                confidence=0.5,
            ),
            Classification(
                view_ref=ViewRef(id="image", name="image"),
                entity_ref=EntityRef(id="entity", name="conversations"),
                labels=["a cat"],
                confidences=[0.5],
            ),
        )
    ]

    json = jsonable_encoder(
        {
            "dataset_id": "dataset_image_bboxes_keypoint",
            "image": image,
            "entity": entity,
            "classes": ["a  cat", "a dog"],
            "model": "model",
            "box_table_name": "box",
            "class_table_name": "classes",
        }
    )

    url = "/inference/tasks/zero-shot-detection/image"

    response = client.post(url, json=json)
    assert response.status_code == 200
    for expected, actual in zip(expected_output, response.json()):
        assert expected.bbox.model_dump(exclude="id", exclude_timestamps=True) == AnnotationModel.model_validate(
            actual["bbox"]
        ).model_dump(exclude="id", exclude_timestamps=True)
        assert expected.classification.model_dump(
            exclude="id", exclude_timestamps=True
        ) == AnnotationModel.model_validate(actual["classification"]).model_dump(exclude="id", exclude_timestamps=True)

    dataset = Dataset.find(
        "dataset_image_bboxes_keypoint", directory=settings.library_dir, media_dir=settings.media_dir
    )
    sources = dataset.get_data("source", limit=10)
    assert len(sources) == 3

    # Execute again to check the source is not created again.
    response = client.post(url, json=json)
    assert response.status_code == 200
    for expected, actual in zip(expected_output, response.json()):
        assert expected.bbox.model_dump(exclude="id", exclude_timestamps=True) == AnnotationModel.model_validate(
            actual["bbox"]
        ).model_dump(exclude="id", exclude_timestamps=True)
        assert expected.classification.model_dump(
            exclude="id", exclude_timestamps=True
        ) == AnnotationModel.model_validate(actual["classification"]).model_dump(exclude="id", exclude_timestamps=True)

    dataset = Dataset.find(
        "dataset_image_bboxes_keypoint", directory=settings.library_dir, media_dir=settings.media_dir
    )
    sources = dataset.get_data("source", limit=10)
    assert len(sources) == 3
