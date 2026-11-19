# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""REST endpoint for a dataset's overview: how its records, media and annotations spread.

See backend-processing §22.7.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from pixano.api.query import FilterCompileError, build_column_catalogue, compile_cross_filter
from pixano.api.record_reads import refused
from pixano.api.routers._deps import get_dataset_dep
from pixano.api.routers.statistics import get_statistic_registry
from pixano.datasets import Dataset
from pixano.datasets.queries.computed_columns import InvalidRecordFilter
from pixano.datasets.queries.overview import DatasetOverview, dataset_overview
from pixano.statistics.registry import StatisticRegistry


router = APIRouter(prefix="/datasets/{dataset_id}", tags=["Overview"])


@router.get(
    "/overview",
    response_model=DatasetOverview,
    operation_id="get_dataset_overview",
    summary="Dataset overview",
    description="How the records the explorer's filters keep, their images and their objects spread: a card "
    "per thing measured, each a histogram or the count of each value, counted per split when asked. A card of "
    "a column filtered counts the records the other filters keep, and says how many its own filters keep.",
)
def get_dataset_overview(
    dataset_id: str,
    registry: Annotated[StatisticRegistry, Depends(get_statistic_registry)],
    dataset: Dataset = Depends(get_dataset_dep),
    filter: list[str] | None = Query(default=None),
    q: str | None = None,
    where: str | None = None,
    by_split: bool = False,
) -> DatasetOverview:
    """Return the overview of the records the explorer's filters keep, as the records list reads them."""
    try:
        cross_filter = compile_cross_filter(build_column_catalogue(dataset, "records"), filter, q, raw_where=where)
    except FilterCompileError as error:
        raise HTTPException(status_code=400, detail=str(error)) from None
    try:
        return dataset_overview(dataset, cross_filter, by_split=by_split, registry=registry)
    except InvalidRecordFilter as error:
        raise refused(error, bool(where)) from None
