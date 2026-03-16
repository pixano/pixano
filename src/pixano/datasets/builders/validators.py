# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

from collections import defaultdict

from lancedb.pydantic import LanceModel

from pixano.datasets import Dataset
from pixano.datasets.utils.errors import DatasetIntegrityError
from pixano.schemas import View, canonical_table_name_for_schema, is_image, is_sequence_frame


class ViewFamilyIntegrityValidator:
    """Reject mixed image and sequence-frame families for one logical view."""

    def __init__(self, schemas: dict[str, type[LanceModel]]) -> None:
        """Initialize the validator with the dataset table schemas."""
        self.schemas = schemas

    def validate(self, batch: dict[str, list[LanceModel]], dataset: Dataset) -> None:
        """Validate one buffered batch before insertion."""
        families_by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)

        for table_name, rows in batch.items():
            schema = self.schemas.get(table_name)
            if schema is None or not issubclass(schema, View):
                continue

            for row in rows:
                family = self._preview_view_family(type(row))
                if family is None:
                    continue
                pair = (getattr(row, "record_id", ""), getattr(row, "logical_name", ""))
                families_by_pair[pair].add(family)

        for pair, families in list(families_by_pair.items()):
            if len(families) > 1:
                self._raise_mixed_view_family_error(pair[0], pair[1], families)

            record_id, logical_name = pair
            if not record_id or not logical_name:
                continue

            current_family = next(iter(families)) if families else None
            if current_family is None:
                continue

            conflicting_table = "sequence_frames" if current_family == "images" else "images"
            conflicting_schema = dataset.info.tables.get(conflicting_table)
            if conflicting_schema is None:
                continue

            where = f"record_id = '{record_id}' AND logical_name = '{logical_name}'"
            existing_rows = dataset.get_data(conflicting_table, where=where, limit=1)
            if existing_rows:
                conflicting_family = self._preview_view_family(conflicting_schema)
                if conflicting_family is not None and conflicting_family != current_family:
                    self._raise_mixed_view_family_error(record_id, logical_name, {current_family, conflicting_family})

    @staticmethod
    def _preview_view_family(schema: type[LanceModel]) -> str | None:
        if is_sequence_frame(schema):
            return canonical_table_name_for_schema(schema)
        if is_image(schema):
            return canonical_table_name_for_schema(schema)
        return None

    @staticmethod
    def _raise_mixed_view_family_error(record_id: str, logical_name: str, families: set[str]) -> None:
        family_list = ", ".join(sorted(families))
        raise DatasetIntegrityError(
            "Invalid dataset import: logical view family collision for "
            f"record_id='{record_id}', logical_name='{logical_name}'. "
            f"Found conflicting view families: {family_list}."
        )
