# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Generic CRUD service for the API."""

from typing import Any

from fastapi import HTTPException
from lancedb.pydantic import LanceModel
from pydantic import BaseModel

from pixano.datasets import Dataset
from pixano.datasets.utils import DatasetAccessError, DatasetPaginationError
from pixano.datasets.utils.errors import DatasetIntegrityError
from pixano.schemas import SchemaGroup, View

from .models import PaginatedResponse, merge_update_payload, serialize_row
from .resources import ResourceSpec


MAX_QUERY_LIMIT = 1000


class BaseService:
    """Shared CRUD operations for API resources."""

    def __init__(self, dataset: Dataset, resource: ResourceSpec):
        """Initialize the service with a dataset and resource spec."""
        self.dataset = dataset
        self.resource = resource

    def resolve_table(self) -> str:
        """Resolve the backing table for this resource."""
        resolved_table = self.resource.canonical_table_name
        schema_type = self.dataset.info.tables.get(resolved_table)
        if schema_type is None:
            raise HTTPException(status_code=404, detail=f"No table found for resource '{self.resource.path}'.")
        if not issubclass(schema_type, self.resource.schema_cls):
            raise HTTPException(
                status_code=500,
                detail=(
                    f"Dataset integrity error: table '{resolved_table}' uses schema {schema_type.__name__}, "
                    f"expected subclass of {self.resource.schema_cls.__name__}."
                ),
            )
        return resolved_table

    def validate_fk_exists(self, table: str, fk_id: str, label: str) -> None:
        """Ensure a foreign key target exists."""
        if not fk_id:
            return
        row = self.dataset.get_data(table, ids=fk_id)
        if row is None:
            raise HTTPException(
                status_code=400,
                detail=f"Foreign key violation: {label}='{fk_id}' not found in '{table}'.",
            )

    def validate_record_exists(self, record_id: str) -> None:
        """Validate that the referenced record exists."""
        self.validate_fk_exists(SchemaGroup.RECORD.value, record_id, "record_id")

    def validate_entity_exists(self, entity_id: str) -> str | None:
        """Validate that the referenced entity exists and return its table name."""
        if not entity_id:
            return None
        tables = self.dataset.info.groups.get(SchemaGroup.ENTITY, [])
        for table in tables:
            row = self.dataset.get_data(table, ids=entity_id)
            if row is not None:
                return table
        raise HTTPException(
            status_code=400,
            detail=f"Foreign key violation: entity_id='{entity_id}' not found in any entity table.",
        )

    def validate_tracklet_exists(self, tracklet_id: str, expected_entity_id: str | None = None) -> None:
        """Validate that the referenced tracklet exists and belongs to the expected entity."""
        if not tracklet_id:
            return
        tables = self.dataset.info.groups.get(SchemaGroup.ANNOTATION, [])
        for table in tables:
            row = self.dataset.get_data(table, ids=tracklet_id)
            if row is None:
                continue
            if expected_entity_id and hasattr(row, "entity_id") and row.entity_id != expected_entity_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cross-entity check failed: tracklet '{tracklet_id}' belongs to "
                        f"entity '{row.entity_id}', not '{expected_entity_id}'."
                    ),
                )
            return
        raise HTTPException(status_code=400, detail=f"Foreign key violation: tracklet_id='{tracklet_id}' not found.")

    def validate_eds_exists(self, eds_id: str, expected_entity_id: str | None = None) -> None:
        """Validate that the referenced entity dynamic state exists."""
        if not eds_id:
            return
        tables = self.dataset.info.groups.get(SchemaGroup.ENTITY_DYNAMIC_STATE, [])
        for table in tables:
            row = self.dataset.get_data(table, ids=eds_id)
            if row is None:
                continue
            if expected_entity_id and hasattr(row, "entity_id") and row.entity_id != expected_entity_id:
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Cross-entity check failed: EDS '{eds_id}' belongs to "
                        f"entity '{row.entity_id}', not '{expected_entity_id}'."
                    ),
                )
            return
        raise HTTPException(
            status_code=400,
            detail=f"Foreign key violation: entity_dynamic_state_id='{eds_id}' not found.",
        )

    def _response(self, row: LanceModel) -> BaseModel:
        payload = serialize_row(row, exclude_fields=self.resource.response_exclude_fields)
        return self.resource.response_model.model_validate(payload)

    def list(
        self,
        record_id: str | None = None,
        entity_id: str | None = None,
        view_name: str | None = None,
        source_type: str | None = None,
        tracklet_id: str | None = None,
        frame_index: int | None = None,
        where: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> PaginatedResponse:
        """List resources with filtering and pagination."""
        resolved_table = self.resolve_table()
        limit = min(limit, MAX_QUERY_LIMIT)

        clauses = []
        if record_id:
            clauses.append(f"record_id = '{record_id}'")
        if entity_id:
            clauses.append(f"entity_id = '{entity_id}'")
        if view_name:
            view_field = "logical_name" if issubclass(self.resource.schema_cls, View) else "view_id"
            clauses.append(f"{view_field} = '{view_name}'")
        if source_type:
            clauses.append(f"source_type = '{source_type}'")
        if tracklet_id:
            clauses.append(f"tracklet_id = '{tracklet_id}'")
        if frame_index is not None:
            clauses.append(f"frame_index = {frame_index}")
        if where:
            clauses.append(f"({where})")
        combined_where = " AND ".join(clauses) if clauses else None

        try:
            lance_table = self.dataset.open_table(resolved_table)
            total = lance_table.count_rows(combined_where) if combined_where else lance_table.count_rows()
            rows = self.dataset.get_data(
                table_name=resolved_table,
                where=combined_where,
                limit=limit,
                skip=offset,
            )
        except DatasetPaginationError as err:
            raise HTTPException(status_code=400, detail=f"Invalid query parameters. {err}")
        except DatasetAccessError as err:
            raise HTTPException(status_code=500, detail=f"Internal server error. {err}")

        items = [self._response(row) for row in (rows or [])]
        return PaginatedResponse(items=items, total=total, limit=limit, offset=offset)

    def get(self, id: str) -> BaseModel:
        """Fetch one resource by ID."""
        resolved_table = self.resolve_table()
        row = self.dataset.get_data(resolved_table, ids=id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Resource '{id}' not found in '{resolved_table}'.")
        return self._response(row)

    def create(self, data: dict[str, Any]) -> BaseModel:
        """Create a new resource row."""
        resolved_table = self.resolve_table()
        payload = dict(data)

        if self.resource.validate_create is not None:
            self.resource.validate_create(self, payload)

        schema = self.dataset.info.tables[resolved_table]
        try:
            row = schema.model_validate(payload)
        except Exception as err:
            raise HTTPException(status_code=400, detail=f"Invalid data: {err}")

        try:
            created_rows = self.dataset.add_data(resolved_table, [row])
        except DatasetIntegrityError as err:
            raise HTTPException(status_code=400, detail=f"Integrity error: {err}")
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid data: {err}")

        return self._response(created_rows[0])

    def update(self, id: str, data: dict[str, Any]) -> BaseModel:
        """Update an existing resource row."""
        resolved_table = self.resolve_table()
        existing = self.dataset.get_data(resolved_table, ids=id)
        if existing is None:
            raise HTTPException(status_code=404, detail=f"Resource '{id}' not found in '{resolved_table}'.")

        merged = merge_update_payload(existing, data)
        schema = self.dataset.info.tables[resolved_table]
        try:
            row = schema.model_validate(merged)
        except Exception as err:
            raise HTTPException(status_code=400, detail=f"Invalid data: {err}")

        try:
            updated_rows = self.dataset.update_data(resolved_table, [row])
        except DatasetIntegrityError as err:
            raise HTTPException(status_code=400, detail=f"Integrity error: {err}")
        except ValueError as err:
            raise HTTPException(status_code=400, detail=f"Invalid data: {err}")

        return self._response(updated_rows[0])

    def delete(self, id: str) -> None:
        """Delete a resource by ID."""
        resolved_table = self.resolve_table()
        ids_not_found = self.dataset.delete_data(resolved_table, [id])
        if ids_not_found:
            raise HTTPException(status_code=404, detail=f"Resource '{id}' not found in '{resolved_table}'.")


__all__ = ["BaseService"]
