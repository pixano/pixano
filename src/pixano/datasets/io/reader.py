# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Streaming per-record reads for export and preview (spec §3.1/§10).

One ids-only native scan of the record table, then per-table
``record_id IN (page)`` push-down over the scalar indexes — never
per-record queries (the v1 exporter ran O(records × tables) scans).
Blob-bearing tables are fetched in adaptive sub-batches bounded by
``max_bytes_in_flight`` so a page of embedded media never balloons memory.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterator

from lancedb.pydantic import LanceModel

from pixano.datasets.dataset import Dataset
from pixano.datasets.queries import TableQueryBuilder
from pixano.schemas import SchemaGroup
from pixano.utils.python import to_sql_list


_BLOB_COLUMNS = ("raw_bytes", "blob", "preview")


@dataclass
class RecordBundle:
    """One record with all of its component rows, grouped by table."""

    record: LanceModel
    components: dict[str, list[LanceModel]] = field(default_factory=dict)

    @property
    def record_id(self) -> str:
        """The record's id."""
        return self.record.id


class RecordBundleReader:
    """Streams a dataset as per-record bundles with bounded memory."""

    def __init__(
        self,
        page_size: int = 1024,
        max_bytes_in_flight: int = 256 * 1024 * 1024,
        initial_blob_batch: int = 64,
        query_counter: Callable[[str], None] | None = None,
    ):
        """Configure paging.

        Args:
            page_size: Record ids per page (upper bound; blob tables sub-batch).
            max_bytes_in_flight: Approximate cap on blob bytes held per sub-batch.
            initial_blob_batch: Starting sub-batch size for blob-bearing tables.
            query_counter: Optional hook called with the table name per query
                (test instrumentation for the no-per-record-queries guarantee).
        """
        self.page_size = page_size
        self.max_bytes_in_flight = max_bytes_in_flight
        self.initial_blob_batch = initial_blob_batch
        self._query_counter = query_counter

    def iter_bundles(
        self,
        dataset: Dataset,
        splits: list[str] | None = None,
        limit: int | None = None,
    ) -> Iterator[RecordBundle]:
        """Yield every record once, with complete components, in (split, id) order."""
        record_table = dataset.open_table(SchemaGroup.RECORD.value)
        self._count("records:ids")
        id_query = TableQueryBuilder(record_table).select(["id", "split"])
        if splits:
            id_query = id_query.where(f"split in {to_sql_list(splits)}")
        id_rows = id_query.limit(None).to_arrow().to_pylist()
        id_rows.sort(key=lambda row: (row["split"], row["id"]))
        record_ids = [row["id"] for row in id_rows]
        if limit is not None:
            record_ids = record_ids[:limit]

        component_tables = [name for name in dataset.info.tables if name != SchemaGroup.RECORD.value]
        record_schema = dataset.info.tables[SchemaGroup.RECORD.value]

        for start in range(0, len(record_ids), self.page_size):
            page_ids = record_ids[start : start + self.page_size]
            page_sql = to_sql_list(page_ids)

            self._count("records:page")
            records = {
                row.id: row
                for row in TableQueryBuilder(record_table)
                .where(f"id in {page_sql}")
                .limit(None)
                .to_pydantic(record_schema)
            }

            bundles: dict[str, RecordBundle] = {
                record_id: RecordBundle(record=records[record_id]) for record_id in page_ids if record_id in records
            }

            for table_name in component_tables:
                schema = dataset.info.tables[table_name]
                has_blobs = any(column in schema.model_fields for column in _BLOB_COLUMNS)
                for rows in self._fetch_component(dataset, table_name, schema, page_ids, has_blobs):
                    for row in rows:
                        bundle = bundles.get(row.record_id)
                        if bundle is not None:
                            bundle.components.setdefault(table_name, []).append(row)

            for record_id in page_ids:
                bundle = bundles.get(record_id)
                if bundle is not None:
                    yield bundle

    def _fetch_component(
        self,
        dataset: Dataset,
        table_name: str,
        schema: type[LanceModel],
        page_ids: list[str],
        has_blobs: bool,
    ) -> Iterator[list[LanceModel]]:
        table = dataset.open_table(table_name)
        if not has_blobs:
            self._count(table_name)
            yield (
                TableQueryBuilder(table).where(f"record_id in {to_sql_list(page_ids)}").limit(None).to_pydantic(schema)
            )
            return

        # Blob-bearing tables: adaptive sub-batches under the byte budget.
        batch_size = min(self.initial_blob_batch, len(page_ids)) or 1
        position = 0
        while position < len(page_ids):
            chunk = page_ids[position : position + batch_size]
            position += len(chunk)
            self._count(table_name)
            rows = TableQueryBuilder(table).where(f"record_id in {to_sql_list(chunk)}").limit(None).to_pydantic(schema)
            yield rows

            chunk_bytes = sum(
                len(value) for row in rows for column in _BLOB_COLUMNS for value in [getattr(row, column, b"") or b""]
            )
            if chunk_bytes > 0:
                per_id = max(chunk_bytes // max(len(chunk), 1), 1)
                batch_size = max(1, min(self.page_size, self.max_bytes_in_flight // per_id))

    def _count(self, table_name: str) -> None:
        if self._query_counter is not None:
            self._query_counter(table_name)
