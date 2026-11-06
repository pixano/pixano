# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""REST endpoint for the review queue: the next record to open to review a model's annotations."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from pixano.api.review import next_record
from pixano.api.routers._deps import get_dataset_dep
from pixano.datasets import Dataset
from pixano.schemas import ReviewStatus


router = APIRouter(prefix="/datasets/{dataset_id}/review", tags=["Review"])


class NextRecordResponse(BaseModel):
    """The next record to review.

    Attributes:
        record_id: The first record after ``after``, in record id order, wrapping round to the
            first record. Null when no record holds a model's annotation at the status that an
            interface can show for review.
        remaining: How many records hold one. This includes the record the reviewer is on,
            when it still holds one.
    """

    record_id: str | None
    remaining: int


@router.get(
    "/next",
    response_model=NextRecordResponse,
    operation_id="get_next_record_to_review",
    summary="Get the next record to review",
    description=(
        "The next record, in record id order, that holds a model's annotation at the given review "
        "status, whatever the kind of annotation. Wraps round to the first record. An annotation "
        "drawn on a view no interface can show for review, such as a frame of a video, is left out "
        "and keeps its status."
    ),
)
def get_next_record_to_review(
    dataset: Dataset = Depends(get_dataset_dep),
    status: Annotated[
        ReviewStatus, Query(description="The review status to look for. `pending` also finds a model's row with none.")
    ] = ReviewStatus.PENDING,
    after: Annotated[str | None, Query(description="The record the reviewer is leaving.")] = None,
) -> NextRecordResponse:
    """Return the next record to review and how many records hold annotations at the status."""
    found = next_record(dataset, status, after)
    return NextRecordResponse(record_id=found.record_id, remaining=found.remaining)
