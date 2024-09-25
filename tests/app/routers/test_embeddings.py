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
        ("image_embedding", ["image_embedding_0", "image_embedding_1"], None, None, 0),
        ("image_embedding", None, ["0", "1"], None, 0),
        ("image_embedding", None, None, 2, 0),
        ("image_embedding", None, None, 2, None),
        ("image_embedding", None, None, 10, 2),
        ("video_embeddings", None, ["1"], 2, 1),
    ],
)
def test_get_embeddings(
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
        group=SchemaGroup.EMBEDDING,
        table=table,
        ids=ids,
        item_ids=item_ids,
        limit=limit,
        skip=skip,
        app_and_settings=app_and_settings,
    )


def test_get_embeddings_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    _test_get_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        ids=["image_embedding_0", "image_embedding_1"],
        item_ids=["0", "1"],
        app_and_settings=app_and_settings,
    )


def test_get_embedding(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    _test_get_row_handler(
        dataset=dataset_multi_view_tracking_and_image,
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        id="image_embedding_0",
        app_and_settings=app_and_settings,
    )


def test_get_embedding_error(app_and_settings: tuple[FastAPI, Settings]):
    _test_get_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        id="image_embedding_0",
        app_and_settings=app_and_settings,
    )


def test_create_embeddings(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_embeddings_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_embedding(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        id="image_embedding_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_embedding_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        id="image_embedding_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_embeddings(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        field_to_update="vector",
        values=[[10 + i + j for j in range(8)] for i in range(2)],
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_embeddings_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_embedding(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        id="image_embedding_0",
        field_to_update="vector",
        value=[10 + i for i in range(8)],
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_embedding_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        id="image_embedding_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_embeddings(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_embeddings_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_embedding(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        id="image_embedding_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_embedding_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.EMBEDDING,
        table="image_embedding",
        id="image_embedding_0",
        app_and_settings=app_and_settings_with_copy,
    )
