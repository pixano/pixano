# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The review of a model's annotations: which status an update may give a row.

A model's annotation arrives ``pending``. A person accepts it — as it is, or by saving an edit of
it — or rejects it, which deletes it (`ReviewStatus`). A person's own annotation carries no status,
since there is nothing to review. The service applies these rules to every annotation it updates
or creates, and none depends on the kind of annotation: every kind, including one added later,
follows the same rules.

What every layer reads the same way — which stored status means "not reviewed yet", which fields
hold a model's score — comes from `pixano.schemas`.
"""

from typing import Any

from lancedb.pydantic import LanceModel

from pixano.schemas import AnnotationSourceKind, ReviewStatus, is_entity_annotation


MODEL_SOURCE = AnnotationSourceKind.MODEL.value
"""The source type of a model's output, the only rows that carry a review status."""

NO_STATUS = ""
"""The status of a row with nothing to review: an annotation a person made."""

_STATUS_COLUMN = "review_status"
_SOURCE_COLUMN = "source_type"

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


def _human_row_refusal(status: Any) -> ReviewRuleError:
    return ReviewRuleError(
        f"Only a model's annotation (source_type '{MODEL_SOURCE}') has a review status. "
        f"This one is a person's and cannot be '{status}'."
    )


__all__ = [
    "MODEL_SOURCE",
    "NO_STATUS",
    "ReviewRuleError",
    "check_human_update",
    "check_new_row",
    "decision_of",
    "is_model_row",
]
