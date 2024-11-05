# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import warnings
from enum import Enum
from types import GenericAlias
from typing import Any, Literal, cast

import shortuuid
from lancedb.pydantic import LanceModel
from pydantic import create_model
from typing_extensions import TYPE_CHECKING

from pixano.datasets.queries import TableQueryBuilder
from pixano.datasets.utils.errors import DatasetIntegrityError
from pixano.features import (
    AnnotationRef,
    BaseSchema,
    EmbeddingRef,
    EntityRef,
    SchemaGroup,
    SchemaRef,
    Source,
    ViewRef,
    is_annotation_ref,
    is_embedding_ref,
    is_entity_ref,
    is_item_ref,
    is_schema_ref,
    is_source_ref,
    is_view_ref,
)


if TYPE_CHECKING:
    from pixano.datasets import Dataset


class IntegrityCheck(Enum):
    """Integrity check types.

    Attributes:
        DEFINED_ID: Check if the id field is defined.
        UNIQUE_ID: Check if the id field is unique.
        REF_NAME: Check if the ref name is defined in the schema.
        REF_TYPE: Check if the ref type is defined in the schema.
        REF_ID: Check if the ref id is stored in the referenced table.
    """

    DEFINED_ID = 0
    UNIQUE_ID = 1
    REF_NAME = 2
    REF_TYPE = 3
    REF_ID = 4


def get_integry_checks_from_schemas(
    schemas: list[BaseSchema], table_name: str
) -> list[list[tuple[str, str, str, str, Any]]]:
    """Get the integrity checks to perform on a table.

    Args:
        schemas: List of schemas to check.
        table_name: Table name.

    Returns:
        List of integrity checks to perform on the table. The checks are grouped by type.
        - check_id: Check id (unique identifier for the checks). It is used to avoid checking subsequent checks with
            the same id when an error is found.
        - table: Table name.
        - schema_id: Schema id which is the id field value from the schema.
        - field_name: Field name to check.
        - field: Field value to check.
    """
    checks: list[list[tuple[str, str, str, str, Any]]] = [[] for _ in IntegrityCheck]
    for schema in schemas:
        schema_id = schema.id
        check_id = shortuuid.uuid()
        checks[IntegrityCheck.DEFINED_ID.value].append((check_id, table_name, schema_id, "id", schema_id))
        checks[IntegrityCheck.UNIQUE_ID.value].append((check_id, table_name, schema_id, "id", schema_id))
        for field_name, field in schema.model_fields.items():
            if field_name == "id":
                continue
            if isinstance(field.annotation, GenericAlias):
                continue
            type_field = field.annotation
            if is_schema_ref(type_field):
                checks[IntegrityCheck.REF_NAME.value].append(
                    (check_id, table_name, schema_id, field_name, getattr(schema, field_name))
                )
                checks[IntegrityCheck.REF_TYPE.value].append(
                    (check_id, table_name, schema_id, field_name, getattr(schema, field_name))
                )
                checks[IntegrityCheck.REF_ID.value].append(
                    (check_id, table_name, schema_id, field_name, getattr(schema, field_name))
                )

    return checks


def check_table_integrity(
    table_name: str,
    dataset: "Dataset",
    schemas: list[BaseSchema] | None = None,
    updating: bool = False,
    ignore_checks: list[IntegrityCheck] | None = None,
) -> list[tuple[IntegrityCheck, str, str, str, Any]]:
    """Check the integrity of schemas against a table.

    Args:
        table_name: Table name.
        dataset: Dataset that contains the table.
        schemas: List of schemas to insert in table. If None, the table is checked, otherwise the schemas are checked
            against the table.
        updating: If True, the table is being updated. It is used to avoid checking the id uniqueness when updating
            schemas.
        ignore_checks: List of integrity checks to ignore.

    Returns:
        List of errors as tuples with the following values:
        - check_type: Check type.
        - table: Table name.
        - field_name: Field name that caused the error.
        - schema_id: Schema id that raised the error.
        - field: Field value that caused the error.
    """
    table = dataset.open_table(table_name)

    if ignore_checks is not None:
        ignore_checks_set: set[IntegrityCheck] = {IntegrityCheck(check) for check in ignore_checks}
    else:
        ignore_checks_set = set()
    table_schema = Source if table_name == "source" else dataset.schema.schemas[table_name]

    checking_table = schemas is None
    if schemas is None:
        if updating:
            raise ValueError("schemas must be provided when updating a table.")
        table_schema = cast(BaseSchema, table_schema)
        fields_to_check = ["id"] + [
            field_name
            for field_name, field in table_schema.model_fields.items()
            if field_name != "id"
            and not isinstance(field.annotation, GenericAlias)
            and is_schema_ref(field.annotation)
        ]
        model = create_model(
            "_Schema",
            __base__=LanceModel,
            **{field_name: (table_schema.model_fields[field_name].annotation, ...) for field_name in fields_to_check},
        )
        schemas = TableQueryBuilder(table).select(fields_to_check).to_pydantic(model)

    table_ids = [schema.id for schema in schemas]
    count_ids: dict[str, int] = {}
    for id in table_ids:
        count_ids[id] = count_ids.get(id, 0) + 1
    integrity_checks = get_integry_checks_from_schemas(schemas, table_name)
    check_errors: dict[str, tuple[IntegrityCheck, str, str, str, Any]] = {}
    ids_to_check: dict[str, str] = {}
    schemas_refs_to_check: dict[str, list[tuple[str, str, SchemaRef, str]]] = {}

    for check_type_id, checks in enumerate(integrity_checks):
        check_type = IntegrityCheck(check_type_id)
        if check_type in ignore_checks_set:
            continue
        for check_id, _, schema_id, field_name, field in checks:
            if check_id in check_errors:
                continue
            if check_type == IntegrityCheck.DEFINED_ID and field == "":  # id is not defined
                check_errors[check_id] = (check_type, table_name, field_name, schema_id, field)
            elif check_type == IntegrityCheck.UNIQUE_ID:
                if count_ids[schema_id] > 1:  # id is not unique
                    check_errors[check_id] = (check_type, table_name, field_name, schema_id, field)
                elif not checking_table:
                    ids_to_check[schema_id] = check_id
            elif check_type == IntegrityCheck.REF_NAME:
                field = cast(SchemaRef, field)
                if field.name != "" and field.name not in (
                    list(dataset.schema.schemas.keys()) + ["source"]
                ):  # ref name is not defined
                    check_errors[check_id] = (check_type, table_name, field_name, schema_id, field)
            elif check_type == IntegrityCheck.REF_TYPE:
                field = cast(SchemaRef, field)
                if field.name == "":
                    continue
                field_type = type(field)
                if is_view_ref(field_type):  # field is a view ref
                    field = cast(ViewRef, field)
                    if field.name not in dataset.schema.groups[SchemaGroup.VIEW]:  # field name is not a view
                        check_errors[check_id] = (check_type, table_name, field_name, schema_id, field)
                elif is_annotation_ref(field_type):  # field is an annotation ref
                    field = cast(AnnotationRef, field)
                    if (
                        field.name not in dataset.schema.groups[SchemaGroup.ANNOTATION]
                    ):  # field name is not an annotation
                        check_errors[check_id] = (check_type, table_name, field_name, schema_id, field)
                elif is_embedding_ref(field_type):  # field is an embedding ref
                    field = cast(EmbeddingRef, field)
                    if (
                        field.name not in dataset.schema.groups[SchemaGroup.EMBEDDING]
                    ):  # field name is not an embedding
                        check_errors[check_id] = (check_type, table_name, field_name, schema_id, field)
                elif is_entity_ref(field_type):  # field is an entity ref
                    field = cast(EntityRef, field)
                    if field.name not in dataset.schema.groups[SchemaGroup.ENTITY]:  # field name is not an entity
                        check_errors[check_id] = (check_type, table_name, field_name, schema_id, field)
                elif is_item_ref(field_type) or is_source_ref(field_type):
                    pass  # item_ref and source_ref are validated before.
            elif check_type == IntegrityCheck.REF_ID:  # ref id and ref item relation checked below
                field = cast(SchemaRef, field)
                if field_name == "":
                    continue
                # If the field is empty, the reference is to the table itself so no need to check
                if field.id == "":
                    continue
                if field.name not in schemas_refs_to_check:
                    schemas_refs_to_check[field.name] = []
                schemas_refs_to_check[field.name].append((check_id, schema_id, field, field_name))

    if not checking_table and not updating and len(ids_to_check) > 0:
        for id, found in dataset.find_ids_in_table(table_name, set(ids_to_check.keys())).items():
            if found:
                check_errors[ids_to_check[id]] = (IntegrityCheck.UNIQUE_ID, table_name, "id", id, id)

    if len(check_errors) == len(
        {check_id for check_id, *_ in integrity_checks[IntegrityCheck.REF_ID.value]}
    ):  # all checks failed, no need to check later checks that are costly
        return list(check_errors.values())

    for ref_schema_name, refs in schemas_refs_to_check.items():
        if ref_schema_name == "":
            continue
        ref_ids_to_check = {field_ref.id for check_id, _, field_ref, _ in refs if check_id not in check_errors}
        found_ref_ids = dataset.find_ids_in_table(ref_schema_name, ref_ids_to_check)
        for check_id, schema_id, field_ref, field_name in refs:
            if check_id in check_errors:
                continue
            if not found_ref_ids[field_ref.id]:
                check_errors[check_id] = (
                    IntegrityCheck.REF_ID,
                    table_name,
                    field_name,
                    schema_id,
                    field_ref,
                )

    return list(check_errors.values())


def check_dataset_integrity(dataset: "Dataset") -> list[tuple[IntegrityCheck, str, str, str, Any]]:
    """Check the integrity of a dataset.

    Args:
        dataset: Dataset to check.

    Returns:
        List of errors as tuples with the following values:
        - check_type: Check type.
        - table: Table name.
        - field_name: Field name that caused the error.
        - schema_id: Schema id that raised the error.
        - field: Field value that caused the error.
    """
    check_errors: list[tuple[IntegrityCheck, str, str, str, Any]] = []
    for table_name in dataset.schema.schemas.keys():
        check_errors.extend(check_table_integrity(table_name, dataset))
    return check_errors


def handle_integrity_errors(
    check_errors: list[tuple[IntegrityCheck, str, str, str, Any]],
    raise_or_warn: Literal["raise", "warn"] = "raise",
) -> None:
    """Handle integrity check errors.

    Args:
        check_errors: List of errors.
        raise_or_warn: If "raise", raise a ValueError with the errors. If "warn", warns a UserWarning with the errors.
    """
    if len(check_errors) == 0:
        return
    message = "Integrity check errors:\n"
    for check_type, table_name, field_name, schema_id, field in check_errors:
        message += "- "
        if check_type == IntegrityCheck.DEFINED_ID:
            message += f"An id is not defined in table {table_name}.\n"
        elif check_type == IntegrityCheck.UNIQUE_ID:
            message += f"The id {schema_id} is not unique in table {table_name}.\n"
        elif check_type == IntegrityCheck.REF_NAME:
            message += f"The reference {field_name} from {schema_id} to the table {field.name} does not exist.\n"
        elif check_type == IntegrityCheck.REF_TYPE:
            message += (
                f"The reference {field_name} from {schema_id} to the table {field.name} is to an invalid type. "
                f"Got {type(field)}.\n"
            )
        elif check_type == IntegrityCheck.REF_ID:
            message += (
                f"The reference {field_name} from {schema_id} to the table {field.name} has an invalid id. Got "
                f"{field.id}.\n"
            )
    if raise_or_warn == "raise":
        raise DatasetIntegrityError(message)
    else:
        warnings.warn(message, category=UserWarning)
