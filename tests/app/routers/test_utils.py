# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from fastapi import HTTPException
from fastapi.applications import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from pixano.app.models import AnnotationModel, BaseSchemaModel
from pixano.app.routers.utils import (
    create_rows,
    delete_rows,
    get_model_from_row,
    get_models_from_rows,
    update_rows,
    validate_group,
)
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.features import BBox
from pixano.features.schemas.schema_group import SchemaGroup


@pytest.mark.skip(reason="Already done in test_datasets.py")
def test_get_dataset(app_and_settings: tuple[FastAPI, Settings]):
    pass


def test_assert_table_in_group(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings
    client = TestClient(app)

    response = client.get("/annotations/dataset_multi_view_tracking_and_image/bbox_image/?limit=1")
    assert response.status_code == 200

    response = client.get("/annotations/dataset_image_bboxes_keypoint/keypoints/?limit=1")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table keypoints is not in the annotations group table."}


def test_validate_group():
    assert validate_group("annotations") == SchemaGroup.ANNOTATION
    assert validate_group(SchemaGroup.ANNOTATION) == SchemaGroup.ANNOTATION
    assert validate_group(SchemaGroup.ANNOTATION, {SchemaGroup.ANNOTATION}) == SchemaGroup.ANNOTATION

    with pytest.raises(HTTPException) as error:
        validate_group("wrong_input")
    assert error.value.status_code == 400
    assert error.value.detail == "Group wrong_input is not a SchemaGroup."

    with pytest.raises(HTTPException) as error:
        validate_group(SchemaGroup.ANNOTATION, {SchemaGroup.VIEW})
    assert error.value.status_code == 400
    assert error.value.detail == f"Group {SchemaGroup.ANNOTATION.value} is not valid."


def test_get_rows(
    app_and_settings: tuple[FastAPI, Settings], two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image
):
    app, settings = app_and_settings
    client = TestClient(app)

    response = client.get("/annotations/dataset_multi_view_tracking_and_image/bbox_image/?limit=2")
    assert response.status_code == 200
    assert response.json() == jsonable_encoder(two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image)

    response = client.get("/annotations/dataset_multi_view_tracking_and_image/bbox_image/?limit=2&ids=0")
    assert response.status_code == 400
    assert "Invalid query parameters. ids and limit cannot be set at the same time" in response.json()["detail"]

    response = client.get("/annotations/dataset_multi_view_tracking_and_image/bbox_image/?ids=nothing")
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/bbox_image."}

    response = client.get("/annotations/dataset_multi_view_tracking_and_image/bbox_image/?limit=10&skip=200")
    assert response.status_code == 404
    assert response.json() == {"detail": "Invalid query parameters. No results found at this offset"}


def test_get_model_from_row(
    two_difficult_bboxes_from_dataset_multiview_tracking_and_image,
    two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image,
):
    row = two_difficult_bboxes_from_dataset_multiview_tracking_and_image[0]
    model = get_model_from_row("bbox_image", AnnotationModel, row)
    assert model == two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image[0]

    ## Test exceptions
    # Test wrong input
    with pytest.raises(HTTPException) as error:
        model = get_model_from_row("bbox_image", "wrong_input", row)
    assert error.value.status_code == 500
    assert error.value.detail == "Model type is not a subclass of BaseModelSchema."

    # Test wrong model type
    with pytest.raises(HTTPException) as error:
        model = get_model_from_row("bbox_image", BaseSchemaModel, row)
    assert error.value.status_code == 500
    assert error.value.detail == "Model type not correct."

    # Test unregistered schema type
    class BBoxUnregistered:
        pass

    row_unregistered = BBoxUnregistered()
    with pytest.raises(HTTPException) as error:
        model = get_model_from_row("bboxes", AnnotationModel, row_unregistered)
    assert error.value.status_code == 500
    assert error.value.detail == "Schema type not found in registry."


def test_get_model_from_rows(
    two_difficult_bboxes_from_dataset_multiview_tracking_and_image,
    two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image,
):
    models = get_models_from_rows(
        "bbox_image", AnnotationModel, two_difficult_bboxes_from_dataset_multiview_tracking_and_image
    )
    assert models == two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image


def test_delete_rows(dataset_multi_view_tracking_and_image_copy: Dataset):
    ids_not_found = delete_rows(
        dataset_multi_view_tracking_and_image_copy, "bbox_image", ["bbox_image_0", "bbox_image_1", "bbox_unknown"]
    )

    assert ids_not_found == ["bbox_unknown"]
    assert dataset_multi_view_tracking_and_image_copy.get_data("bbox_image", ["bbox_image_0", "bbox_image_1"]) == []

    with pytest.raises(HTTPException) as error:
        ids_not_found = delete_rows(dataset_multi_view_tracking_and_image_copy, "bbox_image", "wrong_input")
    assert error.value.status_code == 400
    assert error.value.detail == "Invalid query parameters. ids and item_ids cannot be set at the same time"


def test_update_rows(
    dataset_multi_view_tracking_and_image_copy: Dataset,
    two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image,
):
    for model in two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image:
        model.data["confidence"] = 0.5
    new_model = type(two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image[0]).model_validate(
        two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image[0].model_dump()
    )
    new_model.id = "bbox_image_new"
    models = two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image + [new_model]
    updated_rows = update_rows(dataset_multi_view_tracking_and_image_copy, "bbox_image", models)

    for model, row in zip(models, updated_rows):
        if row.id.endswith("_new"):
            assert AnnotationModel.from_row(row, table_info=model.table_info).model_dump(
                exclude_timestamps=True
            ) == model.model_dump(exclude_timestamps=True)
        else:
            assert AnnotationModel.from_row(row, table_info=model.table_info).model_dump(
                exclude="updated_at"
            ) == model.model_dump(exclude="updated_at")
    assert [
        row.model_dump(exclude_timestamps=True) if row.id.endswith("_new") else row.model_dump(exclude="updated_at")
        for row in dataset_multi_view_tracking_and_image_copy.get_data(
            "bbox_image", ["bbox_image_0", "bbox_image_1", "bbox_image_new"]
        )
    ] == [
        row.model_dump(exclude_timestamps=True) if row.id.endswith("_new") else row.model_dump(exclude="updated_at")
        for row in updated_rows
    ]

    ## Test exceptions
    # Test wrong input
    with pytest.raises(HTTPException) as error:
        update_rows(dataset_multi_view_tracking_and_image_copy, "bbox_image", ["wrong_input"])
    assert error.value.status_code == 400
    assert error.value.detail == "Invalid data."

    # Test wrong data
    with pytest.raises(HTTPException) as error:
        update_rows(dataset_multi_view_tracking_and_image_copy, "bbox_image", [new_model, new_model])


def test_create_rows(
    dataset_multi_view_tracking_and_image_copy: Dataset,
    two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image,
):
    new_models = []
    for model in two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image:
        new_model = type(model).model_validate(model.model_dump())
        new_model.id = f"{model.id}_new"
        new_models.append(new_model)

    created_rows = create_rows(dataset_multi_view_tracking_and_image_copy, "bbox_image", new_models)

    assert [model.model_dump(exclude_timestamps=True) for model in new_models] == [
        AnnotationModel.from_row(row, table_info=model.table_info).model_dump(exclude_timestamps=True)
        for model, row in zip(new_models, created_rows)
    ]

    assert [
        row.model_dump(exclude_timestamps=True)
        for row in dataset_multi_view_tracking_and_image_copy.get_data(
            "bbox_image", [model.id for model in new_models]
        )
    ] == [row.model_dump(exclude_timestamps=True) for row in created_rows]

    ## Test exceptions
    # Test wrong input
    with pytest.raises(HTTPException) as error:
        create_rows(dataset_multi_view_tracking_and_image_copy, "bbox_image", ["wrong_input"])
    assert error.value.status_code == 400
    assert error.value.detail == "Invalid data."

    # Test wrong data
    with pytest.raises(HTTPException) as error:
        create_rows(dataset_multi_view_tracking_and_image_copy, "bbox_image", [new_models[0], new_models[0]])
