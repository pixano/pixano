# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What every layer reads the same way about the review of a model's annotations.

A model's row may be stored with no status at all, and still be a model's output nobody has
reviewed, whether it can be reviewed depends on its kind and on the view it is drawn on, and which
of its fields hold the model's score depends on its schema. A layer that decides something from a
row's status, kind, view or score reads it through these definitions rather than writing its own
copy of the answer, so that no two layers read the same row differently.
"""

from typing import Callable

from ..views import is_image, is_point_cloud, is_point_cloud_frame, is_sequence_frame, is_text
from .entity_annotation import ReviewStatus, is_entity_annotation
from .relation import is_relation
from .text_span import is_text_span
from .tracklet import is_tracklet


NOT_REVIEWED_STATUSES: tuple[str, ...] = (ReviewStatus.PENDING.value, "")
"""The stored statuses of a model's row that nobody has reviewed yet.

``pending`` is the status a model's output arrives with. The empty status is a model's row stored
without one: re-imported from JSONL, whose grammar does not carry the status, or written by a
client that sets none, as the legacy interface's smart tracking does. Nobody reviewed either, so
both read as ``pending``: for the API's rules, for its queue, for the export by status, and for the
worker's writer.
"""

_SCORE_DECLARATION = "MODEL_SCORE_FIELDS"
_ALIGNMENT_DECLARATION = "MODEL_SCORE_ALIGNMENT"


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


# The kinds of entity annotation that no person can review yet. A tracklet is structure: the span
# of an object across frames, reviewed through the per-frame annotations it groups. No interface
# can show a relation or a text span for review yet. A model's row of such a kind would stay
# pending forever: the queue would never empty, and an export by status would drop it although
# nobody could have accepted it. Remove a kind from this list when an interface can review it.
_NOT_REVIEWABLE: tuple[Callable[[type], bool], ...] = (is_tracklet, is_relation, is_text_span)

# The kinds of view an interface can show a model's annotations on for review. The review
# interface (ui/apps/web) has a widget for a still image, a point cloud and a text: the bases its
# image, point-cloud and text extensions claim (`src/lib/extensions/builtin/`). It has none for a
# video or its frames, which derive from an image here, for a frame of a point-cloud sequence,
# which derives from a point cloud, or for a PDF; the legacy interface reviews still images, and
# shows video without reviewing it. Add a kind when an interface can show it for review.
_SHOWN_FOR_REVIEW: tuple[Callable[[type], bool], ...] = (is_image, is_point_cloud, is_text)
_FRAMES_OF_A_SEQUENCE: tuple[Callable[[type], bool], ...] = (is_sequence_frame, is_point_cloud_frame)


def is_reviewable_annotation(cls: type) -> bool:
    """Whether a person can review a model's rows of this schema.

    The review queue and the export by review status read only these. Every other row is outside
    the review: the queue does not wait for it, and an export keeps it whatever its status.

    Args:
        cls: An annotation schema.

    Returns:
        True for an entity annotation of a kind an interface can review.
    """
    return is_entity_annotation(cls) and not any(is_kind(cls) for is_kind in _NOT_REVIEWABLE)


def is_reviewable_view(cls: type) -> bool:
    """Whether an interface can show a model's annotations drawn on a view of this schema for review.

    The review queue leaves out a model's row drawn on any other view: a record whose rows to
    review are all on a video's frames would show nothing to review, and the queue would never
    empty. Such a row keeps its status. Only the queue reads this: an export by review status
    filters the row by its status like any other, so an export of accepted rows leaves out a
    pending row nobody could review.

    Args:
        cls: A view schema.

    Returns:
        True for a still image, a point cloud or a text; False for a video, a frame of a video or
        of a point-cloud sequence, a PDF, and what is not a view.
    """
    if any(is_frame(cls) for is_frame in _FRAMES_OF_A_SEQUENCE):
        return False
    return any(is_shown(cls) for is_shown in _SHOWN_FOR_REVIEW)


def model_score_fields(cls: type) -> tuple[str, ...]:
    """The fields of a schema that hold the score its model gave a row.

    Each schema declares its own in ``MODEL_SCORE_FIELDS``: ``confidence`` for a box, ``confidences``
    for a classification. A person's edit of a model's row does not change them, and changing them
    is not an edit. A list of scores only moves with the values it scores
    (`model_score_alignment`).

    Args:
        cls: An annotation schema.

    Returns:
        The score fields, empty when the schema declares none.
    """
    return tuple(getattr(cls, _SCORE_DECLARATION, ()))


def model_score_alignment(cls: type) -> dict[str, str]:
    """The field each list of model scores of a schema scores, position by position.

    Each schema declares it in ``MODEL_SCORE_ALIGNMENT``, next to its ``MODEL_SCORE_FIELDS``: a
    classification's ``confidences[i]`` scores its ``labels[i]``. A model's score follows what it
    scores. When a person's edit changes the scored field, each value the model gave keeps the
    model's score, and a value the person adds takes the score the client sent with it. Kept as
    stored, the scores would score other values, or no longer match their number.

    Args:
        cls: An annotation schema.

    Returns:
        Each aligned score field, with the field it scores. Empty when no score is aligned with
        another field, as a box's single ``confidence``.
    """
    return dict(getattr(cls, _ALIGNMENT_DECLARATION, {}))


__all__ = [
    "NOT_REVIEWED_STATUSES",
    "is_reviewable_annotation",
    "is_reviewable_view",
    "model_score_alignment",
    "model_score_fields",
    "review_status_of",
    "stored_statuses",
]
