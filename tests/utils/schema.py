# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from lancedb.pydantic import LanceModel


def register_schema(schema: type[LanceModel]) -> type[LanceModel]:
    """Compatibility helper for tests while schemas no longer require registration."""
    return schema
