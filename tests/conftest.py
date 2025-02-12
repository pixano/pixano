# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from tests.fixtures.app.app import (
    app_and_settings,
    app_and_settings_copy,
    app_and_settings_with_client,
    app_and_settings_with_client_copy,
    empty_app_and_settings,
    empty_app_and_settings_with_client,
)
from tests.fixtures.app.models.dataset_info import (
    info_model_dataset_image_bboxes_keypoint,
    info_model_dataset_multi_view_tracking_and_image,
)
from tests.fixtures.app.routers.browser import (
    browser_dataset_image_bboxes_keypoint,
    browser_dataset_multi_view_tracking_and_image,
    browser_dataset_multi_view_tracking_and_image_semantic_search,
    df_semantic_search,
)
from tests.fixtures.app.routers.models.annotations import (
    two_difficult_bboxes_models_from_dataset_multiview_tracking_and_image,
)
from tests.fixtures.datasets.builders.builder import (
    dataset_builder_image_bboxes_keypoint,
    dataset_builder_multi_view_tracking_and_image,
)
from tests.fixtures.datasets.builders.folder import (
    image_folder,
    image_folder_builder,
    image_folder_builder_no_jsonl,
    image_folder_no_jsonl,
    video_folder,
    video_folder_builder,
    vqa_folder,
    vqa_folder_builder,
)
from tests.fixtures.datasets.dataset import (
    dataset_image_bboxes_keypoint,
    dataset_image_bboxes_keypoint_copy,
    dataset_multi_view_tracking_and_image,
    dataset_multi_view_tracking_and_image_copy,
)
from tests.fixtures.datasets.dataset_info import (
    info_dataset_image_bboxes_keypoint,
    info_dataset_multi_view_tracking_and_image,
)
from tests.fixtures.datasets.dataset_item import (
    dataset_item_bboxes_metadata,
    dataset_item_image_bboxes_keypoint,
    dataset_item_image_bboxes_keypoints,
    dataset_item_image_embeddings,
    dataset_item_multi_view_tracking_and_image,
    dataset_item_video_bboxes_keypoint,
)
from tests.fixtures.datasets.dataset_schema import (
    dataset_schema_image_bboxes_keypoint,
    dataset_schema_item_categories_image_bbox,
    dataset_schema_item_categories_name_index_image_bbox_embedding,
    dataset_schema_multi_view_tracking_and_image,
    json_dataset_image_bboxes_keypoint,
    json_dataset_schema_item_categories_image_bbox,
    json_dataset_schema_item_categories_name_index_image_bbox_embedding,
    json_dataset_schema_multi_view_tracking_and_image,
)
from tests.fixtures.features.bbox import (
    bbox_difficult,
    bbox_xywh,
    bbox_xyxy,
    coords,
    height_width,
    two_difficult_bboxes_from_dataset_multiview_tracking_and_image,
)
from tests.fixtures.features.compressed_rle import counts, rle, size
from tests.fixtures.features.embedding import dumb_embedding_function, embedding_8, view_embedding_8
from tests.fixtures.features.entity import (
    entity_category,
    two_image_entities_from_dataset_multiview_tracking_and_image,
)
from tests.fixtures.features.item import item_categories, item_categories_name_index, item_metadata
from tests.fixtures.features.sequence_frame import sequence_frame_category
from tests.fixtures.inference.client import simple_pixano_inference_client
