# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The review status a model's annotation carries."""

import pytest

from pixano.schemas import BBox, ReviewStatus


def _box(**fields) -> BBox:
    return BBox(id="b1", coords=[0, 0, 1, 1], format="xyxy", is_normalized=True, **fields)


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
