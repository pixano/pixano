# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import ConfigDict, field_validator

from pixano.datasets import Dataset
from pixano.features import EntityDynamicState, SchemaGroup, is_entity_dynamic_state

from .base_schema import BaseSchemaModel
from .table_info import TableInfo


class EntityDynamicStateModel(BaseSchemaModel[EntityDynamicState]):
    """Model for [EntityDynamicState][pixano.features.EntityDynamicState] rows."""

    model_config = ConfigDict(
        validate_assignment=True,
        json_schema_extra={
            "examples": [
                {
                    "id": "state_1",
                    "table_info": {
                        "group": "entity_dynamic_states",
                        "name": "states",
                        "base_schema": "EntityDynamicState",
                    },
                    "data": {
                        "item_id": "1",
                        "entity_id": "entity_1",
                        "tracklet_id": "tracklet_1",
                        "source_id": "source_1",
                        "view_name": "image",
                        "frame_id": "frame_1",
                        "frame_index": 0,
                    },
                }
            ]
        },
    )

    @field_validator("table_info")
    @classmethod
    def _validate_table_info(cls, value: TableInfo) -> TableInfo:
        """Validate table info."""
        if value.group != SchemaGroup.ENTITY_DYNAMIC_STATE.value:
            raise ValueError(f"Table info group must be {SchemaGroup.ENTITY_DYNAMIC_STATE.value}.")
        return value

    def to_row(self, dataset: Dataset) -> EntityDynamicState:
        """Create an [EntityDynamicState][pixano.features.EntityDynamicState] row from the model."""
        schema = dataset.schema.resolve_schema(self.table_info.name)
        if not is_entity_dynamic_state(schema):
            raise ValueError(f"Schema type must be a subclass of {EntityDynamicState.__name__}.")
        return super().to_row(dataset)
