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
                        "annotations": {"bbox": {"count": 0 }, "keypoints": {"count": 0 }},
                        "embeddings": {"image_embedding": {"count": 1 }, "video_embedding": {"count": 2 }},
                        "entities": {"persons": 0, "tracks": {"count": 10 }},
                        "views": {"image": {"count": 1 }, "video": {"count": 2 }},
                    },
                }
            ]
        },
    )

    info: dict[str, dict[str, dict[str, int|float]]]
