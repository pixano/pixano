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
        ("bbox_image", ["bbox_image_0", "bbox_image_1"], None, None, 0),
        ("bbox_image", None, ["0", "1"], None, 0),
        ("bbox_image", None, None, 2, 0),
        ("bbox_image", None, None, 2, None),
        ("bbox_image", None, None, 10, 2),
        ("bboxes_video", None, ["2"], 2, 1),
    ],
)
def test_get_annotations(
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
        group=SchemaGroup.ANNOTATION,
        table=table,
        ids=ids,
        item_ids=item_ids,
        limit=limit,
        skip=skip,
        app_and_settings=app_and_settings,
    )


def test_get_annotations_error(
    app_and_settings: tuple[FastAPI, Settings],
):
    _test_get_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        ids=["bbox_image_0", "bbox_image_1"],
        item_ids=["0", "1"],
        app_and_settings=app_and_settings,
    )


def test_get_annotation(app_and_settings: tuple[FastAPI, Settings], dataset_multi_view_tracking_and_image: Dataset):
    _test_get_row_handler(
        dataset=dataset_multi_view_tracking_and_image,
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        id="bbox_image_0",
        app_and_settings=app_and_settings,
    )


def test_get_annotation_error(app_and_settings: tuple[FastAPI, Settings]):
    _test_get_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        id="bbox_image_0",
        app_and_settings=app_and_settings,
    )


def test_create_annotations(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_annotations_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_annotation(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        id="bbox_image_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_create_annotation_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_create_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        id="bbox_image_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_annotations(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        field_to_update="coords",
        values=[[i, i, 100 + i, 100 + i] for i in range(2)],
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_annotations_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_annotation(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        id="bbox_image_0",
        field_to_update="coords",
        value=[1, 1, 100, 100],
        app_and_settings=app_and_settings_with_copy,
    )


def test_update_annotation_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_update_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        id="bbox_image_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_annotations(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_annotations_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_rows_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_annotation(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        id="bbox_image_0",
        app_and_settings=app_and_settings_with_copy,
    )


def test_delete_annotation_error(
    app_and_settings_with_copy: tuple[FastAPI, Settings],
):
    _test_delete_row_handler_error(
        dataset_id="dataset_multi_view_tracking_and_image",
        group=SchemaGroup.ANNOTATION,
        table="bbox_image",
        id="bbox_image_0",
        app_and_settings=app_and_settings_with_copy,
    )
