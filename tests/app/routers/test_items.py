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

from pixano.app.models.items import ItemModel
from pixano.app.routers.utils import get_model_from_row, get_models_from_rows
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset


@pytest.mark.parametrize(
    "table, ids, limit, skip",
    [
        ("item", ["0", "1"], None, 0),
        ("item", None, 2, 0),
        ("item", None, 2, None),
        ("item", None, 10, 2),
    ],
)
def test_get_items(
    table: str,
    ids: list[str] | None,
    limit: int | None,
    skip: int | None,
    app_and_settings: tuple[FastAPI, Settings],
    dataset_multi_view_tracking_and_image: Dataset,
):
    app, settings = app_and_settings

    url = "/items/dataset_multi_view_tracking_and_image/?"
    if ids is not None:
        url += "&".join(["ids=" + id for id in ids])
    if limit is not None:
        url += "limit=" + str(limit)
    if skip is not None:
        url += "&skip=" + str(skip)

    expected_output = get_models_from_rows(
        table,
        ItemModel,
        dataset_multi_view_tracking_and_image.get_data(table, ids, limit, skip if skip is not None else 0, None),
    )

    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 200
    for model_json in response.json():
        model = ItemModel.model_validate(model_json)
        assert model in expected_output
    assert len(response.json()) == len(expected_output)


def test_get_items_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings

    # Wrong dataset ID
    url = "/items/dataset_multi_view_tracking_and_image_wrong/"
    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong query parameters
    url = "/items/dataset_multi_view_tracking_and_image/?"
    for wrong_url_part in [
        "ids=0&limit=10",
    ]:
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert "Invalid query parameters. ids and limit cannot be set at the same time" in response.json()["detail"]

    # No items found
    url = "/items/dataset_multi_view_tracking_and_image/?ids=100"
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/item."}

    # Offset reached limit
    url = "/items/dataset_multi_view_tracking_and_image/?limit=10&skip=50"
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "Invalid query parameters. No results found at this offset"}


def test_get_item(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    app, settings = app_and_settings

    expected_output = get_model_from_row(
        "item", ItemModel, dataset_multi_view_tracking_and_image.get_data("item", "0")
    )

    client = TestClient(app)
    response = client.get("/items/dataset_multi_view_tracking_and_image/0")
    assert response.status_code == 200
    model = ItemModel.model_validate(response.json())

    assert model == expected_output


def test_get_item_error(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings

    # Wrong dataset ID
    client = TestClient(app)
    response = client.get("/items/dataset_multi_view_tracking_and_image_wrong/0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong item ID
    response = client.get("/items/dataset_multi_view_tracking_and_image/100")
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/item."}


def test_create_items(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    items = dataset_multi_view_tracking_and_image.get_data("item", limit=2)
    new_items = [item.model_copy(deep=True) for item in items]
    for new_item in new_items:
        new_item.id = "new_" + new_item.id

    new_items_models = get_models_from_rows("item", ItemModel, new_items)

    client = TestClient(app)
    response = client.post(
        "/items/dataset_multi_view_tracking_and_image/",
        json=jsonable_encoder(new_items_models),
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = ItemModel.model_validate(model_json)
        for new_model in new_items_models:
            if model.id == new_model.id:
                assert model.model_dump(exclude_timestamps=True) == new_model.model_dump(exclude_timestamps=True)
                break
    assert len(response.json()) == len(new_items_models)

    # Check that the items were added to the dataset
    assert len(dataset_multi_view_tracking_and_image.get_data("item", [new_item.id for new_item in new_items])) == len(
        new_items
    )


def test_create_items_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    good_data = get_models_from_rows(
        "item", ItemModel, dataset_multi_view_tracking_and_image.get_data("item", limit=2)
    )
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/items/dataset_multi_view_tracking_and_image_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = jsonable_encoder(bad_data)
    response = client.post(
        "/items/dataset_multi_view_tracking_and_image/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_create_item(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    item = dataset_multi_view_tracking_and_image.get_data("item", "0")
    new_item = item.model_copy(deep=True)
    new_item.id = "new_" + new_item.id

    new_item_model = get_model_from_row("item", ItemModel, new_item)

    client = TestClient(app)
    response = client.post(
        "/items/dataset_multi_view_tracking_and_image/new_0",
        json=jsonable_encoder(new_item_model),
    )

    assert response.status_code == 200
    model = ItemModel.model_validate(response.json())
    assert model.model_dump(exclude_timestamps=True) == new_item_model.model_dump(exclude_timestamps=True)

    # Check that the item was added to the dataset
    assert dataset_multi_view_tracking_and_image.get_data("item", "new_0") is not None


def test_create_item_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_model_from_row(
        "item",
        ItemModel,
        dataset_multi_view_tracking_and_image.get_data("item", "0"),
    )  # actually it is not good because id already exists but we look for errors so it is fine
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/items/dataset_multi_view_tracking_and_image_wrong/0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong item ID
    response = client.post(
        "/items/dataset_multi_view_tracking_and_image/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_update_items(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    items = dataset_multi_view_tracking_and_image.get_data("item", limit=2)
    updated_items = [item.model_copy(deep=True) for item in items for i in range(2)]
    for i, updated_item in enumerate(updated_items):
        if i % 2:
            updated_item.id = "new_" + updated_item.id
        updated_item.other_categories.append(i)

    updated_items_models = get_models_from_rows("item", ItemModel, updated_items)

    client = TestClient(app)
    response = client.put(
        "/items/dataset_multi_view_tracking_and_image/",
        json=jsonable_encoder(updated_items_models),
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = ItemModel.model_validate(model_json)
        for updated_model in updated_items_models:
            if model.id != updated_model.id:
                continue
            else:
                if model.id.startswith("new_"):
                    assert model.model_dump(exclude_timestamps=True) == updated_model.model_dump(
                        exclude_timestamps=True
                    )
                else:
                    assert model.model_dump(exclude="updated_at") == updated_model.model_dump(exclude="updated_at")
    assert len(response.json()) == len(updated_items_models)

    # Check that the items were updated in the dataset
    updated_rows = dataset_multi_view_tracking_and_image.get_data(
        "item", [updated_item.id for updated_item in updated_items_models]
    )
    assert len(updated_rows) == len(updated_items)
    for updated_row in updated_rows:
        cur_item = None
        for updated_item in updated_items:
            if updated_item.id == updated_row.id:
                cur_item = updated_item
                break
        assert cur_item is not None
        if cur_item.id.startswith("new_"):
            assert cur_item.model_dump(exclude_timestamps=True) == updated_row.model_dump(exclude_timestamps=True)
        else:
            assert cur_item.model_dump(exclude="updated_at") == updated_row.model_dump(exclude="updated_at")


def test_update_items_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_models_from_rows(
        "item", ItemModel, dataset_multi_view_tracking_and_image.get_data("item", limit=2)
    )
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/items/dataset_multi_view_tracking_and_image_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = jsonable_encoder(bad_data)
    response = client.put(
        "/items/dataset_multi_view_tracking_and_image/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_update_item(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    item = dataset_multi_view_tracking_and_image.get_data("item", "0")
    updated_item = item.model_copy(deep=True)
    updated_item.other_categories.append(1)

    updated_item_model = get_model_from_row("item", ItemModel, updated_item)

    client = TestClient(app)
    response = client.put(
        "/items/dataset_multi_view_tracking_and_image/0",
        json=jsonable_encoder(updated_item_model),
    )

    assert response.status_code == 200
    model = ItemModel.model_validate(response.json())
    assert model.model_dump(exclude="updated_at") == updated_item_model.model_dump(exclude="updated_at")

    # Check that the item was updated in the dataset
    updated_row = dataset_multi_view_tracking_and_image.get_data("item", updated_item.id)
    assert updated_row is not None
    assert updated_row.model_dump(exclude="updated_at") == updated_item.model_dump(exclude="updated_at")
    assert updated_row.updated_at > item.updated_at


def test_update_item_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_model_from_row(
        "item",
        ItemModel,
        dataset_multi_view_tracking_and_image.get_data("item", "0"),
    )
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/items/dataset_multi_view_tracking_and_image_wrong/0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong item ID
    response = client.put(
        "/items/dataset_multi_view_tracking_and_image/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_delete_items(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    items = dataset_multi_view_tracking_and_image.get_data("item", limit=2)
    assert len(items) > 0
    deleted_ids = [item.id for item in items]

    client = TestClient(app)
    delete_url = "/items/dataset_multi_view_tracking_and_image/" f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"
    response = client.delete(delete_url)

    assert response.status_code == 200

    # Check that the items were deleted from the dataset
    assert len(dataset_multi_view_tracking_and_image.get_data("item", deleted_ids)) == 0


def test_delete_items_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    items = dataset_multi_view_tracking_and_image.get_data("item", limit=2)
    deleted_ids = [item.id for item in items]

    delete_ids_url = f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"

    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete(f"/items/dataset_multi_view_tracking_and_image_wrong/{delete_ids_url}")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }


def test_delete_item(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    item = dataset_multi_view_tracking_and_image.get_data("item", "0")
    assert item is not None

    client = TestClient(app)
    response = client.delete("/items/dataset_multi_view_tracking_and_image/0")

    assert response.status_code == 200

    # Check that the item was deleted from the dataset
    assert dataset_multi_view_tracking_and_image.get_data("item", "0") is None


def test_delete_item_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete("/items/dataset_multi_view_tracking_and_image_wrong/0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }
