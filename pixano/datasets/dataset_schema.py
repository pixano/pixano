# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from datetime import datetime
from enum import Enum
from pathlib import Path
from types import GenericAlias
from typing import Any

from pydantic import BaseModel, create_model, model_serializer, model_validator
from typing_extensions import TYPE_CHECKING, Self

from pixano.features import BaseSchema, Item
from pixano.features.schemas.registry import _SCHEMA_REGISTRY
from pixano.features.schemas.schema_group import _SCHEMA_GROUP_TO_SCHEMA_DICT, SchemaGroup
from pixano.utils.validation import validate_and_init_create_at_and_update_at


if TYPE_CHECKING:
    from pixano.datasets.dataset import Dataset


class SchemaRelation(Enum):
    """Relation between tables.

    Attributes:
        ONE_TO_MANY: One to many relation.
        MANY_TO_ONE: Many to one relation.
        ONE_TO_ONE: One to one relation.
        MANY_TO_MANY: Many to many relation
    """

    ONE_TO_MANY = "one_to_many"
    MANY_TO_ONE = "many_to_one"
    ONE_TO_ONE = "one_to_one"
    MANY_TO_MANY = "many_to_many"


class DatasetSchema(BaseModel):
    """A dataset schema that defines the tables and the relations between them.

    Attributes:
        schemas: The mapping between the table names and their schema.
        relations: The relations between the item table and the other tables.
        groups: The groups of tables. It is filled automatically based on the schemas.
    """

    schemas: dict[str, type[BaseSchema]]
    relations: dict[str, dict[str, SchemaRelation]]
    groups: dict[SchemaGroup, set[str]] = {key: set() for key in SchemaGroup if key != SchemaGroup.SOURCE}

    def add_schema(
        self, table_name: str, schema: type[BaseSchema], relation_item: SchemaRelation, overwrite_schema: bool = False
    ) -> Self:
        """Add a schema to the dataset schema.

        Args:
            table_name: Name of the table to add to the dataset schema.
            schema: Schema of the table.
            relation_item: Relationship with the item schema.
            overwrite_schema: If True, existing schema will be overwritten, else raise ValueError.

        Returns:
            The dataset schema.
        """
        table_name = self.format_table_name(table_name)
        if not overwrite_schema and table_name in self.schemas:
            raise ValueError(f"Table {table_name} already exists in the schemas.")
        elif not issubclass(schema, BaseSchema):
            raise ValueError(f"Schema {schema} should be a subclass of BaseSchema.")
        elif not isinstance(relation_item, SchemaRelation):
            raise ValueError(f"Invalid relation {relation_item}.")
        found_group = False
        for group, group_type in _SCHEMA_GROUP_TO_SCHEMA_DICT.items():
            if issubclass(schema, group_type):
                self.groups[group].add(table_name)
                found_group = True
                break
        if not found_group:
            raise ValueError(f"Invalid table type {schema}")
        self.schemas[table_name] = schema
        if relation_item == SchemaRelation.ONE_TO_ONE:
            self.relations[SchemaGroup.ITEM.value][table_name] = SchemaRelation.ONE_TO_ONE
            self.relations[table_name] = {SchemaGroup.ITEM.value: SchemaRelation.ONE_TO_ONE}
        elif relation_item == SchemaRelation.ONE_TO_MANY:
            self.relations[SchemaGroup.ITEM.value][table_name] = SchemaRelation.MANY_TO_ONE
            self.relations[table_name] = {SchemaGroup.ITEM.value: SchemaRelation.ONE_TO_MANY}
        elif relation_item == SchemaRelation.MANY_TO_ONE:
            self.relations[SchemaGroup.ITEM.value][table_name] = SchemaRelation.ONE_TO_MANY
            self.relations[table_name] = {SchemaGroup.ITEM.value: SchemaRelation.MANY_TO_ONE}
        elif relation_item == SchemaRelation.MANY_TO_MANY:
            self.relations[SchemaGroup.ITEM.value][table_name] = SchemaRelation.MANY_TO_MANY
            self.relations[table_name] = {SchemaGroup.ITEM.value: SchemaRelation.MANY_TO_MANY}
        return self

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
                if group == SchemaGroup.SOURCE:
                    continue
                if issubclass(schema, group_type):
                    found_group = True
                    if table not in self.groups[group]:
                        self.groups[group].add(table)
                    break
            if not found_group:
                raise ValueError(f"Invalid table type {schema}")
        if not item_found:
            raise ValueError("DatasetSchema should contain an item schema.")
        return self

    @model_validator(mode="after")
    def _check_relations(self) -> Self:
        for table, relations in self.relations.items():
            if table not in self.schemas:
                raise ValueError(f"Relation {table} not found in schemas.")
            for relation, relation_type in relations.items():
                if relation not in self.schemas:
                    raise ValueError(f"Relation {relation} not found in schemas.")
                if relation not in self.relations:
                    raise ValueError(f"Relation {relation} not found in relations.")
                if (
                    relation_type == SchemaRelation.ONE_TO_ONE
                    and not self.relations[relation][table] == SchemaRelation.ONE_TO_ONE
                ):
                    raise ValueError(f"Relation {table} -> {relation} should be one to one.")
                elif (
                    relation_type == SchemaRelation.ONE_TO_MANY
                    and not self.relations[relation][table] == SchemaRelation.MANY_TO_ONE
                ):
                    raise ValueError(f"Relation {table} -> {relation} should be one to many.")
                elif (
                    relation_type == SchemaRelation.MANY_TO_ONE
                    and not self.relations[relation][table] == SchemaRelation.ONE_TO_MANY
                ):
                    raise ValueError(f"Relation {table} -> {relation} should be many to one.")
                elif (
                    relation_type == SchemaRelation.MANY_TO_MANY
                    and not self.relations[relation][table] == SchemaRelation.MANY_TO_MANY
                ):
                    raise ValueError(f"Relation {table} -> {relation} should be many to many.")
        if SchemaGroup.ITEM.value not in self.relations:
            raise ValueError("Item schema should have relations.")
        else:
            if len(self.relations[SchemaGroup.ITEM.value]) != len(self.schemas) - 1:
                raise ValueError("Item schema should have relations with all other schemas.")
        return self

    @staticmethod
    def format_table_name(table_name: str) -> str:
        """Format table name.

        It converts the table name to lowercase and replaces spaces with underscores.

        Args:
            table_name: Table name.

        Returns:
            the formatted table name.
        """
        return table_name.lower().replace(" ", "_")

    def get_table_group(self, table_name: str) -> SchemaGroup:
        """Get the group of a table.

        Args:
            table_name: Table name.

        Returns:
            The group of the table.
        """
        for group, tables in self.groups.items():
            if table_name in tables:
                return group
        raise ValueError(f"Table {table_name} not found in groups.")

    @model_serializer
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
            The serialized dataset schema.
        """
        dataset_schema_json: dict[str, dict[str, Any]] = {
            "relations": {
                schema1: {schema2: relation.value for schema2, relation in relations.items()}
                for schema1, relations in self.relations.items()
            },
            "schemas": {},
            "groups": {group.value: list(schemas) for group, schemas in self.groups.items()},
        }
        for table_name, schema in self.schemas.items():
            dataset_schema_json["schemas"][table_name] = schema.serialize()
        return dataset_schema_json

    @staticmethod
    def deserialize(dataset_schema_json: dict[str, dict[str, Any]]) -> "DatasetSchema":
        """Deserialize the dataset schema.

        Args:
            dataset_schema_json: Serialized dataset schema.

        Returns:
            The dataset schema.
        """
        dataset_schema_dict: dict[str, Any] = {
            "relations": {
                schema1: {schema2: SchemaRelation(relation) for schema2, relation in relations.items()}
                for schema1, relations in dataset_schema_json["relations"].items()
            },
            "schemas": {},
            "groups": {SchemaGroup(group): set(schemas) for group, schemas in dataset_schema_json["groups"].items()},
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
                if table not in old_json_content["schemas"]:
                    continue
                schema["schema"] = old_json_content["schemas"][table]["schema"]
        json_fp.write_text(json.dumps(json_content, indent=4), encoding="utf-8")

    @staticmethod
    def from_json(
        json_fp: Path,
    ) -> "DatasetSchema":
        """Read a dataset schema from JSON file.

        Args:
            json_fp: JSON file path

        Returns:
            The dataset schema.
        """
        schema_json = json.loads(json_fp.read_text(encoding="utf-8"))

        return DatasetSchema.deserialize(schema_json)

    @staticmethod
    def from_dataset_item(dataset_item: type["DatasetItem"]) -> "DatasetSchema":
        """Create a dataset schema from a [DatasetItem][pixano.datasets.DatasetItem].

        Args:
            dataset_item: The dataset item.

        Returns:
            The dataset schema.
        """
        item_fields = {}

        # table schemas
        dataset_schema_dict: dict[str, Any] = {}
        dataset_schema_dict["relations"] = {SchemaGroup.ITEM.value: {}}
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
                        dataset_schema_dict["relations"][SchemaGroup.ITEM.value][field_name] = (
                            SchemaRelation.ONE_TO_MANY
                        )
                        dataset_schema_dict["relations"][field_name] = {
                            SchemaGroup.ITEM.value: SchemaRelation.MANY_TO_ONE
                        }
                    else:
                        item_fields[field_name] = (list[args[0]], ...)  # type: ignore[valid-type]
                else:
                    # Default case: categorize as item attribute
                    item_fields[field_name] = (args[0], ...)  # type: ignore[valid-type]
            # Check if field is a schema
            elif issubclass(field.annotation, tuple(_SCHEMA_REGISTRY.values())):
                schemas[field_name] = field.annotation
                dataset_schema_dict["relations"][SchemaGroup.ITEM.value][field_name] = SchemaRelation.ONE_TO_ONE
                dataset_schema_dict["relations"][field_name] = {SchemaGroup.ITEM.value: SchemaRelation.ONE_TO_ONE}
            else:
                # Default case: item attribute
                item_fields[field_name] = (field.annotation, ...)

        CustomItem = create_model("Item", **item_fields, __base__=Item)

        schemas[SchemaGroup.ITEM.value] = CustomItem
        dataset_schema_dict["schemas"] = schemas

        return DatasetSchema(**dataset_schema_dict)


class DatasetItem(BaseModel):
    """Dataset Item.

    It is a Pydantic model that represents an item in a dataset.

    Attributes:
        id: The unique identifier of the item.
        split: The split of the item.
        created_at: The creation date of the item.
        updated_at: The last modification date of the item.
    """

    id: str
    split: str = "default"
    created_at: datetime
    updated_at: datetime

    def __init__(self, /, created_at: datetime | None = None, updated_at: datetime | None = None, **data: Any) -> None:
        """Create a new model by parsing and validating input data from keyword arguments.

        Raises [`ValidationError`][pydantic_core.ValidationError] if the input data cannot be
        validated to form a valid model.

        `self` is explicitly positional-only to allow `self` as a field name.

        Args:
            created_at: The creation date of the object.
            updated_at: The last modification date of the object.
            data: The data of the object validated by Pydantic.
        """
        created_at, updated_at = validate_and_init_create_at_and_update_at(created_at, updated_at)
        data.update({"created_at": created_at, "updated_at": updated_at})
        super().__init__(**data)

    def to_schemas_data(self, dataset_schema: DatasetSchema) -> dict[str, BaseSchema | list[BaseSchema] | None]:
        """Convert DatasetItem to schemas data.

        Args:
            dataset_schema: DatasetSchema to convert to.

        Returns:
            Schemas data.
        """
        schemas_data = {}
        item_data = {}
        for field_name in self.model_fields.keys():
            if field_name in dataset_schema.schemas:
                schemas_data[field_name] = getattr(self, field_name)
            else:
                item_data[field_name] = getattr(self, field_name)
        schemas_data[SchemaGroup.ITEM.value] = dataset_schema.schemas[SchemaGroup.ITEM.value](**item_data)
        return schemas_data

    @staticmethod
    def from_schemas_data(
        cls: "DatasetItem", schemas_data: dict[str, BaseSchema | list[BaseSchema] | None]
    ) -> "DatasetItem":
        """Create a DatasetItem from schemas data.

        Args:
            cls: The DatasetItem class.
            schemas_data: Schemas data.

        Returns:
            The created DatasetItem.
        """
        if SchemaGroup.ITEM.value not in schemas_data:
            raise ValueError("Item schema data not found.")

        schemas_data.update(schemas_data.pop(SchemaGroup.ITEM.value).model_dump())  # type: ignore[union-attr]
        return cls(**schemas_data)

    def model_dump(self, exclude_timestamps: bool = False, **kwargs: Any) -> dict[str, Any]:
        """Dump the model to a dictionary.

        Args:
            exclude_timestamps: Exclude timestamps "created_at" and "updated_at" from the model dump. Useful for
                comparing models without timestamps.
            kwargs: Arguments for pydantic `BaseModel.model_dump()`.

        Returns:
            The model dump.
        """
        model_dump = super().model_dump(**kwargs)
        if exclude_timestamps:
            model_dump.pop("created_at", None)
            model_dump.pop("updated_at", None)
            for k, value in model_dump.items():
                if isinstance(value, dict):
                    value.pop("created_at", None)
                    value.pop("updated_at", None)
                elif isinstance(value, list):  # Only one level deep.
                    for item in value:
                        if isinstance(item, dict):
                            item.pop("created_at", None)
                            item.pop("updated_at", None)
        return model_dump

    def model_copy(self, *, dataset: "Dataset", deep: bool = False) -> Self:
        """Returns a copy of the model.

        Args:
            dataset: The dataset where the DatasetItem belongs.
            deep: Set to `True` to make a deep copy of the model.

        Returns:
            New model instance.
        """
        # Actual copy done by each schema to call our own model_copy method
        data: dict[str, BaseSchema | list[BaseSchema] | None] = self.to_schemas_data(dataset.schema)
        copied_data: dict[str, BaseSchema | list[BaseSchema] | None] = {}
        for key, value in data.items():
            if isinstance(value, list):
                copied_data[key] = [item.model_copy(deep=deep) for item in value]
            elif value is not None:
                copied_data[key] = value.model_copy(deep=deep)
            else:
                copied_data[key] = None
        copy_item = self.from_schemas_data(self.__class__, copied_data)  # type: ignore[arg-type]
        return copy_item

    @classmethod
    def to_dataset_schema(cls) -> DatasetSchema:
        """Convert a DatasetItem to a DatasetSchema."""
        return DatasetSchema.from_dataset_item(cls)

    @staticmethod
    def from_dataset_schema(dataset_schema: DatasetSchema, exclude_embeddings: bool = True) -> type["DatasetItem"]:
        """Create a dataset item model based on the schema.

        Args:
            dataset_schema: The dataset schema.
            exclude_embeddings: Exclude embeddings from the dataset item model to reduce the size.

        Returns:
            The dataset item model
        """
        item_type = dataset_schema.schemas[SchemaGroup.ITEM.value]
        fields: dict[str, Any] = {}

        if dataset_schema.relations != {} and SchemaGroup.ITEM.value in dataset_schema.relations:
            for schema, relation in dataset_schema.relations[SchemaGroup.ITEM.value].items():
                if exclude_embeddings and schema in dataset_schema.groups[SchemaGroup.EMBEDDING]:
                    continue
                # Add default value in case an item does not have a specific view or entity.
                schema_type = dataset_schema.schemas[schema]
                if relation == SchemaRelation.ONE_TO_MANY:
                    fields[schema] = (list[schema_type], [])  # type: ignore[valid-type]
                else:
                    fields[schema] = (schema_type | None, None)

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
    def get_sub_dataset_item(cls, selected_fields: list[str]) -> type[Self]:
        """Create a new dataset item based on the selected fields of the original dataset
        item.

        Note:
            The id and split fields are always included in the sub dataset item.

        Note:
            The sub dataset item does not have the methods and config of the original
            dataset item.

        Args:
            selected_fields: The selected fields.

        Returns:
            The sub dataset item.
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
