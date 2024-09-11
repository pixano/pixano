# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import pytest


@pytest.fixture()
def dataset_image_bboxes_keypoint(dataset_builder_image_bboxes_keypoint):
    return dataset_builder_image_bboxes_keypoint.build()


@pytest.fixture()
def dataset_multi_view_tracking_and_image(dataset_builder_multi_view_tracking_and_image):
    return dataset_builder_multi_view_tracking_and_image.build()
