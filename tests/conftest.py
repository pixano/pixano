# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from tests.fixtures.datasets.builders.builder import (
    dataset_builder_image_bboxes_keypoint,
    dataset_builder_multi_view_tracking_and_image,
)
from tests.fixtures.datasets.builders.folder import (
    image_folder,
    image_folder_builder,
    video_folder,
    video_folder_builder,
)
from tests.fixtures.datasets.dataset import dataset_image_bboxes_keypoint, dataset_multi_view_tracking_and_image
from tests.fixtures.datasets.dataset_info import info
from tests.fixtures.datasets.dataset_item import (
    dataset_item_bboxes_metadata,
    dataset_item_image_bboxes_keypoint,
    dataset_item_image_bboxes_keypoints,
    dataset_item_image_embeddings,
    dataset_item_multi_view_tracking_and_image,
    dataset_item_video_bboxes_keypoint,
)
from tests.fixtures.datasets.dataset_schema import (
    dataset_schema_item_categories_image_bbox,
    dataset_schema_item_categories_name_index_image_bbox_embedding,
    dataset_schema_multi_view_tracking_and_image,
    json_dataset_schema_item_categories_image_bbox,
    json_dataset_schema_item_categories_name_index_image_bbox_embedding,
    json_dataset_schema_multi_view_tracking_and_image,
)
from tests.fixtures.features.bbox import bbox_difficult, bbox_xywh, bbox_xyxy, coords, height_width
from tests.fixtures.features.compressed_rle import counts, rle, size
from tests.fixtures.features.embedding import dumb_embedding_function, embedding_8, view_embedding_8
from tests.fixtures.features.entity import entity_category
from tests.fixtures.features.item import item_categories, item_categories_name_index
from tests.fixtures.features.sequence_frame import sequence_frame_category
