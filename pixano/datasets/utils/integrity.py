# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import warnings
from enum import Enum
from typing import TYPE_CHECKING, Any

from pixano.datasets.utils.errors import DatasetIntegrityError
from pixano.features import SchemaGroup


if TYPE_CHECKING:
    from pixano.datasets import Dataset
    from pixano.features import BaseSchema


class IntegrityCheck(Enum):
    """Integrity check types."""

    DEFINED_ID = 0
    UNIQUE_ID = 1
    FK_ID = 2


def _table_group(dataset: "Dataset", table_name: str) -> SchemaGroup | None:
    for group, tables in dataset.schema.groups.items():
        if table_name in tables:
            return group
    return None


def _resolve_fk_target_tables(dataset: "Dataset", table_name: str, field_name: str) -> list[str]:
    """Resolve candidate target tables for a `*_id` foreign key field."""
    if field_name == "item_id":
        return [SchemaGroup.ITEM.value]
    if field_name == "source_id":
        return [SchemaGroup.SOURCE.value]
    if field_name == "entity_id":
        return list(dataset.schema.groups.get(SchemaGroup.ENTITY, set()))
    if field_name == "entity_dynamic_state_id":
        return list(dataset.schema.groups.get(SchemaGroup.ENTITY_DYNAMIC_STATE, set()))
    if field_name == "tracklet_id":
        return [
            t for t in dataset.schema.groups.get(SchemaGroup.ANNOTATION, set()) if "tracklet" in t
        ]
    if field_name == "frame_id":
        return list(dataset.schema.groups.get(SchemaGroup.VIEW, set()))
    if field_name in {"subject_id", "object_id"}:
        return list(dataset.schema.groups.get(SchemaGroup.ANNOTATION, set()))
    if field_name == "parent_id":
        group = _table_group(dataset, table_name)
        if group == SchemaGroup.ENTITY:
            return list(dataset.schema.groups.get(SchemaGroup.ENTITY, set()))
        if group == SchemaGroup.VIEW:
            return list(dataset.schema.groups.get(SchemaGroup.VIEW, set()))
        return []

    # Generic fallback: <prefix>_id -> table named <prefix> or <prefix>s
    prefix = field_name[:-3] if field_name.endswith("_id") else field_name
    candidates: list[str] = []
    if prefix in dataset.schema.schemas:
        candidates.append(prefix)
    plural = f"{prefix}s"
    if plural in dataset.schema.schemas:
        candidates.append(plural)
    return candidates


def _schema_id_fields(schema: "BaseSchema") -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for field_name in schema.model_fields:
        if field_name != "id" and field_name.endswith("_id"):
            value = getattr(schema, field_name, "")
            if isinstance(value, str):
                fields.append((field_name, value))
    return fields


def get_integry_checks_from_schemas(
    schemas: list["BaseSchema"], table_name: str
) -> list[list[tuple[str, str, str, str, Any]]]:
    """Expose normalized check candidates grouped by check type."""
    checks: list[list[tuple[str, str, str, str, Any]]] = [[] for _ in IntegrityCheck]
    for schema in schemas:
        checks[IntegrityCheck.DEFINED_ID.value].append((schema.id, table_name, schema.id, "id", schema.id))
        checks[IntegrityCheck.UNIQUE_ID.value].append((schema.id, table_name, schema.id, "id", schema.id))
        for field_name, field_value in _schema_id_fields(schema):
            checks[IntegrityCheck.FK_ID.value].append((schema.id, table_name, schema.id, field_name, field_value))
    return checks


def check_table_integrity(
    table_name: str,
    dataset: "Dataset",
    schemas: list["BaseSchema"] | None = None,
    updating: bool = False,
    ignore_checks: list[IntegrityCheck] | None = None,
) -> list[tuple[IntegrityCheck, str, str, str, Any]]:
    """Check table-level integrity against ID and FK constraints."""

    ignore = set(ignore_checks or [])
    schema_type = dataset.schema.schemas.get(table_name)
    if schema_type is None:
        if table_name == SchemaGroup.SOURCE.value:
            return []
        raise ValueError(f"Unknown table '{table_name}'.")

    if schemas is None:
        validating_existing_rows = True
        schemas = dataset.get_data(table_name, limit=dataset.open_table(table_name).count_rows())
    else:
        validating_existing_rows = False

    errors: list[tuple[IntegrityCheck, str, str, str, Any]] = []

    # ID checks
    id_counts: dict[str, int] = {}
    for schema in schemas:
        schema_id = schema.id
        if IntegrityCheck.DEFINED_ID not in ignore and schema_id == "":
            errors.append((IntegrityCheck.DEFINED_ID, table_name, "id", schema_id, schema_id))
        id_counts[schema_id] = id_counts.get(schema_id, 0) + 1

    if IntegrityCheck.UNIQUE_ID not in ignore:
        for schema_id, count in id_counts.items():
            if schema_id != "" and count > 1:
                errors.append((IntegrityCheck.UNIQUE_ID, table_name, "id", schema_id, schema_id))

        # Check against existing table IDs only when validating incoming rows.
        if not updating and not validating_existing_rows and schemas and table_name in dataset.schema.schemas:
            incoming_ids = {schema.id for schema in schemas if schema.id}
            found = dataset.find_ids_in_table(table_name, incoming_ids)
            for schema in schemas:
                if schema.id and found.get(schema.id, False):
                    errors.append((IntegrityCheck.UNIQUE_ID, table_name, "id", schema.id, schema.id))

    # FK checks
    if IntegrityCheck.FK_ID in ignore:
        return errors

    for schema in schemas:
        for field_name, field_value in _schema_id_fields(schema):
            if field_value == "":
                continue
            target_tables = _resolve_fk_target_tables(dataset, table_name, field_name)
            if not target_tables:
                continue

            found = False
            for target_table in target_tables:
                try:
                    if dataset.find_ids_in_table(target_table, {field_value}).get(field_value, False):
                        found = True
                        break
                except Exception:
                    continue

            if not found:
                errors.append((IntegrityCheck.FK_ID, table_name, field_name, schema.id, field_value))

    return errors


def check_dataset_integrity(dataset: "Dataset") -> list[tuple[IntegrityCheck, str, str, str, Any]]:
    """Check integrity for all dataset tables."""
    check_errors: list[tuple[IntegrityCheck, str, str, str, Any]] = []
    for table_name in dataset.schema.schemas.keys():
        check_errors.extend(check_table_integrity(table_name, dataset))
    return check_errors


def handle_integrity_errors(
    check_errors: list[tuple[IntegrityCheck, str, str, str, Any]],
    raise_or_warn: str = "raise",
) -> None:
    """Handle integrity check errors."""
    if len(check_errors) == 0:
        return

    message = "Integrity check errors:\n"
    for check_type, table_name, field_name, schema_id, field in check_errors:
        if check_type == IntegrityCheck.DEFINED_ID:
            message += f"- Missing id in table '{table_name}'.\n"
        elif check_type == IntegrityCheck.UNIQUE_ID:
            message += f"- Duplicate id '{schema_id}' in table '{table_name}'.\n"
        elif check_type == IntegrityCheck.FK_ID:
            message += (
                f"- Invalid foreign key '{field_name}'='{field}' in table '{table_name}' for row '{schema_id}'.\n"
            )

    if raise_or_warn == "raise":
        raise DatasetIntegrityError(message)
    warnings.warn(message, category=UserWarning)
