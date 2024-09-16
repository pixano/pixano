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
from pixano.app.models.item_info import ItemInfoModel
from pixano.app.models.items import ItemModel
from pixano.app.routers.utils import get_model_from_row, get_models_from_rows
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.features.schemas.schema_group import _SCHEMA_GROUP_TO_SCHEMA_DICT, SchemaGroup


def DatasetItem_to_ItemInfo(dataset_item: DatasetItemModel) -> ItemInfoModel:
    src_obj = dataset_item.model_dump()
    item = src_obj.pop("item", None)
    src_obj.pop("split", None)
    target_obj = dict(src_obj)
    target_obj.update(item)

    info_dict = {}
    for schema_group in _SCHEMA_GROUP_TO_SCHEMA_DICT.keys():
        if schema_group.value in [SchemaGroup.EMBEDDING.value, SchemaGroup.ITEM.value]:
            continue
        info_dict[schema_group.value] = {}
        target_obj.pop(schema_group.value, None)

    for schema_group in _SCHEMA_GROUP_TO_SCHEMA_DICT.keys():
        if schema_group.value in [SchemaGroup.EMBEDDING.value, SchemaGroup.ITEM.value]:
            continue
        for schema_name, objects in dataset_item.model_dump()[schema_group.value].items():
            objects = objects if isinstance(objects, list) else [objects]
            info_dict[schema_group.value][schema_name] = {"count": len(objects)}

    target_obj.update({"info": info_dict})
    return ItemInfoModel(**target_obj)


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
    app_and_settings: tuple[FastAPI, Settings],
    dataset_multi_view_tracking_and_image: Dataset,
):
    app, settings = app_and_settings

    url = "/items_info/dataset_multi_view_tracking_and_image/?"
    if ids is not None:
        url += "&".join(["ids=" + id for id in ids])
    if limit is not None:
        url += "limit=" + str(limit)
    if skip is not None:
        url += "&skip=" + str(skip)

    intermediate_output: list[DatasetItemModel] = DatasetItemModel.from_dataset_items(
        dataset_multi_view_tracking_and_image.get_dataset_items(ids, limit, skip if skip is not None else 0),
        dataset_multi_view_tracking_and_image.schema,
    )

    expected_output: list[ItemInfoModel] = []
    for datasetItem in intermediate_output:
        itemInfo = DatasetItem_to_ItemInfo(datasetItem)
        expected_output.append(itemInfo)

    client = TestClient(app)
    response = client.get(url)
    assert response.status_code == 200
    for model_json in response.json():
        model = ItemInfoModel.model_validate(model_json)

        assert model in expected_output
    assert len(response.json()) == len(expected_output)


def test_get_items_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    app, settings = app_and_settings

    # Wrong dataset ID
    url = "/items_info/dataset_multi_view_tracking_and_image_wrong/"
    client = TestClient(app)
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


def test_get_item_info(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    app, settings = app_and_settings

    intermediate_output = DatasetItemModel.from_dataset_items(
        dataset_multi_view_tracking_and_image.get_dataset_items(ids=["0"], limit=None, skip=0),
        dataset_multi_view_tracking_and_image.schema,
    )
    expected_output: list[ItemInfoModel] = []
    for datasetItem in intermediate_output:
        itemInfo = DatasetItem_to_ItemInfo(datasetItem)
        expected_output.append(itemInfo)

    client = TestClient(app)
    response = client.get("/items_info/dataset_multi_view_tracking_and_image/0")
    assert response.status_code == 200
    model = ItemInfoModel.model_validate(response.json())

    assert model == expected_output[0]


def test_get_item_info_error(app_and_settings: tuple[FastAPI, Settings]):
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
