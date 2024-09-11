# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict

from .items import ItemModel


class ItemInfo(ItemModel):
    """Item info."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "1",
                    "table_info": {"group": "item", "name": "item", "base_schema": "Item"},
                    "data": {"split": "train", "source": "source1"},
                    "infos": {
                        "annotations": {"bbox": 0, "keypoints": 0},
                        "embeddings": {"image_embedding": 1, "video_embedding": 2},
                        "entities": {"persons": 0, "tracks": 10},
                        "views": {"image": 1, "video": 2},
                    },
                }
            ]
        },
    )

    id: str
    info: dict[str, dict[str, int]]
