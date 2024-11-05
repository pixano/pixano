# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict

from .items import ItemModel


class ItemInfoModel(ItemModel):
    """Item information.

    It contains all the information contained in an [ItemModel][pixano.app.models.ItemModel] and additional
    information about the dataset item such as the number of annotations, embeddings, entities and views.

    Attributes:
        infos: Information about the dataset item. Structure:
            {info_name: {sub_info_name: {"count": int, ...}, ...}, ...}
    """

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "1",
                    "table_info": {"group": "item", "name": "item", "base_schema": "Item"},
                    "data": {"split": "train", "source": "source1"},
                    "infos": {
                        "annotations": {"bbox": {"count": 0}, "keypoints": {"count": 0}},
                        "embeddings": {"image_embedding": {"count": 1}, "video_embedding": {"count": 2}},
                        "entities": {"persons": 0, "tracks": {"count": 10}},
                        "views": {"image": {"count": 1}, "video": {"count": 2}},
                    },
                }
            ]
        },
    )

    info: dict[str, dict[str, dict[str, int | float]]]
