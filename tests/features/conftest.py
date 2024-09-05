# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from tests.fixtures.datasets.builders.builder import dumb_builder
from tests.fixtures.datasets.builders.folder import (
    image_folder,
    image_folder_builder,
    video_folder,
    video_folder_builder,
)
from tests.fixtures.datasets.dataset import dumb_dataset
from tests.fixtures.datasets.dataset_info import info
from tests.fixtures.datasets.dataset_item import (
    dataset_item_bboxes_metadata,
    dataset_item_image_bboxes_keypoint,
    dataset_item_image_bboxes_keypoints,
    dataset_item_image_embeddings,
    dataset_item_video_bboxes_keypoint,
)
from tests.fixtures.datasets.dataset_schema import (
    dataset_schema_1,
    dataset_schema_image_embeddings,
    json_dataset_schema_1,
)
from tests.fixtures.features.bbox import bbox_xywh, bbox_xyxy, coords, height_width
from tests.fixtures.features.compressed_rle import counts, rle, size
from tests.fixtures.features.embedding import dumb_embedding_function, embedding_8, view_embedding_8
from tests.fixtures.features.item import custom_item_1, custom_item_2
