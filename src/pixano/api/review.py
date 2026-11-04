# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The review of a model's annotations: the status rules, and the next record to review.

A model's annotation arrives ``pending``. A person accepts it — as it is, or by saving an edit of
it — or rejects it, which deletes it (`ReviewStatus`). A person's own annotation carries no status,
since there is nothing to review. This module holds three things, and none depends on the kind of
annotation. Every kind, including one added later, follows the same rules and is found by the same
scan:

- which status an update may give a row. The service applies these rules to every annotation
  it updates or creates;
- which annotations a person's edit of an entity accepts;
- which record still holds annotations at a given status, so that a reviewer can move from one
  record to the next (`GET /datasets/{id}/review/next`).

What every layer reads the same way — which stored status means "not reviewed yet", which kinds
can be reviewed, which fields hold a model's score — comes from `pixano.schemas`.
"""

from bisect import bisect_right
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

from lancedb.pydantic import LanceModel
from lancedb.table import LanceTable

from pixano.datasets import Dataset
from pixano.datasets.queries import TableQueryBuilder
from pixano.schemas import (
    AnnotationSourceKind,
    ReviewStatus,
    is_entity_annotation,
    is_reviewable_annotation,
    stored_statuses,
)
from pixano.utils.python import to_sql_list


MODEL_SOURCE = AnnotationSourceKind.MODEL.value
"""The source type of a model's output, the only rows that carry a review status."""

NO_STATUS = ""
"""The status of a row with nothing to review: an annotation a person made."""

_STATUS_COLUMN = "review_status"
_SOURCE_COLUMN = "source_type"
_RECORD_COLUMN = "record_id"
_ENTITY_COLUMN = "entity_id"

# What an update of a model's row may ask for: ``pending``, which only echoes the status a model's
# output arrives with, and ``accepted``, the one decision. A person who rejects the row deletes it.
_VALID_STATUSES = [ReviewStatus.PENDING.value, ReviewStatus.ACCEPTED.value]


class ReviewRuleError(ValueError):
    """A request that the review rules refuse, such as a status a row cannot take. The API answers 400."""


def is_model_row(row: LanceModel) -> bool:
    """Whether the row is a model's output, and so has something to review."""
    return getattr(row, _SOURCE_COLUMN, None) == MODEL_SOURCE


def decision_of(row: LanceModel, requested: Any) -> ReviewStatus | None:
    """The decision that an update of a model's row asks for, or None when it asks for none.

    There is one decision: ``accepted``, taken from ``pending``. A person who rejects a model's
    annotation deletes it, so no status says so. These cases ask for no decision:

    - no status, or null.
    - the status the row already has. This is an echo, not a decision: a client that edits by
      sending back every field of the row it read sends the status back too. ``accepted`` asked
      of an accepted row is one.
    - ``pending``, the status a model's output arrives with, which no person gives: no update
      takes a row back from ``accepted``.

    Args:
        row: The model's row as stored.
        requested: The ``review_status`` of the request, if any.

    Returns:
        ``accepted``, or None.

    Raises:
        ReviewRuleError: The empty status, which would take the row out of the review, or any
            other value than ``pending`` and ``accepted``.
    """
    if requested is None or requested == getattr(row, _STATUS_COLUMN, NO_STATUS):
        return None
    if requested == ReviewStatus.PENDING.value:
        return None
    if requested == NO_STATUS:
        raise ReviewRuleError(
            "A model's annotation keeps a review status: review_status cannot be emptied. "
            f"Must be one of {_VALID_STATUSES}."
        )
    if requested != ReviewStatus.ACCEPTED.value:
        raise ReviewRuleError(f"review_status '{requested}' is not valid. Must be one of {_VALID_STATUSES}.")
    return ReviewStatus.ACCEPTED


def check_human_update(row: LanceModel, requested: Any) -> None:
    """Refuse a review status on a person's annotation, which has nothing to review.

    Sending back the status the row already has is not a request, as for a model's row.

    Args:
        row: The person's row as stored.
        requested: The ``review_status`` of the request, if any.

    Raises:
        ReviewRuleError: The request sets a status.
    """
    if requested in (None, NO_STATUS, getattr(row, _STATUS_COLUMN, NO_STATUS)):
        return
    raise _human_row_refusal(requested)


def check_new_row(row: LanceModel) -> None:
    """Refuse a new person's annotation that carries a review status.

    A model's row may be created with a status: its output arrives ``pending``, and a client
    that stores a model's output through the API may write it so.

    Args:
        row: The validated row to create.

    Raises:
        ReviewRuleError: A person's row with a status.
    """
    if not is_entity_annotation(type(row)) or is_model_row(row):
        return
    status = getattr(row, _STATUS_COLUMN, NO_STATUS)
    if status != NO_STATUS:
        raise _human_row_refusal(status)


def acceptances_of_entity_edit(dataset: Dataset, entity_id: str) -> dict[str, list[LanceModel]]:
    """The model's annotations that a person's edit of an entity accepts, made ``accepted``.

    What an annotation says can live in its entity: a detection's class, for instance, lives in
    the object it names. A person who fixes the class edits the entity and leaves the annotation
    as the model wrote it. That is an edit of what the annotation says all the same, saved by the
    person, and it follows the rule of a saved edit of the row itself: a pending row becomes
    ``accepted``. Left pending, the next run of the model would write its own class back over the
    person's, and the queue and the export by status would read the row as never reviewed. An
    accepted row is already a person's work and is not rewritten.

    Every table of entity annotations is searched, whatever its kind. A table that lacks the
    status column is skipped: a dataset whose migration to the review layout failed, a read-only
    library for instance, has nowhere to store a decision in it. Nothing is written: the caller
    stores the rows with the entity's edit.

    Args:
        dataset: The dataset holding the entity.
        entity_id: The entity the person edits.

    Returns:
        The rows to store, by table, their status set to ``accepted``. Only the pending rows, a
        model's row stored without a status included (`pixano.schemas.NOT_REVIEWED_STATUSES`).
    """
    where = (
        f"{_ENTITY_COLUMN} IN {to_sql_list([entity_id])} AND {_SOURCE_COLUMN} = '{MODEL_SOURCE}' "
        f"AND {_STATUS_COLUMN} IN {to_sql_list(stored_statuses(ReviewStatus.PENDING))}"
    )
    acceptances: dict[str, list[LanceModel]] = {}
    for table_name, schema in dataset.info.tables.items():
        if not is_entity_annotation(schema):
            continue
        if _STATUS_COLUMN not in dataset.open_table(table_name).schema.names:
            continue
        rows = dataset.get_data(table_name, where=where, limit=None)
        for row in rows:
            setattr(row, _STATUS_COLUMN, ReviewStatus.ACCEPTED.value)
        if rows:
            acceptances[table_name] = rows
    return acceptances


def _human_row_refusal(status: Any) -> ReviewRuleError:
    return ReviewRuleError(
        f"Only a model's annotation (source_type '{MODEL_SOURCE}') has a review status. "
        f"This one is a person's and cannot be '{status}'."
    )


@dataclass(frozen=True)
class NextRecord:
    """The next record to review.

    Attributes:
        record_id: The first record after the one asked about, in record id order, wrapping
            round to the first record. None when no record holds an annotation at the status.
        remaining: How many records hold an annotation at the status. This includes the
            record the reviewer is on, when it still holds one.
    """

    record_id: str | None
    remaining: int


def records_at(dataset: Dataset, status: ReviewStatus) -> list[str]:
    """The records that hold a model's annotation at this status, in record id order.

    Each table of a kind a person can review (`pixano.schemas.is_reviewable_annotation`) is
    scanned, whatever that kind, and only its record ids are read. A kind no interface can review
    would keep its records in the queue for good. The scan uses the tables the dataset has. It
    never goes through `BaseService.resolve_table`, which creates a missing annotation table: a
    review must not change the dataset's tables.

    Args:
        dataset: The dataset under review.
        status: The status looked for. ``pending`` also finds a model's row with no status
            (`pixano.schemas.NOT_REVIEWED_STATUSES`).

    Returns:
        The distinct record ids, sorted.
    """
    where = f"{_SOURCE_COLUMN} = '{MODEL_SOURCE}' AND {_STATUS_COLUMN} IN {to_sql_list(stored_statuses(status))}"
    records: set[str] = set()
    for table in _tables_under_review(dataset):
        found = TableQueryBuilder(table).select([_RECORD_COLUMN]).where(where).to_arrow()
        records.update(found.column(_RECORD_COLUMN).to_pylist())
    return sorted(records)


def _tables_under_review(dataset: Dataset) -> Iterator[LanceTable]:
    """The dataset's tables of a kind a person can review, where a decision can be stored."""
    for table_name, schema in dataset.info.tables.items():
        if not is_reviewable_annotation(schema):
            continue
        table = dataset.open_table(table_name)
        # A dataset whose migration to the review layout failed, a read-only library for
        # instance, has tables without the column. A decision could not be stored in them, so
        # their rows are outside the review, like a kind no interface can review: the queue
        # does not wait for them.
        if _STATUS_COLUMN not in table.schema.names:
            continue
        yield table


def next_record(dataset: Dataset, status: ReviewStatus, after: str | None = None) -> NextRecord:
    """The record to open next to review the annotations at a status.

    Args:
        dataset: The dataset under review.
        status: The status the reviewer works on, usually ``pending``.
        after: The record the reviewer is leaving, if any. It does not need to hold anything
            at the status.

    Returns:
        The first record after ``after`` in record id order, wrapping round, and how many
        records hold an annotation at the status.
    """
    records = records_at(dataset, status)
    if not records:
        return NextRecord(record_id=None, remaining=0)
    following = bisect_right(records, after) if after is not None else 0
    return NextRecord(record_id=records[following % len(records)], remaining=len(records))


__all__ = [
    "MODEL_SOURCE",
    "NO_STATUS",
    "NextRecord",
    "ReviewRuleError",
    "acceptances_of_entity_edit",
    "check_human_update",
    "check_new_row",
    "decision_of",
    "is_model_row",
    "next_record",
    "records_at",
]
