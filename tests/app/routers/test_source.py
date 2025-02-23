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
    "table, where, ids, item_ids, limit, skip",
    [
        ("source", None, ["source_0", "source_1"], None, None, 0),
        ("source", None, None, None, 2, 0),
        ("source", "id = 'source_0'", None, None, 2, 0),
        ("source", None, None, None, 2, None),
        ("source", None, None, None, 10, 2),
    ],
)
def test_get_sources(
    table: str,
    ids: list[str] | None,
    item_ids: list[str] | None,
    where: str | None,
    limit: int | None,
    skip: int | None,
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
    dataset_multi_view_tracking_and_image: Dataset,
):
    _test_get_rows_handler(
        dataset=dataset_multi_view_tracking_and_image,
        group=SchemaGroup.SOURCE,
        table=table,
        ids=ids,
        where=where,
        item_ids=item_ids,
        limit=limit,
        skip=skip,
        app_and_settings_with_client=app_and_settings_with_client,
    )


def test_get_sources_error(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient],
):
    _test_get_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        ids=["source_0", "source_1"],
        item_ids=None,
        app_and_settings_with_client=app_and_settings_with_client,
    )


def test_get_source(
    app_and_settings_with_client: tuple[FastAPI, Settings, TestClient], dataset_multi_view_tracking_and_image: Dataset
):
    _test_get_row_handler(
        dataset=dataset_multi_view_tracking_and_image,
        group=SchemaGroup.SOURCE,
        table="source",
        id="source_0",
        app_and_settings_with_client=app_and_settings_with_client,
    )


def test_get_source_error(app_and_settings_with_client: tuple[FastAPI, Settings, TestClient]):
    _test_get_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        id="source_0",
        app_and_settings_with_client=app_and_settings_with_client,
    )


def test_create_sources(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_create_sources_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_create_source(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        id="source_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_create_source_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        id="source_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_update_sources(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        field_to_update="name",
        values=["name_source_0", "name_source_1"],
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_update_sources_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_update_source(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        id="source_0",
        field_to_update="name",
        value="name_source_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_update_source_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        id="source_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_delete_sources(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_delete_sources_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_delete_source(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        id="source_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )


def test_delete_source_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.SOURCE,
        table="source",
        id="source_0",
        app_and_settings_with_client=app_and_settings_with_client_copy,
    )
