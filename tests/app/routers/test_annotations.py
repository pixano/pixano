# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pixano.app.models.annotations import AnnotationModel
from pixano.app.routers.utils import get_model_from_row, get_models_from_rows
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset


@pytest.mark.parametrize(
    "table, ids, items_ids, limit, skip",
    [
        ("bbox_image", ["bbox_image_0", "bbox_image_1"], None, None, 0),
        ("bbox_image", None, ["0", "1"], None, 0),
        ("bbox_image", None, None, 2, 0),
        ("bbox_image", None, None, 2, None),
        ("bbox_image", None, None, 10, 2),
    ],
)
def test_get_annotations(
    table: str,
    ids: list[str] | None,
    items_ids: list[str] | None,
    limit: int | None,
    skip: int | None,
    app_and_settings: tuple[FastAPI, Settings],
    dataset_multi_view_tracking_and_image: Dataset,
):
    app, settings = app_and_settings

    url = "/annotations/dataset_multi_view_tracking_and_image/" + table + "/?"
    if ids is not None:
        url += "&".join(["ids=" + id for id in ids])
    if items_ids is not None:
        url += "&".join(["item_ids=" + id for id in items_ids])
    if limit is not None:
        url += "limit=" + str(limit)
    if skip is not None:
        url += "&skip=" + str(skip)

    expected_output = get_models_from_rows(
        table,
        AnnotationModel,
        dataset_multi_view_tracking_and_image.get_data(table, ids, limit, skip if skip is not None else 0, items_ids),
    )

    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 200
    for model_json in response.json():
        model = AnnotationModel.model_validate(model_json)
        assert model in expected_output
    assert len(response.json()) == len(expected_output)


def test_get_annotations_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings

    # Wrong dataset ID
    url = "/annotations/dataset_multi_view_tracking_and_image_wrong/bbox_image/"
    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    url = "/annotations/dataset_multi_view_tracking_and_image/bbox_wrong/"
    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the annotations group table."}

    # Wrong query parameters
    url = "/annotations/dataset_multi_view_tracking_and_image/bbox_image/?"
    for wrong_url_part in [
        "ids=bbox_image_0&item_ids=0",
        "ids=bbox_image_0&limit=10",
        "item_ids=0&limit=10",
    ]:
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert (
            "Invalid query parameters. ids and item_ids cannot be set at the same time." in response.json()["detail"]
        )

    # No annotations found
    url = "/annotations/dataset_multi_view_tracking_and_image/bbox_image/?item_ids=100"
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/bbox_image."}


def test_get_annotation(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    app, settings = app_and_settings

    expected_output = get_model_from_row(
        "bbox_image", AnnotationModel, dataset_multi_view_tracking_and_image.get_data("bbox_image", "bbox_image_0")
    )

    client = TestClient(app)
    response = client.get("/annotations/dataset_multi_view_tracking_and_image/bbox_image/bbox_image_0")
    assert response.status_code == 200
    model = AnnotationModel.model_validate(response.json())

    assert model == expected_output


def test_get_annotation_error(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings

    # Wrong dataset ID
    client = TestClient(app)
    response = client.get("/annotations/dataset_multi_view_tracking_and_image_wrong/bbox_image/bbox_image_0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.get("/annotations/dataset_multi_view_tracking_and_image/bbox_wrong/bbox_image_0")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the annotations group table."}

    # Wrong annotation ID
    response = client.get("/annotations/dataset_multi_view_tracking_and_image/bbox_image/bbox_image_100")
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/bbox_image."}


def test_create_annotations(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    annotations = dataset_multi_view_tracking_and_image.get_data("bbox_image", limit=2)
    new_annotations = [annotation.model_copy(deep=True) for annotation in annotations]
    for new_annotation in new_annotations:
        new_annotation.id = "new_" + new_annotation.id

    new_annotations_models = get_models_from_rows("bbox_image", AnnotationModel, new_annotations)

    client = TestClient(app)
    response = client.post(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_image/",
        json=[model.model_dump() for model in new_annotations_models],
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = AnnotationModel.model_validate(model_json)
        assert model in new_annotations_models
    assert len(response.json()) == len(new_annotations_models)

    # Check that the annotations were added to the dataset
    assert len(
        dataset_multi_view_tracking_and_image.get_data(
            "bbox_image", [new_annotation.id for new_annotation in new_annotations]
        )
    ) == len(new_annotations)


def test_create_annotations_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    good_data = get_models_from_rows(
        "bbox_image", AnnotationModel, dataset_multi_view_tracking_and_image.get_data("bbox_image", limit=2)
    )
    json_data = [model.model_dump() for model in good_data]

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/annotations/dataset_multi_view_tracking_and_image_wrong/bbox_image/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.post(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the annotations group table."}

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = [model.model_dump() for model in bad_data]
    response = client.post(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_image/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_create_annotation(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    annotation = dataset_multi_view_tracking_and_image.get_data("bbox_image", "bbox_image_0")
    new_annotation = annotation.model_copy(deep=True)
    new_annotation.id = "new_" + new_annotation.id

    new_annotation_model = get_model_from_row("bbox_image", AnnotationModel, new_annotation)

    client = TestClient(app)
    response = client.post(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_image/new_bbox_image_0",
        json=new_annotation_model.model_dump(),
    )

    assert response.status_code == 200
    model = AnnotationModel.model_validate(response.json())
    assert model == new_annotation_model

    # Check that the annotation was added to the dataset
    assert dataset_multi_view_tracking_and_image.get_data("bbox_image", "new_bbox_image_0") is not None


def test_create_annotation_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_model_from_row(
        "bbox_image",
        AnnotationModel,
        dataset_multi_view_tracking_and_image.get_data("bbox_image", "bbox_image_0"),
    )  # actually it is not good because id already exists but we look for errors so it is fine
    json_data = good_data.model_dump()

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/annotations/dataset_multi_view_tracking_and_image_wrong/bbox_image/bbox_image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.post(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_wrong/bbox_image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the annotations group table."}

    # Wrong annotation ID
    response = client.post(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_image/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_update_annotations(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    annotations = dataset_multi_view_tracking_and_image.get_data("bbox_image", limit=2)
    updated_annotations = [annotation.model_copy(deep=True) for annotation in annotations for i in range(2)]
    for i, updated_annotation in enumerate(updated_annotations):
        if i % 2:
            updated_annotation.id = "new_" + updated_annotation.id
        updated_annotation.coords[0] += i + 1

    updated_annotations_models = get_models_from_rows("bbox_image", AnnotationModel, updated_annotations)

    client = TestClient(app)
    response = client.put(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_image/",
        json=[model.model_dump() for model in updated_annotations_models],
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = AnnotationModel.model_validate(model_json)
        assert model in updated_annotations_models
    assert len(response.json()) == len(updated_annotations_models)

    # Check that the annotations were updated in the dataset
    updated_rows = dataset_multi_view_tracking_and_image.get_data(
        "bbox_image", [updated_annotation.id for updated_annotation in updated_annotations_models]
    )
    assert len(updated_rows) == len(updated_annotations)
    for updated_row in updated_rows:
        cur_annotation = None
        for updated_annotation in updated_annotations:
            if updated_annotation.id == updated_row.id:
                cur_annotation = updated_annotation
                break
        assert cur_annotation is not None
        assert cur_annotation.model_dump() == updated_row.model_dump()


def test_update_annotations_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_models_from_rows(
        "bbox_image", AnnotationModel, dataset_multi_view_tracking_and_image.get_data("bbox_image", limit=2)
    )
    json_data = [model.model_dump() for model in good_data]

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/annotations/dataset_multi_view_tracking_and_image_wrong/bbox_image/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.put(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the annotations group table."}

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = [model.model_dump() for model in bad_data]
    response = client.put(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_image/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_update_annotation(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    annotation = dataset_multi_view_tracking_and_image.get_data("bbox_image", "bbox_image_0")
    updated_annotation = annotation.model_copy(deep=True)
    updated_annotation.coords[0] += 1

    updated_annotation_model = get_model_from_row("bbox_image", AnnotationModel, updated_annotation)

    client = TestClient(app)
    response = client.put(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_image/bbox_image_0",
        json=updated_annotation_model.model_dump(),
    )

    assert response.status_code == 200
    model = AnnotationModel.model_validate(response.json())
    assert model == updated_annotation_model

    # Check that the annotation was updated in the dataset
    updated_row = dataset_multi_view_tracking_and_image.get_data("bbox_image", updated_annotation.id)
    assert updated_row is not None
    assert updated_row.model_dump() == updated_annotation.model_dump()


def test_update_annotation_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_model_from_row(
        "bbox_image",
        AnnotationModel,
        dataset_multi_view_tracking_and_image.get_data("bbox_image", "bbox_image_0"),
    )
    json_data = good_data.model_dump()

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/annotations/dataset_multi_view_tracking_and_image_wrong/bbox_image/bbox_image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.put(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_wrong/bbox_image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the annotations group table."}

    # Wrong annotation ID
    response = client.put(
        "/annotations/dataset_multi_view_tracking_and_image/bbox_image/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_delete_annotations(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    annotations = dataset_multi_view_tracking_and_image.get_data("bbox_image", limit=2)
    assert len(annotations) > 0
    deleted_ids = [annotation.id for annotation in annotations]

    client = TestClient(app)
    delete_url = (
        "/annotations/dataset_multi_view_tracking_and_image/bbox_image/"
        f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"
    )
    response = client.delete(delete_url)

    assert response.status_code == 200

    # Check that the annotations were deleted from the dataset
    assert len(dataset_multi_view_tracking_and_image.get_data("bbox_image", deleted_ids)) == 0


def test_delete_annotations_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    annotations = dataset_multi_view_tracking_and_image.get_data("bbox_image", limit=2)
    deleted_ids = [annotation.id for annotation in annotations]

    delete_ids_url = f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"

    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete(f"/annotations/dataset_multi_view_tracking_and_image_wrong/bbox_image/{delete_ids_url}")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.delete(f"/annotations/dataset_multi_view_tracking_and_image/bbox_wrong/{delete_ids_url}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the annotations group table."}


def test_delete_annotation(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    annotation = dataset_multi_view_tracking_and_image.get_data("bbox_image", "bbox_image_0")
    assert annotation is not None

    client = TestClient(app)
    response = client.delete("/annotations/dataset_multi_view_tracking_and_image/bbox_image/bbox_image_0")

    assert response.status_code == 200

    # Check that the annotation was deleted from the dataset
    assert dataset_multi_view_tracking_and_image.get_data("bbox_image", "bbox_image_0") is None


def test_delete_annotation_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete("/annotations/dataset_multi_view_tracking_and_image_wrong/bbox_image/bbox_image_0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.delete("/annotations/dataset_multi_view_tracking_and_image/bbox_wrong/bbox_image_0")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the annotations group table."}
