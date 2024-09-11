# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pixano.app.models.datasets import DatasetBrowser, DatasetModel, PaginationColumn, PaginationInfo, TableData
from pixano.datasets.dataset import Dataset


class TestDatasetExplorer:
    def test_init(self):
        DatasetBrowser(
            id="voc",
            name="pascal",
            table_data=TableData(cols=[PaginationColumn(name="col", type="col")], rows=[{"metadata": 123}]),
            pagination=PaginationInfo(current=1, size=10, total=20),
            semantic_search=["search1", "search2"],
        )


class TestDatasetModel:
    def test_from_dataset(self, dataset_multi_view_tracking_and_image: Dataset):
        dataset_model = DatasetModel.from_dataset(dataset_multi_view_tracking_and_image)
        dataset_model.id = dataset_multi_view_tracking_and_image.info.id
        dataset_model.path = dataset_multi_view_tracking_and_image.path
        dataset_model.previews_path = dataset_multi_view_tracking_and_image.previews_path
        dataset_model.media_dir = dataset_multi_view_tracking_and_image.media_dir
        dataset_model.thumbnail = dataset_multi_view_tracking_and_image.thumbnail
        dataset_model.dataset_schema = dataset_multi_view_tracking_and_image.schema
        dataset_model.feature_values = dataset_multi_view_tracking_and_image.features_values
        dataset_model.info = dataset_multi_view_tracking_and_image.info

    def test_to_dataset(self, dataset_multi_view_tracking_and_image: Dataset):
        dataset_model = DatasetModel.from_dataset(dataset_multi_view_tracking_and_image)
        dataset = dataset_model.to_dataset()
        assert dataset.info == dataset_multi_view_tracking_and_image.info
        assert dataset.path == dataset_multi_view_tracking_and_image.path
        assert dataset.previews_path == dataset_multi_view_tracking_and_image.previews_path
        assert dataset.media_dir == dataset_multi_view_tracking_and_image.media_dir
        assert dataset.thumbnail == dataset_multi_view_tracking_and_image.thumbnail
        assert dataset.schema.model_dump() == dataset_multi_view_tracking_and_image.schema.model_dump()
        assert (
            dataset.features_values.model_dump() == dataset_multi_view_tracking_and_image.features_values.model_dump()
        )
