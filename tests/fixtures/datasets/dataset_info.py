# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType


@pytest.fixture()
def info_dataset_image_bboxes_keypoint():
    return DatasetInfo(
        name="dataset_image_bboxes_keypoint",
        description="Description dataset_image_bboxes_keypoint.",
        workspace=WorkspaceType.IMAGE,
    )


@pytest.fixture()
def info_dataset_vqa():
    return DatasetInfo(
        name="dataset_vqa",
        description="Description dataset_vqa.",
        workspace=WorkspaceType.IMAGE_VQA,
    )


@pytest.fixture()
def info_dataset_multi_view_tracking_and_image():
    return DatasetInfo(
        name="dataset_multi_view_tracking_and_image",
        description="Description dataset_multi_view_tracking_and_image.",
        workspace=WorkspaceType.VIDEO,
    )


@pytest.fixture()
def info_dataset_mel():
    return DatasetInfo(
        name="dataset_mel",
        description="Description dataset_mel.",
        workspace=WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
    )
