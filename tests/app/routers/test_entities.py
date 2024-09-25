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
        ("entity_image", ["entity_image_0", "entity_image_1"], None, None, 0),
        ("entity_image", None, ["0", "1"], None, 0),
        ("entity_image", None, None, 2, 0),
        ("entity_image", None, None, 2, None),
        ("entity_image", None, None, 10, 2),
        ("entities_video", None, ["1"], 2, 1),
    ],
)
def test_get_entities(
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
        group=SchemaGroup.ENTITY,
        table=table,
        ids=ids,
        item_ids=item_ids,
        limit=limit,
        skip=skip,
        app_and_settings=app_and_settings,
    )


def test_get_entities_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    _test_get_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        ids=["entity_image_0", "entity_image_1"],
        item_ids=["0", "1"],
        app_and_settings=app_and_settings,
    )


def test_get_entity(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    _test_get_row_handler(
        dataset=dataset_multi_view_tracking_and_image,
        group=SchemaGroup.ENTITY,
        table="entity_image",
        id="entity_image_0",
        app_and_settings=app_and_settings,
    )


def test_get_entity_error(app_and_settings: tuple[FastAPI, Settings]):
    _test_get_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        id="entity_image_0",
        app_and_settings=app_and_settings,
    )


def test_create_entities(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_entities_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_entity(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        id="entity_image_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_entity_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        id="entity_image_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_entities(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        field_to_update="category",
        values=["cat", "dog"],
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_entities_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_entity(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        id="entity_image_0",
        field_to_update="category",
        value="squirrel",
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_entity_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        id="entity_image_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_entities(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_entities_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_entity(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        id="entity_image_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_entity_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ENTITY,
        table="entity_image",
        id="entity_image_0",
        app_and_settings=app_and_settings_with_copy,
    )
