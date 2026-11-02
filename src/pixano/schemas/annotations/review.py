# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What every layer reads the same way about the review of a model's annotations.

A model's row may be stored with no status at all, and still be a model's output nobody has
reviewed, and which of its fields hold the model's score depends on its schema. A layer that
decides something from a row's status or score reads it through these definitions rather than
writing its own copy of the answer, so that no two layers read the same row differently.
"""

from .entity_annotation import ReviewStatus


NOT_REVIEWED_STATUSES: tuple[str, ...] = (ReviewStatus.PENDING.value, "")
"""The stored statuses of a model's row that nobody has reviewed yet.

``pending`` is the status a model's output arrives with. The empty status is a model's row stored
without one: re-imported from JSONL, whose grammar does not carry the status, or written by a
client that sets none, as the legacy interface's smart tracking does. Nobody reviewed either, so
both read as ``pending``.
"""

_SCORE_DECLARATION = "MODEL_SCORE_FIELDS"


def review_status_of(stored: str) -> ReviewStatus:
    """The review status a model's row stands at, read from its stored ``review_status``.

    Args:
        stored: The row's ``review_status`` column.

    Returns:
        ``pending`` for a row nobody reviewed (`NOT_REVIEWED_STATUSES`), else the stored status.

    Raises:
        ValueError: The stored value is not a review status.
    """
    return ReviewStatus.PENDING if stored in NOT_REVIEWED_STATUSES else ReviewStatus(stored)


def stored_statuses(status: ReviewStatus) -> tuple[str, ...]:
    """The stored ``review_status`` values that read as this status, for a filter on the column.

    Args:
        status: The status looked for.

    Returns:
        Every value of `NOT_REVIEWED_STATUSES` for ``pending``, else the status's own value.
    """
    return NOT_REVIEWED_STATUSES if status is ReviewStatus.PENDING else (status.value,)


def model_score_fields(cls: type) -> tuple[str, ...]:
    """The fields of a schema that hold the score its model gave a row.

    Each schema declares its own in ``MODEL_SCORE_FIELDS``: ``confidence`` for a box, ``confidences``
    for a classification. A person's edit of a model's row does not change them, and changing them
    is not an edit.

    Args:
        cls: An annotation schema.

    Returns:
        The score fields, empty when the schema declares none.
    """
    return tuple(getattr(cls, _SCORE_DECLARATION, ()))


__all__ = [
    "NOT_REVIEWED_STATUSES",
    "model_score_fields",
    "review_status_of",
    "stored_statuses",
]
