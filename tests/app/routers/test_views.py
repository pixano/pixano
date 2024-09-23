# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from pixano.app.models.views import ViewModel
from pixano.app.routers.utils import get_model_from_row, get_models_from_rows
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset


@pytest.mark.parametrize(
    "table, ids, items_ids, limit, skip",
    [
        ("image", ["image_0", "image_1"], None, None, 0),
        ("image", None, ["0", "1"], None, 0),
        ("image", None, None, 2, 0),
        ("image", None, None, 2, None),
        ("image", None, None, 10, 2),
        ("image", None, ["0", "1", "2"], 10, 1),
    ],
)
def test_get_views(
    table: str,
    ids: list[str] | None,
    items_ids: list[str] | None,
    limit: int | None,
    skip: int | None,
    app_and_settings: tuple[FastAPI, Settings],
    dataset_multi_view_tracking_and_image: Dataset,
):
    app, settings = app_and_settings

    url = "/views/dataset_multi_view_tracking_and_image/" + table + "/?"
    if ids is not None:
        url += "&".join(["ids=" + id for id in ids])
    if items_ids is not None:
        url += "&".join(["item_ids=" + id for id in items_ids])
    if limit is not None:
        if url[-1] not in ["&", "?"]:
            url += "&"
        url += "limit=" + str(limit)
    if skip is not None:
        url += "&skip=" + str(skip)

    expected_output = get_models_from_rows(
        table,
        ViewModel,
        dataset_multi_view_tracking_and_image.get_data(table, ids, limit, skip if skip is not None else 0, items_ids),
    )

    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 200
    for model_json in response.json():
        model = ViewModel.model_validate(model_json)
        assert model in expected_output
    assert len(response.json()) == len(expected_output)


def test_get_views_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings

    # Wrong dataset ID
    url = "/views/dataset_multi_view_tracking_and_image_wrong/image/"
    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    url = "/views/dataset_multi_view_tracking_and_image/view_wrong/"
    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "Table view_wrong is not in the views group table."}

    # Wrong query parameters
    url = "/views/dataset_multi_view_tracking_and_image/image/?"
    for wrong_url_part in [
        "ids=image_0&item_ids=0",
    ]:
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert "Invalid query parameters. ids and item_ids cannot be set at the same time" in response.json()["detail"]
    for wrong_url_part in [
        "ids=image_0&limit=10",
    ]:
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert "Invalid query parameters. ids and limit cannot be set at the same time" in response.json()["detail"]

    # No views found
    url = "/views/dataset_multi_view_tracking_and_image/image/?item_ids=100"
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/image."}


def test_get_view(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    app, settings = app_and_settings

    expected_output = get_model_from_row(
        "image",
        ViewModel,
        dataset_multi_view_tracking_and_image.get_data("image", "image_0"),
    )

    client = TestClient(app)
    response = client.get("/views/dataset_multi_view_tracking_and_image/image/image_0")
    assert response.status_code == 200
    model = ViewModel.model_validate(response.json())

    assert model == expected_output


def test_get_view_error(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings

    # Wrong dataset ID
    client = TestClient(app)
    response = client.get("/views/dataset_multi_view_tracking_and_image_wrong/image/image_0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.get("/views/dataset_multi_view_tracking_and_image/view_wrong/image_0")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table view_wrong is not in the views group table."}

    # Wrong view ID
    response = client.get("/views/dataset_multi_view_tracking_and_image/image/image_100")
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/image."}


def test_create_views(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    views = dataset_multi_view_tracking_and_image.get_data("image", limit=2)
    new_views = [view.model_copy(deep=True) for view in views]
    for new_view in new_views:
        new_view.id = "new_" + new_view.id

    new_views_models = [
        model.model_dump(exclude_timestamps=True) for model in get_models_from_rows("image", ViewModel, new_views)
    ]

    client = TestClient(app)
    response = client.post(
        "/views/dataset_multi_view_tracking_and_image/image/",
        json=jsonable_encoder(new_views_models),
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = ViewModel.model_validate(model_json).model_dump(exclude_timestamps=True)
        assert model in new_views_models
    assert len(response.json()) == len(new_views_models)

    # Check that the views were added to the dataset
    assert len(
        dataset_multi_view_tracking_and_image.get_data("image", [new_view.id for new_view in new_views])
    ) == len(new_views)


def test_create_views_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    good_data = get_models_from_rows(
        "image", ViewModel, dataset_multi_view_tracking_and_image.get_data("image", limit=2)
    )
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/views/dataset_multi_view_tracking_and_image_wrong/image/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.post(
        "/views/dataset_multi_view_tracking_and_image/view_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table view_wrong is not in the views group table."}

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = jsonable_encoder(bad_data)
    response = client.post(
        "/views/dataset_multi_view_tracking_and_image/image/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_create_view(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    view = dataset_multi_view_tracking_and_image.get_data("image", "image_0")
    new_view = view.model_copy(deep=True)
    new_view.id = "new_" + new_view.id

    new_view_model = get_model_from_row("image", ViewModel, new_view)

    client = TestClient(app)
    response = client.post(
        "/views/dataset_multi_view_tracking_and_image/image/new_image_0",
        json=jsonable_encoder(new_view_model),
    )

    assert response.status_code == 200
    model = ViewModel.model_validate(response.json())
    assert model.model_dump(exclude_timestamps=True) == new_view_model.model_dump(exclude_timestamps=True)

    # Check that the view was added to the dataset
    assert dataset_multi_view_tracking_and_image.get_data("image", "new_image_0") is not None


def test_create_view_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_model_from_row(
        "image",
        ViewModel,
        dataset_multi_view_tracking_and_image.get_data("image", "image_0"),
    )  # actually it is not good because id already exists but we look for errors so it is fine
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/views/dataset_multi_view_tracking_and_image_wrong/image/image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.post(
        "/views/dataset_multi_view_tracking_and_image/view_wrong/image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table view_wrong is not in the views group table."}

    # Wrong view ID
    response = client.post(
        "/views/dataset_multi_view_tracking_and_image/image/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_update_views(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    views = dataset_multi_view_tracking_and_image.get_data("image", limit=2)
    updated_views = [view.model_copy(deep=True) for view in views for i in range(2)]
    for i, updated_view in enumerate(updated_views):
        if i % 2:
            updated_view.id = "new_" + updated_view.id
        updated_view.width = i + 1

    updated_views_models = get_models_from_rows("image", ViewModel, updated_views)

    client = TestClient(app)
    response = client.put(
        "/views/dataset_multi_view_tracking_and_image/image/",
        json=jsonable_encoder(updated_views_models),
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = ViewModel.model_validate(model_json)
        assert model.model_dump(exclude_timestamps=True) in [
            u_model.model_dump(exclude_timestamps=True) for u_model in updated_views_models
        ]
    assert len(response.json()) == len(updated_views_models)

    # Check that the views were updated in the dataset
    updated_rows = dataset_multi_view_tracking_and_image.get_data(
        "image", [updated_view.id for updated_view in updated_views_models]
    )
    assert len(updated_rows) == len(updated_views)
    for updated_row in updated_rows:
        cur_view = None
        for updated_view in updated_views:
            if updated_view.id == updated_row.id:
                cur_view = updated_view
                break
        assert cur_view is not None
        if cur_view.id.startswith("new_"):
            assert cur_view.model_dump(exclude_timestamps=True) == updated_row.model_dump(exclude_timestamps=True)
        else:
            assert cur_view.model_dump(exclude="updated_at") == updated_row.model_dump(exclude="updated_at")


def test_update_views_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_models_from_rows(
        "image", ViewModel, dataset_multi_view_tracking_and_image.get_data("image", limit=2)
    )
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/views/dataset_multi_view_tracking_and_image_wrong/image/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.put(
        "/views/dataset_multi_view_tracking_and_image/view_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table view_wrong is not in the views group table."}

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = jsonable_encoder(bad_data)
    response = client.put(
        "/views/dataset_multi_view_tracking_and_image/image/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_update_view(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    view = dataset_multi_view_tracking_and_image.get_data("image", "image_0")
    updated_view = view.model_copy(deep=True)
    updated_view.width = 10

    updated_view_model = get_model_from_row("image", ViewModel, updated_view)

    client = TestClient(app)
    response = client.put(
        "/views/dataset_multi_view_tracking_and_image/image/image_0",
        json=jsonable_encoder(updated_view_model),
    )

    assert response.status_code == 200
    model = ViewModel.model_validate(response.json())
    assert model.model_dump(exclude="updated_at") == updated_view_model.model_dump(exclude="updated_at")

    # Check that the view was updated in the dataset
    updated_row = dataset_multi_view_tracking_and_image.get_data("image", updated_view.id)
    assert updated_row is not None
    assert updated_row.model_dump(exclude="updated_at") == updated_view.model_dump(exclude="updated_at")


def test_update_view_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_model_from_row(
        "image",
        ViewModel,
        dataset_multi_view_tracking_and_image.get_data("image", "image_0"),
    )
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/views/dataset_multi_view_tracking_and_image_wrong/image/image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.put(
        "/views/dataset_multi_view_tracking_and_image/view_wrong/image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table view_wrong is not in the views group table."}

    # Wrong view ID
    response = client.put(
        "/views/dataset_multi_view_tracking_and_image/image/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_delete_views(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    views = dataset_multi_view_tracking_and_image.get_data("image", limit=2)
    assert len(views) > 0
    deleted_ids = [view.id for view in views]

    client = TestClient(app)
    delete_url = (
        "/views/dataset_multi_view_tracking_and_image/image/" f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"
    )
    response = client.delete(delete_url)

    assert response.status_code == 200

    # Check that the views were deleted from the dataset
    assert len(dataset_multi_view_tracking_and_image.get_data("image", deleted_ids)) == 0


def test_delete_views_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    views = dataset_multi_view_tracking_and_image.get_data("image", limit=2)
    deleted_ids = [view.id for view in views]

    delete_ids_url = f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"

    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete(f"/views/dataset_multi_view_tracking_and_image_wrong/image/{delete_ids_url}")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.delete(f"/views/dataset_multi_view_tracking_and_image/view_wrong/{delete_ids_url}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table view_wrong is not in the views group table."}


def test_delete_view(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    view = dataset_multi_view_tracking_and_image.get_data("image", "image_0")
    assert view is not None

    client = TestClient(app)
    response = client.delete("/views/dataset_multi_view_tracking_and_image/image/image_0")

    assert response.status_code == 200

    # Check that the view was deleted from the dataset
    assert dataset_multi_view_tracking_and_image.get_data("image", "image_0") is None


def test_delete_view_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete("/views/dataset_multi_view_tracking_and_image_wrong/image/image_0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.delete("/views/dataset_multi_view_tracking_and_image/view_wrong/image_0")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table view_wrong is not in the views group table."}
