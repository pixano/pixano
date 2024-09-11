# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Any

from pydantic import BaseModel


class ItemInfo(BaseModel):
    """Item info."""

    id: str
    infos: dict[str, dict[str, int]]
    data: dict[str, Any]
