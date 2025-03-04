# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.app.models import DatasetInfoModel
from pixano.datasets.workspaces import WorkspaceType


@pytest.fixture()
def info_model_dataset_image_bboxes_keypoint():
    return DatasetInfoModel(
        name="dataset_image_bboxes_keypoint",
        description="Description dataset_image_bboxes_keypoint.",
        workspace=WorkspaceType.IMAGE,
        num_items=5,
    )


@pytest.fixture()
def info_model_dataset_multi_view_tracking_and_image():
    return DatasetInfoModel(
        name="dataset_multi_view_tracking_and_image",
        description="Description dataset_multi_view_tracking_and_image.",
        workspace=WorkspaceType.VIDEO,
        num_items=5,
    )


@pytest.fixture()
def info_model_dataset_vqa():
    return DatasetInfoModel(
        name="dataset_vqa",
        description="Description dataset_vqa.",
        workspace=WorkspaceType.IMAGE_VQA,
        num_items=4,
    )
