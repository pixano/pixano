# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Reading the explorer's records under one request: a page, a record's neighbors, those a search keeps.

Each read goes through the join of the records with their statistics when a statistic is filtered or
sorted on (`pixano.datasets.queries.record_statistics`, backend-processing §22.5), as before
otherwise. This module makes that choice, once for the three reads.

A deprecated raw `where` clause is the only condition that can be malformed: the reads answer it
400 when LanceDB refuses it, and let any other failure through.
"""

from typing import Any

from fastapi import HTTPException

from pixano.api.models import PaginatedResponse
from pixano.api.query import RecordQuery
from pixano.api.service import MAX_QUERY_LIMIT, BaseService
from pixano.datasets import Dataset
from pixano.datasets.queries.record_statistics import (
    InvalidRecordFilter,
    matching_record_ids,
    ordered_record_ids,
    record_neighbors,
)
from pixano.schemas import SchemaGroup


_RECORDS_TABLE = SchemaGroup.RECORD.value


def read_page(
    dataset: Dataset, service: BaseService, query: RecordQuery, limit: int, offset: int, raw_where: bool
) -> PaginatedResponse:
    """A page of the records the request matches, in its order.

    Args:
        dataset: The dataset.
        service: The records' service, which reads a page or records by identifier.
        query: The request, compiled.
        limit: The page's size, at most `MAX_QUERY_LIMIT`.
        offset: How many records the page skips.
        raw_where: Whether the request carries a deprecated raw clause.

    Returns:
        The page, with how many records the request matches.
    """
    if not query.through_statistics:
        return service.list(
            where=query.where,
            limit=limit,
            offset=offset,
            sortcol=query.order.column,
            order=query.order.direction,
            force_full_scan=not query.index_servable,
            raw_where=raw_where,
        )
    limit = min(limit, MAX_QUERY_LIMIT)
    try:
        record_ids, total = ordered_record_ids(
            dataset, query.where, query.statistics_filter, query.order, limit, offset
        )
    except InvalidRecordFilter as error:
        raise _refused(error, raw_where) from None
    return PaginatedResponse(items=service.get_many(record_ids), total=total, limit=limit, offset=offset)


def read_neighbors(dataset: Dataset, query: RecordQuery, record_id: str, raw_where: bool) -> dict[str, Any]:
    """Where a record stands among the records the request matches, in its order.

    Returns:
        ``{"prev", "next", "position", "total"}``; a record the request does not match has no
        previous, next nor position.
    """
    if query.through_statistics:
        # The join says when LanceDB refused the condition on the records; any other failure is
        # the server's.
        try:
            return record_neighbors(dataset, query.where, query.statistics_filter, query.order, record_id)
        except InvalidRecordFilter as error:
            raise _refused(error, raw_where) from None
    try:
        return dataset.get_neighbors(
            record_id=record_id,
            table_name=_RECORDS_TABLE,
            where=query.where,
            sortcol=query.order.column,
            order=query.order.direction,
        )
    except RuntimeError as error:
        raise _refused(error, raw_where) from None


def read_matching_ids(dataset: Dataset, query: RecordQuery, raw_where: bool) -> list[str]:
    """The records the request matches, in no particular order: those a semantic search is narrowed to."""
    if query.statistics_filter is not None:
        try:
            return matching_record_ids(dataset, query.where, query.statistics_filter)
        except InvalidRecordFilter as error:
            raise _refused(error, raw_where) from None
    try:
        matches = dataset.get_data(_RECORDS_TABLE, where=query.where, limit=None)
    except RuntimeError as error:
        raise _refused(error, raw_where) from None
    return [record.id for record in (matches or [])]


def _refused(error: Exception, raw_where: bool) -> Exception:
    """A failure of a read as answered: bad input when a raw clause may be to blame, as it is."""
    if raw_where:
        return HTTPException(status_code=400, detail=f"Invalid filter. {error}")
    return error
