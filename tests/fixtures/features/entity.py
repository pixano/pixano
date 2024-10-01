# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import pytest

from pixano.datasets import Dataset
from pixano.features import Entity
from tests.utils.schema import register_schema


@pytest.fixture(scope="session")
def entity_category():
    class EntityCategory(Entity):
        category: str = "none"

    register_schema(EntityCategory)
    return EntityCategory


@pytest.fixture(scope="session")
def two_image_entities_from_dataset_multiview_tracking_and_image(dataset_multi_view_tracking_and_image: Dataset):
    return dataset_multi_view_tracking_and_image.get_data("entity_image", limit=2)
