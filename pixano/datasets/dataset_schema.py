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

from pydantic import BaseModel, ConfigDict, PrivateAttr, create_model

from .features import BaseSchema, Item
from .features.schemas.group import _SCHEMA_GROUP_TO_SCHEMA_DICT, _SchemaGroup
from .features.schemas.registry import _PIXANO_SCHEMA_REGISTRY, _SCHEMA_REGISTRY
from .features.types.registry import _TYPES_REGISTRY


class SchemaRelation(Enum):
    """Relation between tables."""

    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    ONE_TO_ONE = "one_to_one"
    MANY_TO_MANY = "many_to_many"


def _get_super_type_from_dict(
    sub_type: type, dict_types: dict[str, type]
) -> type | None:
    """Get the first super type in a dictionary of types from type."""
    if sub_type in dict_types.values():
        return sub_type

    sup_type = None
    for dict_type in dict_types.values():
        if issubclass(sub_type, dict_type):
            sup_type = dict_type
            break

    if sup_type is None:
        return None

    found_type = True
    while found_type:
        found_type = False
        for dict_type in dict_types.values():
            if (
                issubclass(sub_type, dict_type)
                and issubclass(dict_type, sup_type)
                and dict_type is not sup_type
            ):
                sup_type = dict_type
                found_type = True
                break

    return sup_type


def _dataset_item_to_dict(
    _dataset_item: type["DatasetItem"],
) -> dict[str, dict[str, BaseSchema | SchemaRelation]]:
    # extra item fields infered from the cls
    item_fields = {}

    # table schemas
    dataset_schema_dict = {}
    dataset_schema_dict["relations"] = {_SchemaGroup.ITEM.value: {}}
    schemas = {}

    for field_name, field in _dataset_item.model_fields.items():
        if isinstance(field.annotation, GenericAlias):
            origin = field.annotation.__origin__
            args = field.annotation.__args__

            if origin in [list, tuple]:
                if issubclass(args[0], tuple(_SCHEMA_REGISTRY.values())):
                    # Categorizing List of Object as objects
                    schemas[field_name] = args[0]
                    dataset_schema_dict["relations"][_SchemaGroup.ITEM.value][
                        field_name
                    ] = SchemaRelation.ONE_TO_MANY
                    dataset_schema_dict["relations"][field_name] = {
                        _SchemaGroup.ITEM.value: SchemaRelation.MANY_TO_ONE
                    }
                else:
                    item_fields[field_name] = (list[args[0]], ...)
            else:
                # Default case: categorize as item attribute
                item_fields[field_name] = (args[0], ...)
        elif issubclass(field.annotation, tuple(_SCHEMA_REGISTRY.values())):
            # Categorizing Image as a view
            schemas[field_name] = field.annotation
            dataset_schema_dict["relations"][_SchemaGroup.ITEM.value][field_name] = (
                SchemaRelation.ONE_TO_ONE
            )
            dataset_schema_dict["relations"][field_name] = {
                _SchemaGroup.ITEM.value: SchemaRelation.ONE_TO_ONE
            }
        else:
            # Default case: categorize as item attribute
            item_fields[field_name] = (field.annotation, ...)

    CustomItem = create_model("Item", **item_fields, __base__=Item)

    schemas[_SchemaGroup.ITEM.value] = CustomItem
    dataset_schema_dict["schemas"] = schemas
    return dataset_schema_dict


def _serialize_schema(schema: type[BaseSchema]) -> dict[str, dict[str, Any]]:
    json = {
        "schema": schema.__name__.lower().replace(" ", "_"),
        "base_schema": _get_super_type_from_dict(schema, _PIXANO_SCHEMA_REGISTRY)
        .__name__.lower()
        .replace(" ", "_"),
    }
    fields = {}
    for field_name, field in schema.model_fields.items():
        if isinstance(field.annotation, GenericAlias):
            origin = field.annotation.__origin__
            args = field.annotation.__args__

            if origin in [list, tuple]:
                if issubclass(args[0], tuple(_TYPES_REGISTRY.values())):
                    fields[field_name] = {
                        "type": args[0].__name__.lower().replace(" ", "_"),
                        "collection": True,
                    }
                else:
                    fields[field_name] = {
                        "type": args[0].__name__.lower().replace(" ", "_"),
                        "collection": True,
                    }
            else:
                raise NotImplementedError("Should be a list or tuple.")
        else:
            if issubclass(field.annotation, tuple(_TYPES_REGISTRY.values())):
                fields[field_name] = {
                    "type": field.annotation.__name__.lower().replace(" ", "_"),
                    "collection": False,
                }
            else:
                fields[field_name] = {
                    "type": field.annotation.__name__.lower().replace(" ", "_"),
                    "collection": False,
                }
    json["fields"] = fields
    return json


def _serialize_dataset_schema_dict(
    dataset_schema_dict: dict[str, dict[str, BaseSchema] | dict[str, bool]],
) -> dict[str, dict[str, Any]]:
    dataset_schema_json = {
        "relations": {
            schema1: {
                schema2: relation.value for schema2, relation in relations.items()
            }
            for schema1, relations in dataset_schema_dict["relations"].items()
        },
        "schemas": {},
    }
    for table_name, schema in dataset_schema_dict["schemas"].items():
        dataset_schema_json["schemas"][table_name] = _serialize_schema(schema)
    return dataset_schema_json


def _deserialize_schema(json: dict[str, Any]):
    fields = {}
    for key, value in json["fields"].items():
        if value["type"] in _TYPES_REGISTRY:
            type = _TYPES_REGISTRY[value["type"]]
        else:
            raise ValueError(f"Type {value['type']} not registered")
        if value["collection"]:
            type = list[type]
        fields[key] = (type, ...)

    if json["schema"] in _SCHEMA_REGISTRY:
        table_type = _SCHEMA_REGISTRY[json["schema"]]
    else:
        table_type = _PIXANO_SCHEMA_REGISTRY[json["base_schema"]]

    allow_table_extra = any(
        field not in table_type.model_fields.keys() for field in fields.keys()
    )
    if allow_table_extra:
        fields["model_config"] = ConfigDict(extra="allow")
    model = create_model(table_type.__name__, **fields, __base__=table_type)

    return model


def _deserialize_dataset_schema_dict(
    json_schema: dict[str, dict[str, Any]],
):
    dataset_schema_dict = {
        "relations": {
            schema1: {
                schema2: SchemaRelation(relation)
                for schema2, relation in relations.items()
            }
            for schema1, relations in json_schema["relations"].items()
        },
        "schemas": {},
    }
    for table_name, schema in json_schema["schemas"].items():
        dataset_schema_dict["schemas"][table_name] = _deserialize_schema(schema)
    return dataset_schema_dict


class DatasetSchema(BaseModel):
    """DatasetSchema.

    Attributes:
        schemas (dict[str, BaseSchema]): The tables.
    """

    schemas: dict[str, type[BaseSchema]]
    relations: dict[str, dict[str, SchemaRelation]]
    _groups: dict[_SchemaGroup, list[str]] = PrivateAttr(
        {key: [] for key in _SchemaGroup}
    )

    def _assign_table_groups(self) -> None:
        for table, schema in self.schemas.items():
            found_group = False
            for group, group_type in _SCHEMA_GROUP_TO_SCHEMA_DICT.items():
                if issubclass(schema, group_type):
                    self._groups[group].append(table)
                    found_group = True
                    break
            if not found_group:
                raise ValueError(f"Invalid table type {schema}")
        return

    def to_json(self, json_fp: Path) -> None:
        """Save DatasetSchema to json file."""
        if json_fp.exists():
            old_json_content = json.loads(json_fp.read_text(encoding="utf-8"))
        else:
            old_json_content = None

        json_content = _serialize_dataset_schema_dict(
            {
                "relations": self.relations,
                "schemas": self.schemas,
            }
        )

        if old_json_content is not None:
            for table, schema in json_content["schemas"].items():
                schema["schema"] = old_json_content["schemas"][table]["schema"]

        json_fp.write_text(json.dumps(json_content, indent=4), encoding="utf-8")

    def _get_dataset_item_schema(self) -> type[BaseSchema]:
        return self.schemas[_SchemaGroup.ITEM.value]

    @staticmethod
    def format_table_name(table_name: str) -> str:
        """Format table name.

        Args:
            table_name (str): Table name

        Returns:
            str: Formatted table name
        """
        return table_name.lower().replace(" ", "_")

    @staticmethod
    def format_table_names(schema_json: dict[str, dict[str, str]]):
        """Format table names."""
        keys = list(schema_json.keys())
        for table in keys:
            formatted_table_name = DatasetSchema.format_table_name(table)
            schema_json[formatted_table_name] = schema_json.pop(table)
        return schema_json

    @staticmethod
    def validate_json(  # noqa: D417
        schema_json: dict[str, dict[str, Any]], *args, **kwargs
    ) -> "DatasetSchema":
        """Validate DatasetSchema from json.

        Args:
            schema_json (dict[str, dict[str, Any]]): JSON.

        Returns:
            DatasetSchema: DatasetSchema
        """
        schema_json["schemas"] = DatasetSchema.format_table_names(
            schema_json["schemas"]
        )
        schema_json["relations"] = DatasetSchema.format_table_names(
            schema_json["relations"]
        )

        if _SchemaGroup.ITEM.value not in schema_json["schemas"].keys():
            raise ValueError(f"Schema should contain a {_SchemaGroup.ITEM.value} key.")

        dataset_schema_dict = _deserialize_dataset_schema_dict(schema_json)

        return DatasetSchema.model_validate(dataset_schema_dict, *args, **kwargs)

    @staticmethod
    def validate_dict(  # noqa: D417
        schema_dict: dict[str, dict[str, Any]], *args, **kwargs
    ) -> "DatasetSchema":
        """Validate DatasetSchema from dictionary.

        Args:
            schema_dict (dict[str, dict[str, Any]]): Dictionary.

        Returns:
            DatasetSchema: DatasetSchema
        """
        schema_dict["schemas"] = DatasetSchema.format_table_names(
            schema_dict["schemas"]
        )
        schema_dict["relations"] = DatasetSchema.format_table_names(
            schema_dict["relations"]
        )
        return DatasetSchema.model_validate(schema_dict, *args, **kwargs)

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

        schema = DatasetSchema.validate_json(schema_json)
        schema._assign_table_groups()

        return schema

    @staticmethod
    def from_dataset_item(model: type["DatasetItem"]) -> "DatasetSchema":
        """Create DatasetSchema from a DatasetItem.

        Args:
            model (type[DatasetItem]): DatasetItem.

        Returns:
            DatasetSchema: DatasetSchema
        """
        dataset_schema_dict = _dataset_item_to_dict(model)
        schema = DatasetSchema.validate_dict(dataset_schema_dict)
        schema._assign_table_groups()

        return schema


class DatasetItem(BaseModel):
    """Dataset Item."""

    @classmethod
    def to_dataset_schema(cls) -> DatasetSchema:
        """Convert DatasetItem to a DatasetSchema."""
        return DatasetSchema.from_dataset_item(cls)

    @classmethod
    def to_dataset_schema_dict(
        cls,
    ) -> dict[str, dict[str, BaseSchema | SchemaRelation]]:
        """Convert DatasetItem to a dataset schema dict."""
        return _dataset_item_to_dict(cls)

    @classmethod
    def serialize(cls) -> dict[str, dict[str, Any]]:
        """Serialize DatasetItem."""
        return _serialize_dataset_schema_dict(_dataset_item_to_dict(cls))


def create_custom_dataset_item_class_from_dataset_schema(
    dataset_schema: DatasetSchema,
) -> type[DatasetItem]:
    """Create a custom dataset item class based on the schema.

    Args:
        dataset_schema (DatasetSchema): The dataset schema

    Returns:
        type[DatasetItem]: The custom dataset item class
    """
    item_type = dataset_schema.schemas[_SchemaGroup.ITEM.value]
    fields = {}

    for schema, relation in dataset_schema.relations[_SchemaGroup.ITEM.value].items():
        # Add default value in case an item does not have a specific view or object.
        if relation == SchemaRelation.ONE_TO_MANY:
            fields[schema] = (list[dataset_schema.schemas[schema]], [])
        else:
            fields[schema] = (dataset_schema.schemas[schema], None)

    for field_name, field in item_type.model_fields.items():
        # No default value as all items metadata should be retrieved.
        fields[field_name] = (field.annotation, ...)

    CustomDatasetItem = create_model(
        "DatasetItem",
        **fields,
        __base__=DatasetItem,
    )
    return CustomDatasetItem


def create_sub_dataset_item(
    dataset_item: type[DatasetItem],
    selected_fields: list[str],
) -> type[DatasetItem]:
    """Create a new dataset item based on the selected fields of the original dataset
    item.

    .. note::
        The id field is always included in the sub dataset item.

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
    for field_name, field in dataset_item.model_fields.items():
        if field_name in selected_fields or field_name == "id":
            fields[field_name] = (field.annotation, field.default)

    SubDatasetItem: type[DatasetItem] = create_model(
        dataset_item.__name__,
        **fields,
        __base__=DatasetItem,
    )

    return SubDatasetItem
