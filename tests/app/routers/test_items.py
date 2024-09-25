# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from fastapi import FastAPI

from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.features.schemas.schema_group import SchemaGroup

from .utils import (
    _test_create_row_handler,
    _test_create_row_handler_error,
    _test_create_rows_handler,
    _test_create_rows_handler_error,
    _test_delete_row_handler,
    _test_delete_row_handler_error,
    _test_delete_rows_handler,
    _test_delete_rows_handler_error,
    _test_get_row_handler,
    _test_get_row_handler_error,
    _test_get_rows_handler,
    _test_get_rows_handler_error,
    _test_update_row_handler,
    _test_update_row_handler_error,
    _test_update_rows_handler,
    _test_update_rows_handler_error,
)


@pytest.mark.parametrize(
    "table, ids, item_ids, limit, skip",
    [
        ("item", ["0", "1"], None, None, 0),
        ("item", None, None, 2, 0),
        ("item", None, None, 2, None),
        ("item", None, None, 10, 2),
    ],
)
def test_get_items(
    table: str,
    ids: list[str] | None,
    item_ids: list[str] | None,
    limit: int | None,
    skip: int | None,
    app_and_settings: tuple[FastAPI, Settings],
    dataset_multi_view_tracking_and_image: Dataset,
):
    _test_get_rows_handler(
        dataset=dataset_multi_view_tracking_and_image,
        group=SchemaGroup.ITEM,
        table=table,
        ids=ids,
        item_ids=item_ids,
        limit=limit,
        skip=skip,
        app_and_settings=app_and_settings,
    )


def test_get_items_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    _test_get_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        ids=["0", "1"],
        item_ids=None,
        app_and_settings=app_and_settings,
    )


def test_get_item(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    _test_get_row_handler(
        dataset=dataset_multi_view_tracking_and_image,
        group=SchemaGroup.ITEM,
        table="item",
        id="0",
        app_and_settings=app_and_settings,
    )


def test_get_item_error(app_and_settings: tuple[FastAPI, Settings]):
    _test_get_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        id="0",
        app_and_settings=app_and_settings,
    )


def test_create_items(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_items_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_item(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        id="0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_item_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        id="0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_items(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        field_to_update="split",
        values=["new_split_0", "new_split_1"],
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_items_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_item(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        id="0",
        field_to_update="split",
        value="new_split",
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_item_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        id="0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_items(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_items_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_item(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        id="0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_item_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ITEM,
        table="item",
        id="0",
        app_and_settings=app_and_settings_with_copy,
    )
