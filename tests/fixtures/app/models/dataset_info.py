# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.app.models import DatasetInfoModel


@pytest.fixture()
def info_model_dataset_image_bboxes_keypoint():
    return DatasetInfoModel(
        name="dataset_image_bboxes_keypoint", description="Description dataset_image_bboxes_keypoint.", num_items=5
    )


@pytest.fixture()
def info_model_dataset_multi_view_tracking_and_image():
    return DatasetInfoModel(
        name="dataset_multi_view_tracking_and_image",
        description="Description dataset_multi_view_tracking_and_image.",
        num_items=5,
    )
