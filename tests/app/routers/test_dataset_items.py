# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pixano.app.models.dataset_items import DatasetItemModel
from pixano.app.routers.utils import get_model_from_row, get_models_from_rows
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_schema import DatasetItem
from pixano.features.schemas.schema_group import SchemaGroup


def _create_new_dataset_item_dataset_multi_view_tracking_and_image(dataset_item: DatasetItem) -> DatasetItem:
    new_dataset_item = dataset_item.model_copy(deep=True)
    new_dataset_item.id = "new_" + new_dataset_item.id
    for new_video in new_dataset_item.video:
        new_video.id = "new_" + new_video.id
        new_video.item_ref.id = new_dataset_item.id
    if new_dataset_item.image is not None:
        new_dataset_item.image.id = "new_" + new_dataset_item.image.id
        new_dataset_item.image.item_ref.id = new_dataset_item.id
    if new_dataset_item.entity_image is not None:
        new_dataset_item.entity_image.id = "new_" + new_dataset_item.entity_image.id
        new_dataset_item.entity_image.item_ref.id = new_dataset_item.id
    for new_entity_video in new_dataset_item.entities_video:
        new_entity_video.id = "new_" + new_entity_video.id
        new_entity_video.item_ref.id = new_dataset_item.id
    for new_track in new_dataset_item.tracks:
        new_track.id = "new_" + new_track.id
        new_track.item_ref.id = new_dataset_item.id
    if new_dataset_item.bbox_image is not None:
        new_dataset_item.bbox_image.id = "new_" + new_dataset_item.bbox_image.id
        new_dataset_item.bbox_image.item_ref.id = new_dataset_item.id
    if new_dataset_item.mask_image is not None:
        new_dataset_item.mask_image.id = "new_" + new_dataset_item.mask_image.id
        new_dataset_item.mask_image.item_ref.id = new_dataset_item.id
    for new_keypoint_image in new_dataset_item.keypoints_image:
        new_keypoint_image.id = "new_" + new_keypoint_image.id
        new_keypoint_image.item_ref.id = new_dataset_item.id
    for new_bbox_video in new_dataset_item.bboxes_video:
        new_bbox_video.id = "new_" + new_bbox_video.id
        new_bbox_video.item_ref.id = new_dataset_item.id
    for new_keypoint_video in new_dataset_item.keypoints_video:
        new_keypoint_video.id = "new_" + new_keypoint_video.id
        new_keypoint_video.item_ref.id = new_dataset_item.id
    for new_tracklet in new_dataset_item.tracklets:
        new_tracklet.id = "new_" + new_tracklet.id
        new_tracklet.item_ref.id = new_dataset_item.id
    return new_dataset_item


@pytest.mark.parametrize(
    "ids, limit, skip",
    [
        (["0", "1"], None, None),
        (None, 2, 0),
        (None, 2, None),
        (None, 10, 2),
    ],
)
def test_get_dataset_items(
    ids: list[str] | None,
    limit: int | None,
    skip: int | None,
    app_and_settings: tuple[FastAPI, Settings],
    dataset_multi_view_tracking_and_image: Dataset,
):
    app, settings = app_and_settings

    url = "/dataset_items/dataset_multi_view_tracking_and_image/?"
    if ids is not None:
        url += "&".join(["ids=" + id for id in ids])
    if limit is not None:
        url += "limit=" + str(limit)
    if skip is not None:
        url += "&skip=" + str(skip)

    expected_output = {
        model.id: model.model_dump()
        for model in DatasetItemModel.from_dataset_items(
            dataset_multi_view_tracking_and_image.get_dataset_items(ids, limit, skip if skip is not None else 0),
            dataset_multi_view_tracking_and_image.schema,
        )
    }

    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 200
    assert len(response.json()) == len(expected_output)
    for model_json in response.json():
        model = DatasetItemModel.model_validate(model_json)
        assert model.model_dump() == expected_output[model.id]


def test_get_dataset_items_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings

    # Wrong dataset ID
    url = "/dataset_items/dataset_multi_view_tracking_and_image_wrong/"
    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong query parameters
    url = "/dataset_items/dataset_multi_view_tracking_and_image/?"
    for wrong_url_part in [
        "ids=0&limit=10",
    ]:
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert "Invalid query parameters. ids and limit cannot be set at the same time" in response.json()["detail"]

    # No dataset_items found
    url = "/dataset_items/dataset_multi_view_tracking_and_image/?ids=100"
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "Dataset items not found."}


def test_get_dataset_item(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    app, settings = app_and_settings

    expected_output = DatasetItemModel.from_dataset_item(
        dataset_multi_view_tracking_and_image.get_dataset_items("0"),
        dataset_multi_view_tracking_and_image.schema,
    ).model_dump()

    client = TestClient(app)
    response = client.get("/dataset_items/dataset_multi_view_tracking_and_image/0")
    assert response.status_code == 200
    model = DatasetItemModel.model_validate(response.json()).model_dump()

    assert model == expected_output


def test_get_dataset_item_error(app_and_settings: tuple[FastAPI, Settings]):
    app, settings = app_and_settings

    # Wrong dataset ID
    client = TestClient(app)
    response = client.get("/dataset_items/dataset_multi_view_tracking_and_image_wrong/0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong dataset_item ID
    response = client.get("/dataset_items/dataset_multi_view_tracking_and_image/100")
    assert response.status_code == 404
    assert response.json() == {"detail": "Dataset items not found."}


def test_create_dataset_items(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    dataset_items = dataset_multi_view_tracking_and_image.get_dataset_items(limit=2)
    new_dataset_items = [
        _create_new_dataset_item_dataset_multi_view_tracking_and_image(dataset_item) for dataset_item in dataset_items
    ]

    new_dataset_items_models = {
        model.id: model.model_dump()
        for model in DatasetItemModel.from_dataset_items(
            new_dataset_items, dataset_multi_view_tracking_and_image.schema
        )
    }
    client = TestClient(app)
    response = client.post(
        "/dataset_items/dataset_multi_view_tracking_and_image/",
        json=list(new_dataset_items_models.values()),
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = DatasetItemModel.model_validate(model_json)
        assert model.model_dump() == new_dataset_items_models[model.id]
    assert len(response.json()) == len(new_dataset_items_models)

    # Check that the dataset_items were added to the dataset
    assert len(dataset_multi_view_tracking_and_image.get_dataset_items(list(new_dataset_items_models.keys()))) == len(
        new_dataset_items_models
    )


def test_create_dataset_items_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    good_data = DatasetItemModel.from_dataset_items(
        dataset_multi_view_tracking_and_image.get_dataset_items(limit=2), dataset_multi_view_tracking_and_image.schema
    )
    json_data = [model.model_dump() for model in good_data]

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/dataset_items/dataset_multi_view_tracking_and_image_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = [model.model_dump() for model in bad_data]
    response = client.post(
        "/dataset_items/dataset_multi_view_tracking_and_image/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_create_dataset_item(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    dataset_item = dataset_multi_view_tracking_and_image.get_dataset_items("0")
    new_dataset_item = _create_new_dataset_item_dataset_multi_view_tracking_and_image(dataset_item)

    new_dataset_item_model = DatasetItemModel.from_dataset_item(
        new_dataset_item, dataset_multi_view_tracking_and_image.schema
    )

    client = TestClient(app)
    response = client.post(
        "/dataset_items/dataset_multi_view_tracking_and_image/new_0",
        json=new_dataset_item_model.model_dump(),
    )

    assert response.status_code == 200
    model = DatasetItemModel.model_validate(response.json())
    assert model == new_dataset_item_model

    # Check that the dataset_item was added to the dataset
    assert dataset_multi_view_tracking_and_image.get_dataset_items("new_0") is not None


def test_create_dataset_item_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = DatasetItemModel.from_dataset_item(
        dataset_multi_view_tracking_and_image.get_dataset_items("0"), dataset_multi_view_tracking_and_image.schema
    )  # actually it is not good because id already exists but we look for errors so it is fine
    json_data = good_data.model_dump()

    # Wrong dataset ID
    client = TestClient(app)
    response = client.post(
        "/dataset_items/dataset_multi_view_tracking_and_image_wrong/0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong dataset_item ID
    response = client.post(
        "/dataset_items/dataset_multi_view_tracking_and_image/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_update_dataset_items(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    dataset_items = dataset_multi_view_tracking_and_image.get_dataset_items(limit=2)
    updated_dataset_items = [
        _create_new_dataset_item_dataset_multi_view_tracking_and_image(dataset_item=dataset_item)
        if i % 2
        else dataset_item
        for dataset_item in dataset_items
        for i in range(2)
    ]
    for i, updated_dataset_item in enumerate(updated_dataset_items):
        if i % 2:
            updated_dataset_item.other_categories.append(i)
        updated_dataset_item.image.width = 1000 + i
        updated_dataset_item.entity_image.category = "new_category" + str(i)
        updated_dataset_item.bbox_image.coords[0] += i

    updated_dataset_items_models = DatasetItemModel.from_dataset_items(
        updated_dataset_items, dataset_multi_view_tracking_and_image.schema
    )

    client = TestClient(app)
    response = client.put(
        "/dataset_items/dataset_multi_view_tracking_and_image/",
        json=[model.model_dump() for model in updated_dataset_items_models],
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = DatasetItemModel.model_validate(model_json)
        assert model in updated_dataset_items_models
    assert len(response.json()) == len(updated_dataset_items_models)

    # Check that the dataset_items were updated in the dataset
    updated_rows = dataset_multi_view_tracking_and_image.get_dataset_items(
        [updated_dataset_item.id for updated_dataset_item in updated_dataset_items_models]
    )
    assert len(updated_rows) == len(updated_dataset_items)
    for updated_row in updated_rows:
        cur_dataset_item = None
        for updated_dataset_item in updated_dataset_items:
            if updated_dataset_item.id == updated_row.id:
                cur_dataset_item = updated_dataset_item
                break
        assert cur_dataset_item is not None
        assert cur_dataset_item.model_dump() == updated_row.model_dump()


def test_update_dataset_items_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = DatasetItemModel.from_dataset_items(
        dataset_multi_view_tracking_and_image.get_dataset_items(limit=2), dataset_multi_view_tracking_and_image.schema
    )
    json_data = [model.model_dump() for model in good_data]

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/dataset_items/dataset_multi_view_tracking_and_image_wrong/",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong data
    bad_data = dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
    json_bad_data = [model.model_dump() for model in bad_data]
    response = client.put(
        "/dataset_items/dataset_multi_view_tracking_and_image/",
        json=json_bad_data,
    )
    assert response.status_code == 422


def test_update_dataset_item(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )

    dataset_item = dataset_multi_view_tracking_and_image.get_dataset_items("0")
    dataset_item.other_categories = [1, 2, 3, 4, 5]

    updated_dataset_item_model = DatasetItemModel.from_dataset_item(
        dataset_item, dataset_multi_view_tracking_and_image.schema
    )

    client = TestClient(app)
    response = client.put(
        "/dataset_items/dataset_multi_view_tracking_and_image/0",
        json=updated_dataset_item_model.model_dump(),
    )

    assert response.status_code == 200
    model = DatasetItemModel.model_validate(response.json())
    assert model == updated_dataset_item_model

    # Check that the dataset_item was updated in the dataset
    updated_row = dataset_multi_view_tracking_and_image.get_dataset_items("0")
    assert updated_row is not None
    assert updated_row.model_dump() == dataset_item.model_dump()


def test_update_dataset_item_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    good_data = DatasetItemModel.from_dataset_item(
        dataset_multi_view_tracking_and_image.get_dataset_items("0"), dataset_multi_view_tracking_and_image.schema
    )
    json_data = good_data.model_dump()

    # Wrong dataset ID
    client = TestClient(app)
    response = client.put(
        "/dataset_items/dataset_multi_view_tracking_and_image_wrong/0",
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong dataset_item ID
    response = client.put(
        "/dataset_items/dataset_multi_view_tracking_and_image/wrong_id",
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def test_delete_dataset_items(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    dataset_items = dataset_multi_view_tracking_and_image.get_dataset_items(limit=2)
    assert len(dataset_items) > 0
    deleted_ids = [dataset_item.id for dataset_item in dataset_items]

    client = TestClient(app)
    delete_url = (
        "/dataset_items/dataset_multi_view_tracking_and_image/" f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"
    )
    response = client.delete(delete_url)

    assert response.status_code == 200

    # Check that the dataset_items were deleted from the dataset
    sql_item_ids = f"('{deleted_ids[0]}')" if len(deleted_ids) == 1 else str(tuple(set(deleted_ids)))
    for table_name, table in dataset_multi_view_tracking_and_image.open_tables(exclude_embeddings=True).items():
        if table_name == SchemaGroup.ITEM.value:
            assert dataset_multi_view_tracking_and_image._search_by_ids(sql_item_ids, table).to_list() == []
        else:
            assert (
                dataset_multi_view_tracking_and_image._search_by_field(table, "item_ref.id", sql_item_ids).to_list()
                == []
            )


def test_delete_dataset_items_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    dataset_items = dataset_multi_view_tracking_and_image.get_dataset_items(limit=2)
    deleted_ids = [dataset_item.id for dataset_item in dataset_items]

    delete_ids_url = f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"

    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete(f"/dataset_items/dataset_multi_view_tracking_and_image_wrong/{delete_ids_url}")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }


def test_delete_dataset_item(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy
    dataset_multi_view_tracking_and_image = Dataset.find(
        "dataset_multi_view_tracking_and_image", Path(settings.library_dir)
    )
    dataset_item = dataset_multi_view_tracking_and_image.get_dataset_items("0")

    client = TestClient(app)
    response = client.delete("/dataset_items/dataset_multi_view_tracking_and_image/0")

    assert response.status_code == 200

    # Check that the dataset_item was deleted from the dataset
    sql_item_ids = f"('{dataset_item.id}')"
    for table_name, table in dataset_multi_view_tracking_and_image.open_tables(exclude_embeddings=True).items():
        if table_name == SchemaGroup.ITEM.value:
            assert dataset_multi_view_tracking_and_image._search_by_ids(sql_item_ids, table).to_list() == []
        else:
            assert (
                dataset_multi_view_tracking_and_image._search_by_field(table, "item_ref.id", sql_item_ids).to_list()
                == []
            )


def test_delete_dataset_item_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings_with_copy

    # Wrong dataset ID
    client = TestClient(app)
    response = client.delete("/dataset_items/dataset_multi_view_tracking_and_image_wrong/0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }
