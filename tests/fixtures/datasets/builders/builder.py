# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile

import pytest

from pixano.datasets.builders.dataset_builder import DatasetBuilder
from pixano.datasets.features import BBox, Entity, Image
from pixano.datasets.features.types.schema_reference import EntityRef, ItemRef, ViewRef
from tests.fixtures.datasets import dataset_info as fixture_info
from tests.fixtures.datasets import dataset_item as fixture_dataset_item


info = fixture_info.info
dataset_item = fixture_dataset_item.dataset_item_image_bboxes_keypoint


class DumbDatasetBuilder(DatasetBuilder):
    def __init__(self, num_rows=5, *args, **kwargs):
        self.num_rows = num_rows
        super().__init__(*args, **kwargs)

    def generate_data(self):
        for i in range(self.num_rows):
            item_id = str(i)
            image = Image(
                id=f"image_{i}",
                item_ref=ItemRef(id=item_id),
                url=f"image_{i}.jpg",
                width=100,
                height=100,
                format="jpg",
            )
            entities = []
            bboxes = []
            for j in range(0 if not (i % 2) else 2):
                entities.append(
                    Entity(
                        id=f"entity_{i}_{j}",
                        item_ref=ItemRef(id=item_id),
                        view_ref=ViewRef(id=f"image_{i}", name="image"),
                    )
                )
                bboxes.append(
                    BBox(
                        coords=[0, 0, 100, 100],
                        format="xywh",
                        is_normalized=False,
                        confidence=0.9,
                        id=f"bbox_{i}_{j}",
                        item_ref=ItemRef(id=item_id),
                        view_ref=ViewRef(id=f"image_{i}", name="image"),
                        entity_ref=EntityRef(id=f"entity_{i}_{j}", name="entities"),
                    )
                )

            yield {
                "image": image,
                self.item_schema_name: self.item_schema(
                    id=item_id, metadata=f"metadata_{i}", split="train" if i % 2 else "test"
                ),
                "entities": entities,
                "bboxes": bboxes,
            }


@pytest.fixture
def dumb_builder(dataset_item_image_bboxes_keypoint, info):
    return DumbDatasetBuilder(5, tempfile.mkdtemp(), tempfile.mkdtemp(), dataset_item_image_bboxes_keypoint, info)
