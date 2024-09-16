# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pixano.features.schemas.base_schema import BaseSchema
from pixano.features.schemas.registry import _SCHEMA_REGISTRY
from pixano.features.schemas.registry import register_schema as register_schema_base


def register_schema(schema: type[BaseSchema]):
    if schema.__name__ not in _SCHEMA_REGISTRY:
        register_schema_base(schema)
