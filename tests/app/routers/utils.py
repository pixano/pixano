# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from fastapi import FastAPI
from fastapi.encoders import jsonable_encoder
from fastapi.testclient import TestClient

from pixano.app.models.utils import _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT
from pixano.app.routers.utils import get_model_from_row, get_models_from_rows
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.features.schemas.schema_group import SchemaGroup


def base_url(group: SchemaGroup, dataset_id: str, table: str, id: str = "") -> str:
    if group not in [SchemaGroup.ITEM, SchemaGroup.SOURCE]:
        return f"/{group.value}/{dataset_id}/{table}/" + (f"{id}/" if id else "")
    else:
        return f"/{group.value}s/{dataset_id}/" + (f"{id}/" if id else "")


def _test_get_rows_handler(
    dataset: Dataset,
    group: SchemaGroup,
    table: str,
    ids: list[str] | None,
    item_ids: list[str] | None,
    limit: int | None,
    skip: int | None,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client

    url = base_url(group, dataset.info.id, table) + "?"

    if ids is not None:
        url += "&".join(["ids=" + id for id in ids])
    if item_ids is not None:
        url += "&".join(["item_ids=" + id for id in item_ids])
    if limit is not None:
        if url[-1] not in ["&", "?"]:
            url += "&"
        url += "limit=" + str(limit)
    if skip is not None:
        url += "&skip=" + str(skip)

    model_type = _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group]

    expected_output = get_models_from_rows(
        table,
        model_type,
        dataset.get_data(table, ids, limit, skip if skip is not None else 0, item_ids),
    )

    response = client.get(url)
    assert response.status_code == 200
    for model_json in response.json():
        model = model_type.model_validate(model_json)
        assert model in expected_output
    assert len(response.json()) == len(expected_output)


def _test_get_rows_handler_error(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    ids: list[str],
    item_ids: list[str],
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client

    # Wrong dataset ID
    url = base_url(group, "wrong_dataset", table)
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {settings.data_dir}."}

    # Wrong table name
    if group not in [SchemaGroup.ITEM, SchemaGroup.SOURCE]:
        url = base_url(group, dataset_id, "wrong_table")
        response = client.get(url)
        assert response.status_code == 404
        assert response.json() == {"detail": f"Table wrong_table is not in the {group.value} group table."}

    # Wrong query parameters
    url = base_url(group, dataset_id, table) + "?"
    if group not in [SchemaGroup.ITEM, SchemaGroup.SOURCE]:
        wrong_url_part = "&".join(["ids=" + id for id in ids]) + "&".join(["item_ids=" + id for id in item_ids])
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert "Invalid query parameters. ids and item_ids cannot be set at the same time" in response.json()["detail"]

    wrong_url_part = "&".join(["ids=" + id for id in ids]) + "&limit=10"
    response = client.get(url + wrong_url_part)
    assert response.status_code == 400
    assert "Invalid query parameters. ids and limit cannot be set at the same time" in response.json()["detail"]

    # No rows found
    url = base_url(group, dataset_id, table, "not_found")
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": f"No rows found for {dataset_id}/{table}."}


def _test_get_row_handler(
    dataset: Dataset,
    group: SchemaGroup,
    table: str,
    id: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client

    model_type = _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group]

    expected_output = get_model_from_row(table, model_type, dataset.get_data(table, id))

    response = client.get(base_url(group, dataset.info.id, table, id))
    assert response.status_code == 200
    model = model_type.model_validate(response.json())

    assert model == expected_output


def _test_get_row_handler_error(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    id: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client

    # Wrong dataset ID
    response = client.get(base_url(group, "wrong_dataset", table, id))
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {settings.data_dir}."}

    # Wrong table name
    if group not in [SchemaGroup.ITEM, SchemaGroup.SOURCE]:
        response = client.get(base_url(group, dataset_id, "wrong_table", id))
        assert response.status_code == 404
        assert response.json() == {"detail": f"Table wrong_table is not in the {group.value} group table."}

    # Wrong row ID
    response = client.get(base_url(group, dataset_id, table, "wrong_id"))
    assert response.status_code == 404
    assert response.json() == {"detail": f"No rows found for {dataset_id}/{table}."}


def _test_create_rows_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))

    model_type = _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group]

    rows = dataset.get_data(table, limit=2)
    new_rows = [row.model_copy(deep=True) for row in rows]
    for new_row in new_rows:
        new_row.id = "new_" + new_row.id

    new_rows_models = [
        model.model_dump(exclude_timestamps=True) for model in get_models_from_rows(table, model_type, new_rows)
    ]

    response = client.post(
        base_url(group, dataset_id, table),
        json=jsonable_encoder(new_rows_models),
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = model_type.model_validate(model_json).model_dump(exclude_timestamps=True)
        assert model in new_rows_models
    assert len(response.json()) == len(new_rows_models)

    # Check that the rows were added to the dataset
    assert len(dataset.get_data(table, [new_row.id for new_row in new_rows])) == len(new_rows)


def _test_create_rows_handler_error(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))

    model_type = _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group]

    good_data = get_models_from_rows(table, model_type, dataset.get_data(table, limit=2))
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    response = client.post(
        base_url(group, "wrong_dataset", table),
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {settings.data_dir}."}

    # Wrong table name
    if group not in [SchemaGroup.ITEM, SchemaGroup.SOURCE]:
        response = client.post(
            base_url(group, dataset_id, "wrong_table"),
            json=json_data,
        )
        assert response.status_code == 404
        assert response.json() == {"detail": f"Table wrong_table is not in the {group.value} group table."}

    # Wrong data
    bad_data = {"bad_data": "bad_data"}
    json_bad_data = jsonable_encoder(bad_data)
    response = client.post(
        base_url(group, dataset_id, table),
        json=json_bad_data,
    )
    assert response.status_code == 422


def _test_create_row_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    id: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))

    model_type = _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group]

    row = dataset.get_data(table, id)
    new_row = row.model_copy(deep=True)
    new_row.id = "new_" + new_row.id

    new_row_model = get_model_from_row(table, model_type, new_row)

    response = client.post(
        base_url(group, dataset_id, table, new_row.id),
        json=jsonable_encoder(new_row_model),
    )

    assert response.status_code == 200
    model = model_type.model_validate(response.json())
    assert model.model_dump(exclude_timestamps=True) == new_row_model.model_dump(exclude_timestamps=True)

    # Check that the row was added to the dataset
    assert dataset.get_data(table, new_row.id) is not None


def _test_create_row_handler_error(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    id: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))

    model_type = _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group]

    good_data = get_model_from_row(
        "bbox_image",
        model_type,
        dataset.get_data(table, id),
    )  # actually it is not good because id already exists but we look for errors so it is fine
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    response = client.post(
        base_url(group, "wrong_dataset", table, id),
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {settings.data_dir}."}

    # Wrong table name
    if group not in [SchemaGroup.ITEM, SchemaGroup.SOURCE]:
        response = client.post(
            base_url(group, dataset_id, "wrong_table", id),
            json=json_data,
        )
        assert response.status_code == 404
        assert response.json() == {"detail": f"Table wrong_table is not in the {group.value} group table."}

    # Wrong row ID
    response = client.post(
        base_url(group, dataset_id, table, "wrong_id"),
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def _test_update_rows_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    field_to_update: str,
    values: list,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))

    model_type = _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group]

    rows = dataset.get_data(table, limit=len(values))
    updated_rows = [row.model_copy(deep=True) for row in rows for i in range(2)]
    for i, updated_row in enumerate(updated_rows):
        if i % 2:
            updated_row.id = "new_" + updated_row.id
        setattr(updated_row, field_to_update, values[i % len(values)])

    updated_rows_models = get_models_from_rows(table, model_type, updated_rows)

    response = client.put(
        base_url(group, dataset_id, table),
        json=jsonable_encoder(updated_rows_models),
    )

    assert response.status_code == 200
    for model_json in response.json():
        model = model_type.model_validate(model_json)
        assert model.model_dump(exclude_timestamps=True) in [
            u_model.model_dump(exclude_timestamps=True) for u_model in updated_rows_models
        ]
    assert len(response.json()) == len(updated_rows_models)

    # Check that the rows were updated in the dataset
    dataset_updated_rows = dataset.get_data(table, [updated_row.id for updated_row in updated_rows_models])
    assert len(dataset_updated_rows) == len(updated_rows)
    for dataset_updated_row in dataset_updated_rows:
        cur_row = None
        for updated_row in updated_rows:
            if updated_row.id == dataset_updated_row.id:
                cur_row = updated_row
                break
        assert cur_row is not None
        if cur_row.id.startswith("new_"):
            assert cur_row.model_dump(exclude_timestamps=True) == dataset_updated_row.model_dump(
                exclude_timestamps=True
            )
        else:
            assert cur_row.model_dump(exclude="updated_at") == dataset_updated_row.model_dump(exclude="updated_at")


def _test_update_rows_handler_error(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))

    model_type = _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group]

    good_data = get_models_from_rows(table, model_type, dataset.get_data(table, limit=2))
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    response = client.put(
        base_url(group, "wrong_dataset", table),
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {settings.data_dir}."}

    # Wrong table name
    if group not in [SchemaGroup.ITEM, SchemaGroup.SOURCE]:
        response = client.put(
            base_url(group, dataset_id, "wrong_table"),
            json=json_data,
        )
        assert response.status_code == 404
        assert response.json() == {"detail": f"Table wrong_table is not in the {group.value} group table."}

    # Wrong data
    bad_data = {"bad_data": "bad_data"}
    json_bad_data = jsonable_encoder(bad_data)
    response = client.put(
        base_url(group, dataset_id, table),
        json=json_bad_data,
    )
    assert response.status_code == 422


def _test_update_row_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    id: str,
    field_to_update: str,
    value: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))

    model_type = _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group]

    row = dataset.get_data(table, id)
    updated_row = row.model_copy(deep=True)
    setattr(updated_row, field_to_update, value)

    updated_row_model = get_model_from_row(table, model_type, updated_row)

    response = client.put(
        base_url(group, dataset_id, table, id),
        json=jsonable_encoder(updated_row_model),
    )

    assert response.status_code == 200
    model = model_type.model_validate(response.json())
    assert model.model_dump(exclude="updated_at") == updated_row_model.model_dump(exclude="updated_at")

    # Check that the row was updated in the dataset
    dataset_updated_row = dataset.get_data(table, updated_row.id)
    assert dataset_updated_row is not None
    assert dataset_updated_row.model_dump(exclude="updated_at") == updated_row.model_dump(exclude="updated_at")


def _test_update_row_handler_error(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    id: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))

    model_type = _SCHEMA_GROUP_TO_SCHEMA_MODEL_DICT[group]

    good_data = get_model_from_row(
        table,
        model_type,
        dataset.get_data(table, id),
    )
    json_data = jsonable_encoder(good_data)

    # Wrong dataset ID
    response = client.put(
        base_url(group, "wrong_dataset", table, id),
        json=json_data,
    )
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {settings.data_dir}."}

    # Wrong table name
    if group not in [SchemaGroup.ITEM, SchemaGroup.SOURCE]:
        response = client.put(
            base_url(group, dataset_id, "wrong_table", id),
            json=json_data,
        )
        assert response.status_code == 404
        assert response.json() == {"detail": f"Table wrong_table is not in the {group.value} group table."}

    # Wrong row ID
    response = client.put(
        base_url(group, dataset_id, table, "wrong_id"),
        json=json_data,
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "ID in path and body do not match."}


def _test_delete_rows_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))
    rows = dataset.get_data(table, limit=2)
    assert len(rows) > 0
    deleted_ids = [row.id for row in rows]

    delete_url = base_url(group, dataset_id, table) + f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"
    response = client.delete(delete_url)

    assert response.status_code == 200

    # Check that the rows were deleted from the dataset
    assert len(dataset.get_data(table, deleted_ids)) == 0


def _test_delete_rows_handler_error(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))
    rows = dataset.get_data(table, limit=2)
    deleted_ids = [row.id for row in rows]

    delete_ids_url = f"?{'&'.join([f'ids={id}' for id in deleted_ids])}"

    # Wrong dataset ID
    response = client.delete(base_url(group, "wrong_dataset", table) + delete_ids_url)
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {settings.data_dir}."}

    # Wrong table name
    if group not in [SchemaGroup.ITEM, SchemaGroup.SOURCE]:
        response = client.delete(base_url(group, dataset_id, "wrong_table") + delete_ids_url)
        assert response.status_code == 404
        assert response.json() == {"detail": f"Table wrong_table is not in the {group.value} group table."}


def _test_delete_row_handler(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    id: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    dataset = Dataset.find(dataset_id, Path(settings.library_dir))
    row = dataset.get_data(table, id)
    assert row is not None

    response = client.delete(base_url(group, dataset_id, table, id))

    assert response.status_code == 200

    # Check that the row was deleted from the dataset
    assert dataset.get_data(table, id) is None


def _test_delete_row_handler_error(
    dataset_id: str,
    group: SchemaGroup,
    table: str,
    id: str,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client
    # Wrong dataset ID
    response = client.delete(base_url(group, "wrong_dataset", table, id))
    assert response.status_code == 404
    assert response.json() == {"detail": f"Dataset wrong_dataset not found in {settings.data_dir}."}

    # Wrong table name
    if group not in [SchemaGroup.ITEM, SchemaGroup.SOURCE]:
        response = client.delete(base_url(group, dataset_id, "wrong_table", id))
        assert response.status_code == 404
        assert response.json() == {"detail": f"Table wrong_table is not in the {group.value} group table."}
