# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pixano.app.models.embeddings import EmbeddingModel
from pixano.app.routers.utils import get_model_from_row, get_models_from_rows
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset


@pytest.mark.parametrize(
    "table, ids, items_ids, limit, skip",
    [
        ("image_embedding", ["image_embedding_0", "image_embedding_1"], None, None, 0),
        ("image_embedding", None, ["0", "1"], None, 0),
        ("image_embedding", None, None, 2, 0),
        ("image_embedding", None, None, 2, None),
        ("image_embedding", None, None, 10, 2),
        ("image_embedding", None, ["0", "1", "2"], 10, 1),
    ],
)
def test_get_embeddings(
    table: str,
    ids: list[str] | None,
    items_ids: list[str] | None,
    limit: int | None,
    skip: int | None,
    app_and_settings: tuple[FastAPI, Settings],
    dataset_multi_view_tracking_and_image: Dataset,
):
    app, settings = app_and_settings

    url = "/embeddings/dataset_multi_view_tracking_and_image/" + table + "/?"
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
        EmbeddingModel,
        dataset_multi_view_tracking_and_image.get_data(table, ids, limit, skip if skip is not None else 0, items_ids),
    )

    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 200
    for model_json in response.json():
        model = EmbeddingModel.model_validate(model_json)
        assert model in expected_output
    assert len(response.json()) == len(expected_output)


def test_get_embeddings_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings

    # Wrong dataset ID
    url = "/embeddings/dataset_multi_view_tracking_and_image_wrong/image_embedding/"
    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    url = "/embeddings/dataset_multi_view_tracking_and_image/image_embedding_wrong/"
    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "Table image_embedding_wrong is not in the embeddings group table."}

    # Wrong query parameters
    url = "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/?"
    for wrong_url_part in [
        "ids=image_embedding_0&item_ids=0",
    ]:
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert "Invalid query parameters. ids and item_ids cannot be set at the same time" in response.json()["detail"]
    for wrong_url_part in [
        "ids=image_embedding_0&limit=10",
    ]:
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert "Invalid query parameters. ids and limit cannot be set at the same time" in response.json()["detail"]

    # No embeddings found
    url = "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/?item_ids=100"
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/image_embedding."}


def test_get_embedding(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    app, settings = app_and_settings

    expected_output = get_model_from_row(
        "image_embedding",
        EmbeddingModel,
        dataset_multi_view_tracking_and_image.get_data("image_embedding", "image_embedding_0"),
    )

    client = TestClient(app)
    response = client.get("/embeddings/dataset_multi_view_tracking_and_image/image_embedding/image_embedding_0")
    assert response.status_code == 200
    model = EmbeddingModel.model_validate(response.json())

    assert model == expected_output


def test_get_embedding_error(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings

    # Wrong dataset ID
    client = TestClient(app)
    response = client.get("/embeddings/dataset_multi_view_tracking_and_image_wrong/image_embedding/image_embedding_0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.get("/embeddings/dataset_multi_view_tracking_and_image/image_embedding_wrong/image_embedding_0")
    assert response.status_code == 404
    assert response.json() == {"detail": "Table image_embedding_wrong is not in the embeddings group table."}

    # Wrong embedding ID
    response = client.get("/embeddings/dataset_multi_view_tracking_and_image/image_embedding/image_embedding_100")
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/image_embedding."}


def test_create_embeddings(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    embeddings = dataset_multi_view_tracking_and_image.get_data("image_embedding", limit=2)
    new_embeddings = [embedding.model_copy(deep=True) for embedding in embeddings]
    for new_embedding in new_embeddings:
        new_embedding.id = "new_" + new_embedding.id

    new_embeddings_models = get_models_from_rows("image_embedding", EmbeddingModel, new_embeddings)

    client = TestClient(app)
    response = client.post(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/",
        json=[model.model_dump() for model in new_embeddings_models],
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = EmbeddingModel.model_validate(model_json)
        assert model in new_embeddings_models
    assert len(response.json()) == len(new_embeddings_models)

    # Check that the embeddings were added to the dataset
    assert len(
        dataset_multi_view_tracking_and_image.get_data(
            "image_embedding", [new_embedding.id for new_embedding in new_embeddings]
        )
    ) == len(new_embeddings)


def test_create_embeddings_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    good_data = get_models_from_rows(
        "image_embedding", EmbeddingModel, dataset_multi_view_tracking_and_image.get_data("image_embedding", limit=2)
    )
    json_data = [model.model_dump() for model in good_data]

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/embeddings/dataset_multi_view_tracking_and_image_wrong/image_embedding/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.post(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table image_embedding_wrong is not in the embeddings group table."}

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = [model.model_dump() for model in bad_data]
    response = client.post(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_create_embedding(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    embedding = dataset_multi_view_tracking_and_image.get_data("image_embedding", "image_embedding_0")
    new_embedding = embedding.model_copy(deep=True)
    new_embedding.id = "new_" + new_embedding.id

    new_embedding_model = get_model_from_row("image_embedding", EmbeddingModel, new_embedding)

    client = TestClient(app)
    response = client.post(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/new_image_embedding_0",
        json=new_embedding_model.model_dump(),
    )

    assert response.status_code == 200
    model = EmbeddingModel.model_validate(response.json())
    assert model == new_embedding_model

    # Check that the embedding was added to the dataset
    assert dataset_multi_view_tracking_and_image.get_data("image_embedding", "new_image_embedding_0") is not None


def test_create_embedding_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_model_from_row(
        "image_embedding",
        EmbeddingModel,
        dataset_multi_view_tracking_and_image.get_data("image_embedding", "image_embedding_0"),
    )  # actually it is not good because id already exists but we look for errors so it is fine
    json_data = good_data.model_dump()

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/embeddings/dataset_multi_view_tracking_and_image_wrong/image_embedding/image_embedding_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.post(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding_wrong/image_embedding_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table image_embedding_wrong is not in the embeddings group table."}

    # Wrong embedding ID
    response = client.post(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_update_embeddings(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    embeddings = dataset_multi_view_tracking_and_image.get_data("image_embedding", limit=2)
    updated_embeddings = [embedding.model_copy(deep=True) for embedding in embeddings for i in range(2)]
    for i, updated_embedding in enumerate(updated_embeddings):
        if i % 2:
            updated_embedding.id = "new_" + updated_embedding.id
        updated_embedding.vector[0] = i + 1

    updated_embeddings_models = get_models_from_rows("image_embedding", EmbeddingModel, updated_embeddings)

    client = TestClient(app)
    response = client.put(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/",
        json=[model.model_dump() for model in updated_embeddings_models],
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = EmbeddingModel.model_validate(model_json)
        assert model in updated_embeddings_models
    assert len(response.json()) == len(updated_embeddings_models)

    # Check that the embeddings were updated in the dataset
    updated_rows = dataset_multi_view_tracking_and_image.get_data(
        "image_embedding", [updated_embedding.id for updated_embedding in updated_embeddings_models]
    )
    assert len(updated_rows) == len(updated_embeddings)
    for updated_row in updated_rows:
        cur_embedding = None
        for updated_embedding in updated_embeddings:
            if updated_embedding.id == updated_row.id:
                cur_embedding = updated_embedding
                break
        assert cur_embedding is not None
        assert cur_embedding.model_dump() == updated_row.model_dump()


def test_update_embeddings_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_models_from_rows(
        "image_embedding", EmbeddingModel, dataset_multi_view_tracking_and_image.get_data("image_embedding", limit=2)
    )
    json_data = [model.model_dump() for model in good_data]

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/embeddings/dataset_multi_view_tracking_and_image_wrong/image_embedding/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.put(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table image_embedding_wrong is not in the embeddings group table."}

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = [model.model_dump() for model in bad_data]
    response = client.put(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_update_embedding(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    embedding = dataset_multi_view_tracking_and_image.get_data("image_embedding", "image_embedding_0")
    updated_embedding = embedding.model_copy(deep=True)
    updated_embedding.vector[0] = 100

    updated_embedding_model = get_model_from_row("image_embedding", EmbeddingModel, updated_embedding)

    client = TestClient(app)
    response = client.put(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/image_embedding_0",
        json=updated_embedding_model.model_dump(),
    )

    assert response.status_code == 200
    model = EmbeddingModel.model_validate(response.json())
    assert model == updated_embedding_model

    # Check that the embedding was updated in the dataset
    updated_row = dataset_multi_view_tracking_and_image.get_data("image_embedding", updated_embedding.id)
    assert updated_row is not None
    assert updated_row.model_dump() == updated_embedding.model_dump()


def test_update_embedding_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = get_model_from_row(
        "image_embedding",
        EmbeddingModel,
        dataset_multi_view_tracking_and_image.get_data("image_embedding", "image_embedding_0"),
    )
    json_data = good_data.model_dump()

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/embeddings/dataset_multi_view_tracking_and_image_wrong/image_embedding/image_embedding_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.put(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding_wrong/image_embedding_0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table image_embedding_wrong is not in the embeddings group table."}

    # Wrong embedding ID
    response = client.put(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_delete_embeddings(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    embeddings = dataset_multi_view_tracking_and_image.get_data("image_embedding", limit=2)
    assert len(embeddings) > 0
    deleted_ids = [embedding.id for embedding in embeddings]

    client = TestClient(app)
    delete_url = (
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding/"
        f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"
    )
    response = client.delete(delete_url)

    assert response.status_code == 200

    # Check that the embeddings were deleted from the dataset
    assert len(dataset_multi_view_tracking_and_image.get_data("image_embedding", deleted_ids)) == 0


def test_delete_embeddings_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    embeddings = dataset_multi_view_tracking_and_image.get_data("image_embedding", limit=2)
    deleted_ids = [embedding.id for embedding in embeddings]

    delete_ids_url = f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"

    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete(
        f"/embeddings/dataset_multi_view_tracking_and_image_wrong/image_embedding/{delete_ids_url}"
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.delete(
        f"/embeddings/dataset_multi_view_tracking_and_image/image_embedding_wrong/{delete_ids_url}"
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table image_embedding_wrong is not in the embeddings group table."}


def test_delete_embedding(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    embedding = dataset_multi_view_tracking_and_image.get_data("image_embedding", "image_embedding_0")
    assert embedding is not None

    client = TestClient(app)
    response = client.delete("/embeddings/dataset_multi_view_tracking_and_image/image_embedding/image_embedding_0")

    assert response.status_code == 200

    # Check that the embedding was deleted from the dataset
    assert dataset_multi_view_tracking_and_image.get_data("image_embedding", "image_embedding_0") is None


def test_delete_embedding_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete("/embeddings/dataset_multi_view_tracking_and_image_wrong/bbox_image/image_embedding_0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong table name
    response = client.delete(
        "/embeddings/dataset_multi_view_tracking_and_image/image_embedding_wrong/image_embedding_0"
    )
    assert response.status_code == 404
    assert response.json() == {"detail": "Table image_embedding_wrong is not in the embeddings group table."}
