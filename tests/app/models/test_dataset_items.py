# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from pixano.app.models import (
    AnnotationModel,
    DatasetItemModel,
    EntityModel,
    ItemModel,
    TableInfo,
    ViewModel,
)
from pixano.datasets import DatasetItem, DatasetSchema
from pixano.features.schemas.registry import _PIXANO_SCHEMA_REGISTRY
from pixano.utils.python import get_super_type_from_dict
from tests.fixtures.datasets.builders.builder import generate_data_multi_view_tracking_and_image


class TestDatasetItemModel:
    def test_from_dataset_items(
        self,
        dataset_schema_multi_view_tracking_and_image: DatasetSchema,
    ):
        dataset_items = []
        items_data = []
        for data in generate_data_multi_view_tracking_and_image(
            num_rows=5, schemas=dataset_schema_multi_view_tracking_and_image.schemas
        ):
            dataset_item_multi_view_tracking_and_image = DatasetItem.from_dataset_schema(
                dataset_schema_multi_view_tracking_and_image
            )
            item_data = data.pop("item")
            items_data.append(item_data)
            data.update(item_data)
            dataset_item = dataset_item_multi_view_tracking_and_image.model_validate(data)
            dataset_items.append(dataset_item)

        dataset_item_models = DatasetItemModel.from_dataset_items(
            dataset_items, dataset_schema_multi_view_tracking_and_image
        )

        for dataset_item, dataset_item_model, item_data in zip(dataset_items, dataset_item_models, items_data):
            assert dataset_item_model.id == dataset_item.id
            assert dataset_item_model.item == ItemModel.from_row(
                item_data,
                TableInfo(
                    name="item",
                    group="item",
                    base_schema=get_super_type_from_dict(
                        dataset_schema_multi_view_tracking_and_image.schemas["item"], _PIXANO_SCHEMA_REGISTRY
                    ).__name__,
                ),
            )
            has_video = dataset_item.video != []

            if has_video:
                assert dataset_item_model.views["video"] == ViewModel.from_rows(
                    dataset_item.video,
                    TableInfo(
                        name="video",
                        group="views",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["video"], _PIXANO_SCHEMA_REGISTRY
                        ).__name__,
                    ),
                )
                assert dataset_item_model.entities["tracks"] == EntityModel.from_rows(
                    dataset_item.tracks,
                    TableInfo(
                        name="tracks",
                        group="entities",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["tracks"], _PIXANO_SCHEMA_REGISTRY
                        ).__name__,
                    ),
                )
                assert dataset_item_model.annotations["tracklets"] == AnnotationModel.from_rows(
                    dataset_item.tracklets,
                    TableInfo(
                        name="tracklets",
                        group="annotations",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["tracklets"], _PIXANO_SCHEMA_REGISTRY
                        ).__name__,
                    ),
                )
                assert dataset_item_model.entities["entities_video"] == EntityModel.from_rows(
                    dataset_item.entities_video,
                    TableInfo(
                        name="entities_video",
                        group="entities",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["entities_video"],
                            _PIXANO_SCHEMA_REGISTRY,
                        ).__name__,
                    ),
                )
                assert dataset_item_model.annotations["keypoints_video"] == AnnotationModel.from_rows(
                    dataset_item.keypoints_video,
                    TableInfo(
                        name="keypoints_video",
                        group="annotations",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["keypoints_video"],
                            _PIXANO_SCHEMA_REGISTRY,
                        ).__name__,
                    ),
                )
                assert dataset_item_model.annotations["bboxes_video"] == AnnotationModel.from_rows(
                    dataset_item.bboxes_video,
                    TableInfo(
                        name="bboxes_video",
                        group="annotations",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["bboxes_video"],
                            _PIXANO_SCHEMA_REGISTRY,
                        ).__name__,
                    ),
                )
            else:
                assert dataset_item_model.views["video"] == []
                assert dataset_item_model.entities["tracks"] == []
                assert dataset_item_model.entities["entities_video"] == []
                assert dataset_item_model.annotations["tracklets"] == []
                assert dataset_item_model.annotations["keypoints_video"] == []
                assert dataset_item_model.annotations["bboxes_video"] == []

            has_image = dataset_item.image is not None
            if has_image:
                assert dataset_item_model.views["image"] == ViewModel.from_row(
                    dataset_item.image,
                    TableInfo(
                        name="image",
                        group="views",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["image"], _PIXANO_SCHEMA_REGISTRY
                        ).__name__,
                    ),
                )
                assert dataset_item_model.entities["entity_image"] == EntityModel.from_row(
                    dataset_item.entity_image,
                    TableInfo(
                        name="entity_image",
                        group="entities",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["entity_image"],
                            _PIXANO_SCHEMA_REGISTRY,
                        ).__name__,
                    ),
                )
                assert dataset_item_model.annotations["keypoints_image"] == AnnotationModel.from_rows(
                    dataset_item.keypoints_image,
                    TableInfo(
                        name="keypoints_image",
                        group="annotations",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["keypoints_image"],
                            _PIXANO_SCHEMA_REGISTRY,
                        ).__name__,
                    ),
                )
                assert dataset_item_model.annotations["bbox_image"] == AnnotationModel.from_row(
                    dataset_item.bbox_image,
                    TableInfo(
                        name="bbox_image",
                        group="annotations",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["bbox_image"],
                            _PIXANO_SCHEMA_REGISTRY,
                        ).__name__,
                    ),
                )
                assert dataset_item_model.annotations["mask_image"] == AnnotationModel.from_row(
                    dataset_item.mask_image,
                    TableInfo(
                        name="mask_image",
                        group="annotations",
                        base_schema=get_super_type_from_dict(
                            dataset_schema_multi_view_tracking_and_image.schemas["mask_image"],
                            _PIXANO_SCHEMA_REGISTRY,
                        ).__name__,
                    ),
                )
            else:
                assert dataset_item_model.views["image"] is None
                assert dataset_item_model.entities["entity_image"] is None
                assert dataset_item_model.annotations["keypoints_image"] == []
                assert dataset_item_model.annotations["bbox_image"] is None
                assert dataset_item_model.annotations["mask_image"] is None

    def test_to_dataset_items(
        self,
        dataset_schema_multi_view_tracking_and_image: DatasetSchema,
    ):
        dataset_items = []
        items_data = []
        for data in generate_data_multi_view_tracking_and_image(
            num_rows=5, schemas=dataset_schema_multi_view_tracking_and_image.schemas
        ):
            dataset_item_multi_view_tracking_and_image = DatasetItem.from_dataset_schema(
                dataset_schema_multi_view_tracking_and_image
            )
            item_data = data.pop("item")
            items_data.append(item_data)
            data.update(item_data)
            dataset_item = dataset_item_multi_view_tracking_and_image.model_validate(data)
            dataset_items.append(dataset_item)

        dataset_item_models = DatasetItemModel.from_dataset_items(
            dataset_items, dataset_schema_multi_view_tracking_and_image
        )

        dataset_items_recovered = DatasetItemModel.to_dataset_items(
            dataset_item_models, dataset_schema_multi_view_tracking_and_image
        )

        for dataset_item, dataset_item_recovered in zip(dataset_items, dataset_items_recovered, strict=True):
            assert dataset_item.model_dump() == dataset_item_recovered.model_dump()
