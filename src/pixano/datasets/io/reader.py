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

An optional review-status selection (spec amendment of 2026-10-05) filters the
model annotations of each bundle in memory, before it is yielded, so every
exporter sees the same rows and the query count does not change.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Iterable, Iterator

from lancedb.pydantic import LanceModel

from pixano.datasets.dataset import Dataset
from pixano.datasets.queries import TableQueryBuilder
from pixano.schemas import (
    AnnotationSourceKind,
    ReviewStatus,
    SchemaGroup,
    is_entity,
    is_entity_annotation,
    is_entity_dynamic_state,
    is_relation,
    is_reviewable_annotation,
    is_tracklet,
    review_status_of,
)
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


def _replace_rows(bundle: RecordBundle, table_name: str, rows: list[LanceModel]) -> None:
    """Set a table's rows in a bundle; a table left without rows is absent, as when it had none."""
    if rows:
        bundle.components[table_name] = rows
    else:
        bundle.components.pop(table_name, None)


@dataclass(frozen=True)
class _ReviewTables:
    """The component tables the review selection reads, by role — resolved from the schemas, never by name.

    Attributes:
        reviewed: The annotations a person can review (`pixano.schemas.is_reviewable_annotation`),
            the only ones the selection filters by status.
        unreviewed: The other annotations that name an entity, kept whatever their status:
            nobody could have accepted them. Relations and text spans, today.
        relations: The relations. Kept whatever their status, they protect what they point at.
        entities: The entities.
        tracks: The tracklets — the span of an object across frames, which the kept per-frame
            annotations still name. Never filtered by status. A model's tracklet is structure: it
            goes with its entity and does not keep it. One no model produced keeps its entity, as
            every annotation no model produced is kept. A kept relation naming a tracklet keeps
            its entity, and so the tracklet.
        states: The entities' dynamic states, which describe an entity rather than annotate it:
            dropped only with the entity.
    """

    reviewed: tuple[str, ...]
    unreviewed: tuple[str, ...]
    relations: tuple[str, ...]
    entities: tuple[str, ...]
    tracks: tuple[str, ...]
    states: tuple[str, ...]

    @classmethod
    def of(cls, schemas: dict[str, type[LanceModel]]) -> "_ReviewTables":
        def named(predicate: Callable[[type], bool]) -> tuple[str, ...]:
            return tuple(name for name, schema in schemas.items() if predicate(schema))

        return cls(
            reviewed=named(is_reviewable_annotation),
            unreviewed=named(_is_unreviewed_annotation),
            relations=named(is_relation),
            entities=named(is_entity),
            tracks=named(is_tracklet),
            states=named(is_entity_dynamic_state),
        )


def _is_unreviewed_annotation(schema: type) -> bool:
    return is_entity_annotation(schema) and not is_reviewable_annotation(schema) and not is_tracklet(schema)


def _is_model_output(annotation: LanceModel) -> bool:
    return annotation.source_type == AnnotationSourceKind.MODEL.value


class RecordBundleReader:
    """Streams a dataset as per-record bundles with bounded memory."""

    def __init__(
        self,
        page_size: int = 1024,
        max_bytes_in_flight: int = 256 * 1024 * 1024,
        initial_blob_batch: int = 64,
        query_counter: Callable[[str], None] | None = None,
        review_statuses: Iterable[str | ReviewStatus] = (),
    ):
        """Configure paging and the review-status selection.

        Args:
            page_size: Record ids per page (upper bound; blob tables sub-batch).
            max_bytes_in_flight: Approximate cap on blob bytes held per sub-batch.
            initial_blob_batch: Starting sub-batch size for blob-bearing tables.
            query_counter: Optional hook called with the table name per query
                (test instrumentation for the no-per-record-queries guarantee).
            review_statuses: The review statuses of the model annotations to keep. Annotations
                no model produced are always kept, and so are those of a kind no person can
                review yet (`pixano.schemas.is_reviewable_annotation`); a model's annotation
                without a status counts as ``pending``. Empty, the default, keeps every row.

        Raises:
            ValueError: A selected value is not a review status (``""`` included).
        """
        self.page_size = page_size
        self.max_bytes_in_flight = max_bytes_in_flight
        self.initial_blob_batch = initial_blob_batch
        self._query_counter = query_counter
        requested = {ReviewStatus(status) for status in review_statuses}
        #: The selection, in declaration order (exporters record it as is).
        self.review_statuses: tuple[str, ...] = tuple(status.value for status in ReviewStatus if status in requested)

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
        review_tables = (
            _ReviewTables.of({name: dataset.info.tables[name] for name in component_tables})
            if self.review_statuses
            else None
        )

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
                    if review_tables is not None:
                        self._select_by_review_status(bundle, review_tables)
                    yield bundle

    def _keeps(self, annotation: LanceModel) -> bool:
        if not _is_model_output(annotation):
            return True
        # A model's annotation without a status was written before review statuses existed, or
        # re-imported from a JSONL export (the grammar carries none): nobody reviewed it.
        return review_status_of(annotation.review_status).value in self.review_statuses

    def _select_by_review_status(self, bundle: RecordBundle, tables: _ReviewTables) -> None:
        """Drop the model annotations outside the selection, then the entities that leaves empty.

        Only the annotations a person can review are filtered. The others are kept whatever
        their status. A tracklet is never filtered either: a model's is part of its entity
        rather than an annotation of it, and one no model produced keeps its entity.

        An entity goes only when it had annotations and the selection removed every one of
        them, and nothing kept points at it: neither a kept entity's ``parent_id`` nor a kept
        relation's ``subject_id``/``object_id`` — at the entity or at one of its annotations,
        its tracklets included, since relations link annotations (``utils/integrity.py``). Its
        dynamic states and its tracklets go with it. An entity that never had an annotation
        stays.
        """
        owner_of: dict[str, str] = {}
        annotated: set[str] = set()
        still_annotated: set[str] = set()
        for table_name in (*tables.reviewed, *tables.unreviewed):
            filtered = table_name in tables.reviewed
            kept = []
            for annotation in bundle.components.get(table_name, []):
                if annotation.entity_id:
                    owner_of[annotation.id] = annotation.entity_id
                    annotated.add(annotation.entity_id)
                if not filtered or self._keeps(annotation):
                    kept.append(annotation)
                    if annotation.entity_id:
                        still_annotated.add(annotation.entity_id)
            _replace_rows(bundle, table_name, kept)
        for table_name in tables.tracks:
            for track in bundle.components.get(table_name, []):
                if not track.entity_id:
                    continue
                # A relation naming the tracklet protects its entity, which keeps the tracklet.
                owner_of[track.id] = track.entity_id
                if not _is_model_output(track):
                    # Exported whatever the selection, as every annotation no model produced: its
                    # entity stays with it.
                    annotated.add(track.entity_id)
                    still_annotated.add(track.entity_id)

        emptied = annotated - still_annotated
        if not emptied:
            return

        relation_targets = {
            target
            for table_name in tables.relations
            for relation in bundle.components.get(table_name, [])
            for target in (relation.subject_id, relation.object_id)
            if target
        }
        dropped = emptied - {owner_of.get(target, target) for target in relation_targets}

        # A kept entity keeps its parent, which keeps its own parent in turn.
        entities = {
            entity.id: entity for table_name in tables.entities for entity in bundle.components.get(table_name, [])
        }
        kept_entities = [entity for entity_id, entity in entities.items() if entity_id not in dropped]
        while kept_entities:
            parent_id = kept_entities.pop().parent_id
            if parent_id in dropped:
                dropped.discard(parent_id)
                if parent_id in entities:
                    kept_entities.append(entities[parent_id])

        for table_name in tables.entities:
            _replace_rows(
                bundle,
                table_name,
                [entity for entity in bundle.components.get(table_name, []) if entity.id not in dropped],
            )
        for table_name in (*tables.tracks, *tables.states):
            _replace_rows(
                bundle,
                table_name,
                [row for row in bundle.components.get(table_name, []) if row.entity_id not in dropped],
            )

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
