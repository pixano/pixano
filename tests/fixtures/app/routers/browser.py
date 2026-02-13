# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from datetime import datetime

import polars as pl
import pytest

from pixano.app.models.datasets import DatasetBrowser, PaginationColumn, PaginationInfo, TableData


@pytest.fixture(scope="session")
def browser_dataset_image_bboxes_keypoint() -> DatasetBrowser:
    return DatasetBrowser(
        id="dataset_image_bboxes_keypoint",
        name="dataset_image_bboxes_keypoint",
        table_data=TableData(
            columns=[
                PaginationColumn(name="created_at", type="datetime"),
                PaginationColumn(name="updated_at", type="datetime"),
                PaginationColumn(name="image", type="image"),
                PaginationColumn(name="id", type="str"),
                PaginationColumn(name="split", type="str"),
                PaginationColumn(name="metadata", type="str"),
            ],
            rows=[
                {
                    "image": "",
                    "id": "0",
                    "split": "test",
                    "metadata": "metadata_0",
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                },
                {
                    "image": "",
                    "id": "1",
                    "split": "train",
                    "metadata": "metadata_1",
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                },
                {
                    "image": "",
                    "id": "2",
                    "split": "test",
                    "metadata": "metadata_2",
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                },
                {
                    "image": "",
                    "id": "3",
                    "split": "train",
                    "metadata": "metadata_3",
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                },
                {
                    "image": "",
                    "id": "4",
                    "split": "test",
                    "metadata": "metadata_4",
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                },
            ],
        ),
        pagination=PaginationInfo(current_page=0, page_size=50, total_size=5),
        semantic_search=[],
    )


@pytest.fixture(scope="session")
def browser_dataset_multi_view_tracking_and_image() -> DatasetBrowser:
    return DatasetBrowser(
        id="dataset_multi_view_tracking_and_image",
        name="dataset_multi_view_tracking_and_image",
        table_data=TableData(
            columns=[
                PaginationColumn(name="video", type="image"),
                PaginationColumn(name="image", type="image"),
                PaginationColumn(name="id", type="str"),
                PaginationColumn(name="split", type="str"),
                PaginationColumn(name="categories", type="list"),
                PaginationColumn(name="other_categories", type="list"),
                PaginationColumn(name="created_at", type="datetime"),
                PaginationColumn(name="updated_at", type="datetime"),
            ],
            rows=[
                {
                    "video": "",
                    "image": "",
                    "id": "0",
                    "split": "train",
                    "categories": ["person"],
                    "other_categories": [1],
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                },
                {
                    "video": "",
                    "image": "",
                    "id": "1",
                    "split": "train",
                    "categories": ["cat"],
                    "other_categories": [2],
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                },
                {
                    "video": "",
                    "image": "",
                    "id": "2",
                    "split": "train",
                    "categories": ["dog"],
                    "other_categories": [3],
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                },
                {
                    "video": "",
                    "id": "3",
                    "split": "test",
                    "categories": ["car"],
                    "other_categories": [4],
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                },
                {
                    "video": "",
                    "image": "",
                    "id": "4",
                    "split": "test",
                    "categories": ["person"],
                    "other_categories": [1],
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                },
            ],
        ),
        pagination=PaginationInfo(current_page=0, page_size=50, total_size=5),
        semantic_search=["image_embedding", "video_embeddings"],
    )


@pytest.fixture(scope="session")
def df_semantic_search():
    return pl.DataFrame({"item_ref.id": ["0", "1", "2", "3", "4"], "_distance": [0.5, 0.4, 0.1, 0.2, 0.3]})


@pytest.fixture(scope="session")
def browser_dataset_multi_view_tracking_and_image_semantic_search() -> DatasetBrowser:
    return DatasetBrowser(
        id="dataset_multi_view_tracking_and_image",
        name="dataset_multi_view_tracking_and_image",
        table_data=TableData(
            columns=[
                PaginationColumn(name="video", type="image"),
                PaginationColumn(name="image", type="image"),
                PaginationColumn(name="id", type="str"),
                PaginationColumn(name="split", type="str"),
                PaginationColumn(name="categories", type="list"),
                PaginationColumn(name="other_categories", type="list"),
                PaginationColumn(name="distance", type="float"),
                PaginationColumn(name="created_at", type="datetime"),
                PaginationColumn(name="updated_at", type="datetime"),
            ],
            rows=[
                {
                    "video": "",
                    "image": "",
                    "id": "2",
                    "split": "train",
                    "categories": ["dog"],
                    "other_categories": [3],
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                    "distance": 0.1,
                },
                {
                    "video": "",
                    "id": "3",
                    "split": "test",
                    "categories": ["car"],
                    "other_categories": [4],
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                    "distance": 0.2,
                },
                {
                    "video": "",
                    "image": "",
                    "id": "4",
                    "split": "test",
                    "categories": ["person"],
                    "other_categories": [1],
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                    "distance": 0.3,
                },
                {
                    "video": "",
                    "image": "",
                    "id": "1",
                    "split": "train",
                    "categories": ["cat"],
                    "other_categories": [2],
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                    "distance": 0.4,
                },
                {
                    "video": "",
                    "image": "",
                    "id": "0",
                    "split": "train",
                    "categories": ["person"],
                    "other_categories": [1],
                    "created_at": "2021-01-01T00:00:00",
                    "updated_at": "2021-01-01T00:00:00",
                    "distance": 0.5,
                },
            ],
        ),
        pagination=PaginationInfo(current_page=0, page_size=50, total_size=5),
        semantic_search=["image_embedding", "video_embeddings"],
    )
