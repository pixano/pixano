# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.dataset_info import DatasetInfo


@pytest.fixture()
def info_dataset_image_bboxes_keypoint():
    return DatasetInfo(
        name="dataset_image_bboxes_keypoint",
        description="Description dataset_image_bboxes_keypoint.",
    )


@pytest.fixture()
def info_dataset_multi_view_tracking_and_image():
    return DatasetInfo(
        name="dataset_multi_view_tracking_and_image",
        description="Description dataset_multi_view_tracking_and_image.",
    )
