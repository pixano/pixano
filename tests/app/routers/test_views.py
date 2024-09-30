# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

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
        ("image", ["image_0", "image_1"], None, None, 0),
        ("image", None, ["0", "1"], None, 0),
        ("image", None, None, 2, 0),
        ("image", None, None, 2, None),
        ("image", None, None, 10, 2),
        ("video", None, ["1"], 2, 1),
    ],
)
def test_get_views(
    table: str,
    ids: list[str] | None,
    item_ids: list[str] | None,
    limit: int | None,
    skip: int | None,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    dataset_multi_view_tracking_and_image: Dataset,
):
    _test_get_rows_handler(
        dataset=dataset_multi_view_tracking_and_image,
        group=SchemaGroup.VIEW,
        table=table,
        ids=ids,
        item_ids=item_ids,
        limit=limit,
        skip=skip,
        app_and_settings_with_client=app_and_settings_with_client,
    )


def test_get_views_error(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    _test_get_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        ids=["image_0", "image_1"],
        item_ids=["0", "1"],
        app_and_settings_with_client=app_and_settings_with_client,
    )


def test_get_view(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient], dataset_multi_view_tracking_and_image: Dataset
):
    _test_get_row_handler(
        dataset=dataset_multi_view_tracking_and_image,
        group=SchemaGroup.VIEW,
        table="image",
        id="image_0",
        app_and_settings_with_client=app_and_settings_with_client,
    )


def test_get_view_error(app_and_settings_with_client: tuple[FastAPI, Settings, TestClient]):
    _test_get_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        id="image_0",
        app_and_settings_with_client=app_and_settings_with_client,
    )


def test_create_views(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_create_views_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_create_view(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        id="image_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_create_view_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        id="image_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_update_views(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        field_to_update="width",
        values=[1000 + i for i in range(2)],
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_update_views_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_update_view(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        id="image_0",
        field_to_update="width",
        value=1000,
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_update_view_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        id="image_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_delete_views(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_delete_views_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_delete_view(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        id="image_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_delete_view_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.VIEW,
        table="image",
        id="image_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )
