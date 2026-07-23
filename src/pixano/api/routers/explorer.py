# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Explorer router: filter capability document and item navigation."""

from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.api.models import (
    ColumnDescriptorResponse,
    FilterSchemaResponse,
    NeighborsResponse,
    SearchCapabilities,
)
from pixano.api.query import (
    FilterCompileError,
    build_column_catalogue,
    compile_filters,
    validate_sort,
)
from pixano.api.routers._deps import get_dataset_dep
from pixano.datasets import Dataset


router = APIRouter(prefix="/datasets/{dataset_id}", tags=["Explorer"])


@router.get(
    "/filters",
    response_model=FilterSchemaResponse,
    response_model_exclude_none=True,
    operation_id="get_filter_schema",
    summary="Filter capability document",
    description="Publish the filterable/sortable columns, their operators and enumerable values, "
    "and the available search modes for the dataset's record table.",
)
def get_filter_schema(
    dataset_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
) -> FilterSchemaResponse:
    """Return the explorer's filter/sort/search capability document."""
    catalogue = build_column_catalogue(dataset, "records")
    columns = [
        ColumnDescriptorResponse(
            name=column.name,
            type=column.type,
            collection=column.collection,
            source=column.source,
            filterable=column.filterable,
            sortable=column.sortable,
            searchable=column.searchable,
            indexed=column.indexed,
            operators=list(column.operators),
            values=list(column.values) if column.values is not None else None,
            values_complete=column.values_complete,
        )
        for column in catalogue
    ]
    # `search.modes` is ["text"] today (lexical); semantic modes/models land in
    # 0.9 and will populate these fields with no frontend change.
    return FilterSchemaResponse(table="records", columns=columns, search=SearchCapabilities())


@router.get(
    "/records/{record_id}/neighbors",
    response_model=NeighborsResponse,
    operation_id="get_record_neighbors",
    summary="Record neighbors",
    description="Locate a record within the current filtered, sorted result set and return its "
    "previous/next record ids, 1-based position, and the result-set total.",
)
def get_record_neighbors(
    dataset_id: str,
    record_id: str,
    dataset: Dataset = Depends(get_dataset_dep),
    filter: list[str] | None = Query(default=None),
    q: str | None = None,
    sort: str | None = None,
    order: str | None = None,
    where: str | None = None,
) -> NeighborsResponse:
    """Return a record's neighbors within the explorer's active filter and sort."""
    catalogue = build_column_catalogue(dataset, "records")
    try:
        compiled_where, _referenced, _index_servable = compile_filters(catalogue, filter, q)
        sortcol, sort_order = validate_sort(catalogue, sort, order)
    except FilterCompileError as err:
        raise HTTPException(status_code=400, detail=str(err)) from None

    if where:
        compiled_where = f"({where})" if compiled_where is None else f"{compiled_where} AND ({where})"

    try:
        neighbors = dataset.get_neighbors(
            record_id=record_id,
            table_name="records",
            where=compiled_where,
            sortcol=sortcol,
            order=sort_order,
        )
    except RuntimeError as err:
        # Only reachable via a malformed deprecated raw `where`.
        if where:
            raise HTTPException(status_code=400, detail=f"Invalid filter. {err}") from None
        raise
    return NeighborsResponse(**neighbors)
