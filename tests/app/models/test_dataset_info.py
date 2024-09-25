# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.app.models import DatasetInfoModel
from tests.assets.sample_data.metadata import ASSETS_DIRECTORY


LIBRARY_PATH = ASSETS_DIRECTORY / "library"


class TestDatasetInfoModel:
    def test_from_dataset(
        self,
        dataset_image_bboxes_keypoint,
        info_dataset_image_bboxes_keypoint,
        info_model_dataset_image_bboxes_keypoint,
    ):
        info = DatasetInfoModel.from_dataset_info(
            info_dataset_image_bboxes_keypoint, LIBRARY_PATH / "dataset_image_bboxes_keypoint"
        )
        assert info == info_model_dataset_image_bboxes_keypoint
