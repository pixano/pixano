# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import warnings
from enum import Enum
from typing import TYPE_CHECKING, Any, Literal

from pixano.datasets.utils.errors import DatasetIntegrityError
from pixano.schemas import SchemaGroup, canonical_table_name_for_slot


if TYPE_CHECKING:
    from pixano.datasets import Dataset
    from lancedb.pydantic import LanceModel


class IntegrityCheck(Enum):
    """Integrity check types."""

    DEFINED_ID = 0
    UNIQUE_ID = 1
    FK_ID = 2


def _table_group(dataset: "Dataset", table_name: str) -> SchemaGroup | None:
    for group, tables in dataset.info.groups.items():
        if table_name in tables:
            return group
    return None


def _resolve_fk_target_tables(dataset: "Dataset", table_name: str, field_name: str) -> list[str]:
    """Resolve candidate target tables for a `*_id` foreign key field."""
    if field_name == "record_id":
        return [SchemaGroup.RECORD.value]
    if field_name == "entity_id":
        return [canonical_table_name_for_slot("entity")]
    if field_name == "entity_dynamic_state_id":
        return [canonical_table_name_for_slot("entity_dynamic_state")]
    if field_name == "tracklet_id":
        return [canonical_table_name_for_slot("tracklet")]
    if field_name == "frame_id":
        return list(dataset.info.groups.get(SchemaGroup.VIEW, set()))
    if field_name in {"subject_id", "object_id"}:
        return list(dataset.info.groups.get(SchemaGroup.ANNOTATION, set()))
    if field_name == "parent_id":
        group = _table_group(dataset, table_name)
        if group == SchemaGroup.ENTITY:
            return list(dataset.info.groups.get(SchemaGroup.ENTITY, set()))
        if group == SchemaGroup.VIEW:
            return list(dataset.info.groups.get(SchemaGroup.VIEW, set()))
        return []
    return []


def _schema_id_fields(schema: "LanceModel") -> list[tuple[str, str]]:
    fields: list[tuple[str, str]] = []
    for field_name in type(schema).model_fields:
        if field_name != "id" and field_name.endswith("_id"):
            value = getattr(schema, field_name, "")
            if isinstance(value, str):
                fields.append((field_name, value))
    return fields


def get_integry_checks_from_schemas(
    schemas: list["LanceModel"], table_name: str
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
    schemas: list["LanceModel"] | None = None,
    updating: bool = False,
    ignore_checks: list[IntegrityCheck] | None = None,
) -> list[tuple[IntegrityCheck, str, str, str, Any]]:
    """Check table-level integrity against ID and FK constraints."""

    ignore = set(ignore_checks or [])
    schema_type = dataset.info.tables.get(table_name)
    if schema_type is None:
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
        if not updating and not validating_existing_rows and schemas and table_name in dataset.info.tables:
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
    for table_name in dataset.info.tables.keys():
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


def validate_batch(
    table_name: str,
    schemas: list["LanceModel"],
    known_ids: dict[str, set[str]],
    dataset: "Dataset",
    raise_or_warn: Literal["raise", "warn", "none"] = "raise",
    pending_ids: dict[str, set[str]] | None = None,
) -> None:
    """Validate a batch of schemas before insertion using in-memory ID tracking.

    Instead of per-row DB queries, this checks IDs in-memory and does at most one
    bulk DB query per FK target table per batch.

    Args:
        table_name: The table the batch will be inserted into.
        schemas: The batch of schema instances to validate.
        known_ids: Mapping of table_name -> set of known IDs (accumulated across flushes).
        dataset: The dataset (used for bulk FK lookups against already-flushed data).
        raise_or_warn: How to handle errors: "raise", "warn", or "none".
        pending_ids: Mapping of table_name -> set of IDs that are buffered for insertion
            in this flush cycle. Used only for FK checks so sibling tables that haven't
            been flushed yet can be resolved.
    """
    errors: list[tuple[IntegrityCheck, str, str, str, Any]] = []

    # DEFINED_ID + UNIQUE_ID checks
    batch_ids: set[str] = set()
    for schema in schemas:
        if schema.id == "":
            errors.append((IntegrityCheck.DEFINED_ID, table_name, "id", schema.id, schema.id))
        elif schema.id in batch_ids or schema.id in known_ids.get(table_name, set()):
            errors.append((IntegrityCheck.UNIQUE_ID, table_name, "id", schema.id, schema.id))
        else:
            batch_ids.add(schema.id)

    # FK_ID checks: collect all FK values per target table, then bulk-query
    # Build mapping: target_table -> set of FK values to check
    fk_values_by_target: dict[str, set[str]] = {}
    # Track which (schema_id, field_name, fk_value, target_tables) need checking
    fk_lookups: list[tuple[str, str, str, list[str]]] = []

    for schema in schemas:
        for field_name, field_value in _schema_id_fields(schema):
            if field_value == "":
                continue
            target_tables = _resolve_fk_target_tables(dataset, table_name, field_name)
            if not target_tables:
                continue
            # Check in-memory first
            found_in_memory = any(
                field_value in known_ids.get(t, set()) or field_value in (pending_ids or {}).get(t, set())
                for t in target_tables
            )
            if not found_in_memory:
                fk_lookups.append((schema.id, field_name, field_value, target_tables))
                for t in target_tables:
                    fk_values_by_target.setdefault(t, set()).add(field_value)

    # Bulk DB queries: one per target table
    db_found: dict[str, set[str]] = {}
    for target_table, values in fk_values_by_target.items():
        try:
            result = dataset.find_ids_in_table(target_table, values)
            db_found[target_table] = {v for v, found in result.items() if found}
        except Exception:
            db_found[target_table] = set()

    # Resolve FK lookups
    for schema_id, field_name, field_value, target_tables in fk_lookups:
        found = any(field_value in db_found.get(t, set()) for t in target_tables)
        if not found:
            errors.append((IntegrityCheck.FK_ID, table_name, field_name, schema_id, field_value))

    handle_integrity_errors(errors, raise_or_warn=raise_or_warn)
