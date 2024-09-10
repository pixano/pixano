# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest


@pytest.fixture(scope="session")
def json_browser_dataset_image_bboxes_keypoint():
    return {
        "id": "dataset_image_bboxes_keypoint",
        "name": "dataset_image_bboxes_keypoint",
        "table_data": {
            "cols": [
                {"name": "image", "type": "image"},
                {"name": "id", "type": "str"},
                {"name": "split", "type": "str"},
                {"name": "metadata", "type": "str"},
            ],
            "rows": [
                {"image": "", "id": "0", "split": "test", "metadata": "metadata_0"},
                {"image": "", "id": "1", "split": "train", "metadata": "metadata_1"},
                {"image": "", "id": "2", "split": "test", "metadata": "metadata_2"},
                {"image": "", "id": "3", "split": "train", "metadata": "metadata_3"},
                {"image": "", "id": "4", "split": "test", "metadata": "metadata_4"},
            ],
        },
        "pagination": {"current": 0, "size": 50, "total": 5},
        "sem_search": ["CLIP", "BLIP2"],
    }


@pytest.fixture(scope="session")
def json_browser_dataset_multi_view_tracking_and_image():
    return {
        "id": "dataset_multi_view_tracking_and_image",
        "name": "dataset_multi_view_tracking_and_image",
        "table_data": {
            "cols": [
                {"name": "image", "type": "image"},
                {"name": "video", "type": "image"},
                {"name": "id", "type": "str"},
                {"name": "split", "type": "str"},
                {"name": "categories", "type": "list"},
                {"name": "other_categories", "type": "list"},
            ],
            "rows": [
                {
                    "image": "",
                    "video": "",
                    "id": "0",
                    "split": "train",
                    "categories": ["person"],
                    "other_categories": [1],
                },
                {
                    "image": "",
                    "video": "",
                    "id": "1",
                    "split": "train",
                    "categories": ["cat"],
                    "other_categories": [2],
                },
                {
                    "image": "",
                    "video": "",
                    "id": "2",
                    "split": "train",
                    "categories": ["dog"],
                    "other_categories": [3],
                },
                {"video": "", "id": "3", "split": "test", "categories": ["car"], "other_categories": [4]},
                {
                    "image": "",
                    "video": "",
                    "id": "4",
                    "split": "test",
                    "categories": ["person"],
                    "other_categories": [1],
                },
            ],
        },
        "pagination": {"current": 0, "size": 50, "total": 5},
        "sem_search": ["CLIP", "BLIP2"],
    }
