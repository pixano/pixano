# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The review status a model's annotation carries, and how a stored status reads."""

import pytest

from pixano.schemas import NOT_REVIEWED_STATUSES, BBox, ReviewStatus, review_status_of, stored_statuses


def _box(**fields) -> BBox:
    return BBox(id="b1", coords=[0, 0, 1, 1], format="xyxy", is_normalized=True, **fields)


class TestNotReviewed:
    def test_a_model_row_without_a_status_reads_as_pending(self):
        """Re-imported from JSONL, whose grammar does not carry the status: nobody reviewed it."""
        assert review_status_of("") is ReviewStatus.PENDING
        assert review_status_of("pending") is ReviewStatus.PENDING

    def test_a_decision_reads_as_itself(self):
        assert review_status_of("accepted") is ReviewStatus.ACCEPTED

    @pytest.mark.parametrize("stored", ["approved", "corrected", "rejected"])
    def test_a_value_that_is_no_status_is_refused(self, stored: str):
        """A reject deletes the row and a saved edit accepts it: no status says either."""
        with pytest.raises(ValueError):
            review_status_of(stored)

    def test_a_filter_on_pending_finds_the_rows_stored_without_a_status(self):
        assert set(stored_statuses(ReviewStatus.PENDING)) == set(NOT_REVIEWED_STATUSES) == {"pending", ""}
        assert stored_statuses(ReviewStatus.ACCEPTED) == ("accepted",)


class TestReviewStatus:
    def test_a_model_row_is_pending_or_accepted(self):
        assert [status.value for status in ReviewStatus] == ["pending", "accepted"]

    def test_a_row_takes_a_status_as_its_value(self):
        assert _box(source_type="model", review_status=ReviewStatus.ACCEPTED).review_status == "accepted"

    def test_a_human_row_carries_no_status(self):
        assert _box(source_type="human").review_status == ""

    @pytest.mark.parametrize("status", ["approved", "corrected", "rejected"])
    def test_a_row_cannot_hold_a_value_that_is_no_status(self, status: str):
        """A reject deletes the row and a saved edit accepts it: no status says either. Wherever a
        row is read through its schema, a value no review gives is refused rather than read as
        some status."""
        with pytest.raises(ValueError, match=status):
            _box(source_type="model", review_status=status)
