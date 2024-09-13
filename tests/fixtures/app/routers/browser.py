# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.app.models.datasets import DatasetBrowser, PaginationColumn, PaginationInfo, TableData


@pytest.fixture(scope="session")
def browser_dataset_image_bboxes_keypoint() -> DatasetBrowser:
    return DatasetBrowser(
        id="dataset_image_bboxes_keypoint",
        name="dataset_image_bboxes_keypoint",
        table_data=TableData(
            columns=[
                PaginationColumn(name="image", type="image"),
                PaginationColumn(name="id", type="str"),
                PaginationColumn(name="split", type="str"),
                PaginationColumn(name="metadata", type="str"),
            ],
            rows=[
                {"image": "", "id": "0", "split": "test", "metadata": "metadata_0"},
                {"image": "", "id": "1", "split": "train", "metadata": "metadata_1"},
                {"image": "", "id": "2", "split": "test", "metadata": "metadata_2"},
                {"image": "", "id": "3", "split": "train", "metadata": "metadata_3"},
                {"image": "", "id": "4", "split": "test", "metadata": "metadata_4"},
            ],
        ),
        pagination=PaginationInfo(current_page=0, page_size=50, total_size=5),
        semantic_search=["CLIP", "BLIP2"],
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
            ],
            rows=[
                {
                    "video": "",
                    "image": "",
                    "id": "0",
                    "split": "train",
                    "categories": ["person"],
                    "other_categories": [1],
                },
                {
                    "video": "",
                    "image": "",
                    "id": "1",
                    "split": "train",
                    "categories": ["cat"],
                    "other_categories": [2],
                },
                {
                    "video": "",
                    "image": "",
                    "id": "2",
                    "split": "train",
                    "categories": ["dog"],
                    "other_categories": [3],
                },
                {"video": "", "id": "3", "split": "test", "categories": ["car"], "other_categories": [4]},
                {
                    "video": "",
                    "image": "",
                    "id": "4",
                    "split": "test",
                    "categories": ["person"],
                    "other_categories": [1],
                },
            ],
        ),
        pagination=PaginationInfo(current_page=0, page_size=50, total_size=5),
        semantic_search=["CLIP", "BLIP2"],
    )
