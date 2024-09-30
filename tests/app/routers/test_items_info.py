# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from pixano.app.models.item_info import ItemInfoModel
from pixano.app.models.items import ItemModel
from pixano.app.models.table_info import TableInfo
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.features.schemas.items.item import Item
from pixano.features.schemas.schema_group import SchemaGroup


@pytest.mark.parametrize(
    "ids, limit, skip",
    [
        (["0", "1"], None, 0),
        (None, 2, 0),
        (None, 2, None),
        (None, 10, 2),
    ],
)
def test_get_items_info(
    ids: list[str] | None,
    limit: int | None,
    skip: int | None,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    dataset_multi_view_tracking_and_image: Dataset,
):
    app, settings, client = app_and_settings_with_client

    url = "/items_info/dataset_multi_view_tracking_and_image/?"
    if ids is not None:
        url += "&".join(["ids=" + id for id in ids])
    if limit is not None:
        url += "limit=" + str(limit)
    if skip is not None:
        url += "&skip=" + str(skip)

    dataset_items = dataset_multi_view_tracking_and_image.get_dataset_items(
        ids, limit, skip if skip is not None else 0
    )
    schemas_data = [
        dataset_item.to_schemas_data(dataset_multi_view_tracking_and_image.schema) for dataset_item in dataset_items
    ]
    expected_output = []
    for schema_data in schemas_data:
        item_data = schema_data.pop("item", None)
        item_model = ItemModel.from_row(
            item_data, TableInfo(name="item", group=SchemaGroup.ITEM.value, base_schema=Item.__name__)
        )
        info_dict = {
            group.value: {
                table: {
                    "count": (len(schema_data[table]) if isinstance(schema_data[table], list) else 1)
                    if table in schema_data and schema_data[table] is not None
                    else 0
                }
                for table in tables
            }
            for group, tables in dataset_multi_view_tracking_and_image.schema.groups.items()
            if group not in [SchemaGroup.ITEM, SchemaGroup.EMBEDDING]
        }
        expected_output.append(ItemInfoModel(info=info_dict, **item_model.model_dump()))

    response = client.get(url)
    assert response.status_code == 200
    for model_json in response.json():
        model = ItemInfoModel.model_validate(model_json)
        assert model in expected_output

    assert len(response.json()) == len(expected_output)


def test_get_items_error(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client

    # Wrong dataset ID
    url = "/items_info/dataset_multi_view_tracking_and_image_wrong/"
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong query parameters
    url = "/items_info/dataset_multi_view_tracking_and_image/?"
    for wrong_url_part in [
        "ids=0&limit=10",
    ]:
        response = client.get(url + wrong_url_part)
        assert response.status_code == 400
        assert "Invalid query parameters. ids and limit cannot be set at the same time" in response.json()["detail"]

    # No items found
    url = "/items_info/dataset_multi_view_tracking_and_image/?ids=100"
    response = client.get(url)
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/item."}


def test_get_item_info(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient], dataset_multi_view_tracking_and_image: Dataset
):
    app, settings, client = app_and_settings_with_client

    dataset_item = dataset_multi_view_tracking_and_image.get_dataset_items("0", None, 0)
    assert dataset_item is not None

    schemas_data = dataset_item.to_schemas_data(dataset_multi_view_tracking_and_image.schema)
    item_data = schemas_data.pop("item", None)
    item_model = ItemModel.from_row(
        item_data, TableInfo(name="item", group=SchemaGroup.ITEM.value, base_schema=Item.__name__)
    )
    info_dict = {
        group.value: {
            table: {
                "count": (len(schemas_data[table]) if isinstance(schemas_data[table], list) else 1)
                if table in schemas_data and schemas_data[table] is not None
                else 0
            }
            for table in tables
        }
        for group, tables in dataset_multi_view_tracking_and_image.schema.groups.items()
        if group not in [SchemaGroup.ITEM, SchemaGroup.EMBEDDING]
    }
    expected_output = ItemInfoModel(info=info_dict, **item_model.model_dump())

    response = client.get("/items_info/dataset_multi_view_tracking_and_image/0")
    assert response.status_code == 200
    model = ItemInfoModel.model_validate(response.json())

    assert model == expected_output


def test_get_item_info_error(app_and_settings_with_client: tuple[FastAPI, Settings, TestClient]):
    app, settings, client = app_and_settings_with_client

    # Wrong dataset ID
    response = client.get("/items/dataset_multi_view_tracking_and_image_wrong/0")
    assert response.status_code == 404
    assert response.json() == {
        "detail": f"Dataset dataset_multi_view_tracking_and_image_wrong not found in {settings.data_dir}."
    }

    # Wrong item ID
    response = client.get("/items/dataset_multi_view_tracking_and_image/100")
    assert response.status_code == 404
    assert response.json() == {"detail": "No rows found for dataset_multi_view_tracking_and_image/item."}
