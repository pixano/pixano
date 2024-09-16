# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pixano.app.models.entities import EntityModel
from pixano.app.routers.utils import get_model_from_row, get_models_from_rows
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset


@pytest.mark.parametrize(
    "table, ids, items_ids, limit, skip",
    [
        ("entity_image", ["entity_image_0", "entity_image_1"], None, None, 0),
        ("entity_image", None, ["0", "1"], None, 0),
        ("entity_image", None, None, 2, 0),
        ("entity_image", None, None, 2, None),
        ("entity_image", None, None, 10, 2),
        ("entities_video", None, ["2"], 2, 1),
    ],
)
def test_get_entities(
    table: str,
    ids: list[str] | None,
    items_ids: list[str] | None,
    limit: int | None,
    skip: int | None,
    app_and_settings: tuple[FastAPI, Settings],
    dataset_multi_view_tracking_and_image: Dataset,
):
    app, settings = app_and_settings

    url = "/entities/dataset_multi_view_tracking_and_image/" + table + "/?"
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
        EntityModel,
        dataset_multi_view_tracking_and_image.get_data(table, ids, limit, skip if skip is not None else 0, items_ids),
    )

    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 200
    for model_json in response.json():
        model = EntityModel.model_validate(model_json)
        assert model in expected_output
    assert len(response.json()) == len(expected_output)


def test_get_entities_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings

    # Wrong dataset ID
    url = "/entities/dataset_multi_view_tracking_and_image_wrong/entity_image/"
    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    url = "/entities/dataset_multi_view_tracking_and_image/bbox_wrong/"
    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the entities group table."}

    # Wrong query parameters
    url = "/entities/dataset_multi_view_tracking_and_image/entity_image/?"
    for wrong_url_part in [
        "ids=entity_image_0&item_ids=0",
    ]:
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert "Invalid query parameters. ids and item_ids cannot be set at the same time" in response.json()["detail"]
    for wrong_url_part in [
        "ids=entity_image_0&limit=10",
    ]:
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert "Invalid query parameters. ids and limit cannot be set at the same time" in response.json()["detail"]

    # No entities found
    url = "/entities/dataset_multi_view_tracking_and_image/entity_image/?item_ids=100"
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/entity_image."}


def test_get_entity(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    app, settings = app_and_settings

    expected_output = get_model_from_row(
        "entity_image", EntityModel, dataset_multi_view_tracking_and_image.get_data("entity_image", "entity_image_0")
    )

    client = TestClient(app)
    response = client.get("/entities/dataset_multi_view_tracking_and_image/entity_image/entity_image_0")
    assert response.status_code == 200
    model = EntityModel.model_validate(response.json())

    assert model == expected_output


def test_get_entity_error(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings

    # Wrong dataset ID
    client = TestClient(app)
    response = client.get("/entities/dataset_multi_view_tracking_and_image_wrong/entity_image/entity_image_0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.get("/entities/dataset_multi_view_tracking_and_image/bbox_wrong/entity_image_0")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the entities group table."}

    # Wrong entity ID
    response = client.get("/entities/dataset_multi_view_tracking_and_image/entity_image/entity_image_100")
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/entity_image."}


def test_create_entities(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    entities = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    new_entities = [entity.model_copy(deep=True) for entity in entities]
    for new_entity in new_entities:
        new_entity.id = "new_" + new_entity.id

    new_entities_models = get_models_from_rows("entity_image", EntityModel, new_entities)

    client = TestClient(app)
    response = client.post(
        "/entities/dataset_multi_view_tracking_and_image/entity_image/",
        json=[model.model_dump() for model in new_entities_models],
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = EntityModel.model_validate(model_json)
        assert model in new_entities_models
    assert len(response.json()) == len(new_entities_models)

    # Check that the entities were added to the dataset
    assert len(
        dataset_multi_view_tracking_and_image.get_data("entity_image", [new_entity.id for new_entity in new_entities])
    ) == len(new_entities)


def test_create_entities_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    good_data = get_models_from_rows(
        "entity_image", EntityModel, dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    )
    json_data = [model.model_dump() for model in good_data]

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/entities/dataset_multi_view_tracking_and_image_wrong/entity_image/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.post(
        "/entities/dataset_multi_view_tracking_and_image/bbox_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the entities group table."}

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = [model.model_dump() for model in bad_data]
    response = client.post(
        "/entities/dataset_multi_view_tracking_and_image/entity_image/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_create_entity(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    entity = dataset_multi_view_tracking_and_image.get_data("entity_image", "entity_image_0")
    new_entity = entity.model_copy(deep=True)
    new_entity.id = "new_" + new_entity.id

    new_entity_model = get_model_from_row("entity_image", EntityModel, new_entity)

    client = TestClient(app)
    response = client.post(
        "/entities/dataset_multi_view_tracking_and_image/entity_image/new_entity_image_0",
        json=new_entity_model.model_dump(),
    )

    assert response.status_code == 200
    model = EntityModel.model_validate(response.json())
    assert model == new_entity_model

    # Check that the entity was added to the dataset
    assert dataset_multi_view_tracking_and_image.get_data("entity_image", "new_entity_image_0") is not None


def test_create_entity_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_model_from_row(
        "entity_image",
        EntityModel,
        dataset_multi_view_tracking_and_image.get_data("entity_image", "entity_image_0"),
    )  # actually it is not good because id already exists but we look for errors so it is fine
    json_data = good_data.model_dump()

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/entities/dataset_multi_view_tracking_and_image_wrong/entity_image/entity_image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.post(
        "/entities/dataset_multi_view_tracking_and_image/bbox_wrong/entity_image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the entities group table."}

    # Wrong entity ID
    response = client.post(
        "/entities/dataset_multi_view_tracking_and_image/entity_image/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_update_entities(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    entities = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    updated_entities = [entity.model_copy(deep=True) for entity in entities for i in range(2)]
    for i, updated_entity in enumerate(updated_entities):
        if i % 2:
            updated_entity.id = "new_" + updated_entity.id
        updated_entity.category += "i + 1"

    updated_entities_models = get_models_from_rows("entity_image", EntityModel, updated_entities)

    client = TestClient(app)
    response = client.put(
        "/entities/dataset_multi_view_tracking_and_image/entity_image/",
        json=[model.model_dump() for model in updated_entities_models],
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = EntityModel.model_validate(model_json)
        assert model in updated_entities_models
    assert len(response.json()) == len(updated_entities_models)

    # Check that the entities were updated in the dataset
    updated_rows = dataset_multi_view_tracking_and_image.get_data(
        "entity_image", [updated_entity.id for updated_entity in updated_entities_models]
    )
    assert len(updated_rows) == len(updated_entities)
    for updated_row in updated_rows:
        cur_entity = None
        for updated_entity in updated_entities:
            if updated_entity.id == updated_row.id:
                cur_entity = updated_entity
                break
        assert cur_entity is not None
        assert cur_entity.model_dump() == updated_row.model_dump()


def test_update_entities_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_models_from_rows(
        "entity_image", EntityModel, dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    )
    json_data = [model.model_dump() for model in good_data]

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/entities/dataset_multi_view_tracking_and_image_wrong/entity_image/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.put(
        "/entities/dataset_multi_view_tracking_and_image/bbox_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the entities group table."}

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = [model.model_dump() for model in bad_data]
    response = client.put(
        "/entities/dataset_multi_view_tracking_and_image/entity_image/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_update_entity(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    entity = dataset_multi_view_tracking_and_image.get_data("entity_image", "entity_image_0")
    updated_entity = entity.model_copy(deep=True)
    updated_entity.category += "1"

    updated_entity_model = get_model_from_row("entity_image", EntityModel, updated_entity)

    client = TestClient(app)
    response = client.put(
        "/entities/dataset_multi_view_tracking_and_image/entity_image/entity_image_0",
        json=updated_entity_model.model_dump(),
    )

    assert response.status_code == 200
    model = EntityModel.model_validate(response.json())
    assert model == updated_entity_model

    # Check that the entity was updated in the dataset
    updated_row = dataset_multi_view_tracking_and_image.get_data("entity_image", updated_entity.id)
    assert updated_row is not None
    assert updated_row.model_dump() == updated_entity.model_dump()


def test_update_entity_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_model_from_row(
        "entity_image",
        EntityModel,
        dataset_multi_view_tracking_and_image.get_data("entity_image", "entity_image_0"),
    )
    json_data = good_data.model_dump()

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/entities/dataset_multi_view_tracking_and_image_wrong/entity_image/entity_image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.put(
        "/entities/dataset_multi_view_tracking_and_image/bbox_wrong/entity_image_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the entities group table."}

    # Wrong entity ID
    response = client.put(
        "/entities/dataset_multi_view_tracking_and_image/entity_image/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_delete_entities(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    entities = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    assert len(entities) > 0
    deleted_ids = [entity.id for entity in entities]

    client = TestClient(app)
    delete_url = (
        "/entities/dataset_multi_view_tracking_and_image/entity_image/"
        f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"
    )
    response = client.delete(delete_url)

    assert response.status_code == 200

    # Check that the entities were deleted from the dataset
    assert len(dataset_multi_view_tracking_and_image.get_data("entity_image", deleted_ids)) == 0


def test_delete_entities_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    entities = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    deleted_ids = [entity.id for entity in entities]

    delete_ids_url = f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"

    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete(f"/entities/dataset_multi_view_tracking_and_image_wrong/entity_image/{delete_ids_url}")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.delete(f"/entities/dataset_multi_view_tracking_and_image/bbox_wrong/{delete_ids_url}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the entities group table."}


def test_delete_entity(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    entity = dataset_multi_view_tracking_and_image.get_data("entity_image", "entity_image_0")
    assert entity is not None

    client = TestClient(app)
    response = client.delete("/entities/dataset_multi_view_tracking_and_image/entity_image/entity_image_0")

    assert response.status_code == 200

    # Check that the entity was deleted from the dataset
    assert dataset_multi_view_tracking_and_image.get_data("entity_image", "entity_image_0") is None


def test_delete_entity_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete("/entities/dataset_multi_view_tracking_and_image_wrong/entity_image/entity_image_0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.delete("/entities/dataset_multi_view_tracking_and_image/bbox_wrong/entity_image_0")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table bbox_wrong is not in the entities group table."}
