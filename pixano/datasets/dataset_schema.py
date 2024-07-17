# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from enum import Enum
from pathlib import Path
from types import GenericAlias
from typing import Any

from pydantic import BaseModel, PrivateAttr, create_model, model_validator
from typing_extensions import Self

from .features.schemas import BaseSchema, Item
from .features.schemas.registry import _SCHEMA_REGISTRY
from .features.schemas.schema_group import _SCHEMA_GROUP_TO_SCHEMA_DICT, _SchemaGroup


class SchemaRelation(Enum):
    """Relation between tables."""

    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    ONE_TO_ONE = "one_to_one"
    MANY_TO_MANY = "many_to_many"


class DatasetSchema(BaseModel):
    """DatasetSchema.

    Attributes:
        schemas (dict[str, BaseSchema]): The tables.
    """

    schemas: dict[str, type[BaseSchema]]
    relations: dict[str, dict[str, SchemaRelation]]
    _groups: dict[_SchemaGroup, list[str]] = PrivateAttr({key: [] for key in _SchemaGroup})

    @model_validator(mode="after")
    def _assign_table_groups(self) -> Self:
        for table in (
            list(self.schemas.keys())
            + list(self.relations.keys())
            + [k for v in self.relations.values() for k in v.keys()]
        ):
            # Check if table name is formatted correctly
            if table != self.format_table_name(table):
                raise ValueError(f"Table {table} should be formatted correctly.")
            # Check if table is in schemas
            elif table not in list(self.schemas.keys()):
                raise ValueError(f"Table {table} not found in schemas.")

        item_found = False
        for table, schema in self.schemas.items():
            if issubclass(schema, Item):
                if item_found:
                    raise ValueError("DatasetSchema should contain only one item schema.")
                item_found = True
            found_group = False
            for group, group_type in _SCHEMA_GROUP_TO_SCHEMA_DICT.items():
                if issubclass(schema, group_type):
                    self._groups[group].append(table)
                    found_group = True
                    break
            if not found_group:
                raise ValueError(f"Invalid table type {schema}")
        if not item_found:
            raise ValueError("DatasetSchema should contain an item schema.")
        return self

    @staticmethod
    def format_table_name(table_name: str) -> str:
        """Format table name.

        Args:
            table_name (str): Table name

        Returns:
            str: Formatted table name
        """
        return table_name.lower().replace(" ", "_")

    def serialize(self) -> dict[str, dict[str, Any]]:
        """Serialize the dataset schema.

        The serialized schema is a dictionary with the following format:
        {
            "relations": {
                "item": {
                    "image": "one_to_one",
                }
            },
            "schemas": {
                "table1": {
                    "schema": "CustomItem",
                    "base_schema": "Item",
                    "fields": {
                        "id": {
                            "type": "str",
                            "collection": False
                        },
                        "split": {
                            "type": "str",
                            "collection": False
                        },
                        ...
                    }

                }
            }
        }

        Returns:
            dict[str, dict[str, Any]]: Serialized dataset schema
        """
        dataset_schema_json: dict[str, dict[str, Any]] = {
            "relations": {
                schema1: {schema2: relation.value for schema2, relation in relations.items()}
                for schema1, relations in self.relations.items()
            },
            "schemas": {},
        }
        for table_name, schema in self.schemas.items():
            dataset_schema_json["schemas"][table_name] = schema.serialize()
        return dataset_schema_json

    def deserialize(dataset_schema_json: dict[str, dict[str, Any]]) -> "DatasetSchema":
        """Unserialize the dataset schema.

        Args:
            dataset_schema_json: Serialized dataset schema

        Returns:
            DatasetSchema: DatasetSchema
        """
        dataset_schema_dict: dict[str, Any] = {
            "relations": {
                schema1: {schema2: SchemaRelation(relation) for schema2, relation in relations.items()}
                for schema1, relations in dataset_schema_json["relations"].items()
            },
            "schemas": {},
        }
        for table_name, schema in dataset_schema_json["schemas"].items():
            dataset_schema_dict["schemas"][table_name] = BaseSchema.deserialize(schema)
        return DatasetSchema(**dataset_schema_dict)

    def to_json(self, json_fp: Path) -> None:
        """Save DatasetSchema to json file."""
        if json_fp.exists():
            old_json_content = json.loads(json_fp.read_text(encoding="utf-8"))
        else:
            old_json_content = None

        json_content = self.serialize()

        # Keep the schema field from the old json content for custom schemas.
        if old_json_content is not None:
            for table, schema in json_content["schemas"].items():
                schema["schema"] = old_json_content["schemas"][table]["schema"]

        json_fp.write_text(json.dumps(json_content, indent=4), encoding="utf-8")

    @staticmethod
    def from_json(
        json_fp: Path,
    ) -> "DatasetSchema":
        """Read DatasetSchema from JSON file.

        Args:
            json_fp (Path): JSON file path

        Returns:
            DatasetSchema: DatasetSchema
        """
        schema_json = json.loads(json_fp.read_text(encoding="utf-8"))

        return DatasetSchema.deserialize(schema_json)

    @staticmethod
    def from_dataset_item(dataset_item: type["DatasetItem"]) -> "DatasetSchema":
        """Create DatasetSchema from a DatasetItem.

        Args:
            dataset_item (type[DatasetItem]): DatasetItem.

        Returns:
            DatasetSchema: DatasetSchema
        """
        item_fields = {}

        # table schemas
        dataset_schema_dict: dict[str, Any] = {}
        dataset_schema_dict["relations"] = {_SchemaGroup.ITEM.value: {}}
        schemas = {}

        for field_name, field in dataset_item.model_fields.items():
            # Check if field is a generic alias (list or tuple)
            if isinstance(field.annotation, GenericAlias):
                origin = field.annotation.__origin__
                args = field.annotation.__args__

                # Check if field is list or tuple
                if origin in [list, tuple]:
                    # Categorizing list of schemas as schemas and keeping track of the relation
                    if issubclass(args[0], tuple(_SCHEMA_REGISTRY.values())):
                        schemas[field_name] = args[0]
                        dataset_schema_dict["relations"][_SchemaGroup.ITEM.value][field_name] = (
                            SchemaRelation.ONE_TO_MANY
                        )
                        dataset_schema_dict["relations"][field_name] = {
                            _SchemaGroup.ITEM.value: SchemaRelation.MANY_TO_ONE
                        }
                    else:
                        item_fields[field_name] = (list[args[0]], ...)  # type: ignore[valid-type]
                else:
                    # Default case: categorize as item attribute
                    item_fields[field_name] = (args[0], ...)  # type: ignore[valid-type]
            # Check if field is a schema
            elif issubclass(field.annotation, tuple(_SCHEMA_REGISTRY.values())):
                schemas[field_name] = field.annotation
                dataset_schema_dict["relations"][_SchemaGroup.ITEM.value][field_name] = SchemaRelation.ONE_TO_ONE
                dataset_schema_dict["relations"][field_name] = {_SchemaGroup.ITEM.value: SchemaRelation.ONE_TO_ONE}
            else:
                # Default case: item attribute
                item_fields[field_name] = (field.annotation, ...)

        CustomItem = create_model("Item", **item_fields, __base__=Item)

        schemas[_SchemaGroup.ITEM.value] = CustomItem
        dataset_schema_dict["schemas"] = schemas

        return DatasetSchema(**dataset_schema_dict)


class DatasetItem(BaseModel):
    """Dataset Item."""

    id: str
    split: str = "default"

    def to_schemas_data(self, dataset_schema: DatasetSchema) -> dict[str, BaseSchema | list[BaseSchema] | None]:
        """Convert DatasetItem to schemas data.

        Args:
            dataset_schema: DatasetSchema to convert to.

        Returns:
            dict[str, BaseSchema]: Schemas data.
        """
        schemas_data = {}
        item_data = {}
        for field_name in self.model_fields.keys():
            if field_name in dataset_schema.schemas:
                schemas_data[field_name] = getattr(self, field_name)
            else:
                item_data[field_name] = getattr(self, field_name)
        schemas_data[_SchemaGroup.ITEM.value] = dataset_schema.schemas[_SchemaGroup.ITEM.value](**item_data)
        return schemas_data

    @classmethod
    def to_dataset_schema(cls) -> DatasetSchema:
        """Convert DatasetItem to a DatasetSchema."""
        return DatasetSchema.from_dataset_item(cls)

    @staticmethod
    def from_dataset_schema(dataset_schema: DatasetSchema) -> type["DatasetItem"]:
        """Create a dataset item model based on the schema.

        Args:
            dataset_schema (DatasetSchema): The dataset schema

        Returns:
            type[DatasetItem]: The dataset item model
        """
        item_type = dataset_schema.schemas[_SchemaGroup.ITEM.value]
        fields: dict[str, Any] = {}

        for schema, relation in dataset_schema.relations[_SchemaGroup.ITEM.value].items():
            # Add default value in case an item does not have a specific view or entity.
            schema_type = dataset_schema.schemas[schema]
            if relation == SchemaRelation.ONE_TO_MANY:
                fields[schema] = (list[schema_type], [])  # type: ignore[valid-type]
            else:
                fields[schema] = (schema_type, None)

        for field_name, field in item_type.model_fields.items():
            # No default value as all items metadata should be retrieved.
            fields[field_name] = (field.annotation, ...)

        CustomDatasetItem = create_model(
            "DatasetItem",
            **fields,
            __base__=DatasetItem,
        )
        return CustomDatasetItem

    @classmethod
    def get_sub_dataset_item(cls, selected_fields: list[str]) -> type["DatasetItem"]:
        """Create a new dataset item based on the selected fields of the original dataset
        item.

        .. note::
            The id and split fields are always included in the sub dataset item.

        .. note::
            The sub dataset item does not have the methods and config of the original
            dataset item.

        Args:
            dataset_item (DatasetItem): The dataset item
            selected_fields (list[str]): The selected fields

        Returns:
            DatasetItem: The sub dataset item
        """
        fields = {}
        for field_name, field in cls.model_fields.items():
            if field_name in selected_fields or field_name in ["id", "split"]:
                if isinstance(field.annotation, GenericAlias):
                    origin = field.annotation.__origin__
                    args = field.annotation.__args__

                    # Check if field is list or tuple
                    if origin is tuple:
                        fields[field_name] = (origin[args[0], ...], field.default)  # type: ignore[index]
                    else:
                        fields[field_name] = (field.annotation, field.default)
                else:
                    fields[field_name] = (field.annotation, field.default)

        SubDatasetItem: type[DatasetItem] = create_model(
            cls.__name__,
            **fields,
            __base__=DatasetItem,
        )

        return SubDatasetItem
