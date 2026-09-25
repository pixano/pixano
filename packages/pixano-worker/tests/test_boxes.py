# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The geometry of detected boxes, on its own."""

from types import SimpleNamespace

import pytest
from pixano_worker.kinds.boxes import covered, iou, normalized_corners, placed


SIZE = (200, 100)


class TestIou:
    def test_the_same_box(self) -> None:
        assert iou((0, 0, 1, 1), (0, 0, 1, 1)) == 1

    def test_disjoint_boxes(self) -> None:
        assert iou((0, 0, 0.1, 0.1), (0.5, 0.5, 1, 1)) == 0

    def test_half_a_box(self) -> None:
        assert iou((0, 0, 1, 1), (0, 0, 0.5, 1)) == 0.5


class TestPlaced:
    def test_pixel_corners_become_a_normalised_top_left_and_size(self) -> None:
        assert placed([[20, 10, 120, 60]], [0.9], ["car"], SIZE) == ([[0.1, 0.1, 0.5, 0.5]], [0.9], ["car"])

    def test_a_box_past_the_image_is_cut_at_its_edge(self) -> None:
        assert placed([[-10, -5, 250, 150]], [0.9], ["car"], SIZE)[0] == [[0.0, 0.0, 1.0, 1.0]]

    def test_a_box_reduced_to_nothing_is_not_one(self) -> None:
        assert placed([[300, 10, 400, 60], [10, 10, 10, 60]], [0.9, 0.8], ["car", "dog"], SIZE) == ([], [], [])

    def test_only_the_classes_asked_for_are_kept_case_aside(self) -> None:
        kept = placed([[0, 0, 10, 10], [0, 0, 20, 20]], [0.9, 0.8], ["Car", "dog"], SIZE, wanted=["CAR"])

        assert kept[2] == ["Car"]


class TestNormalizedCorners:
    """A person's box may be stored in either layout, normalised or in pixels."""

    @pytest.mark.parametrize(
        ("coords", "layout", "normalised"),
        [
            ([20, 10, 120, 60], "xyxy", False),
            ([20, 10, 100, 50], "xywh", False),
            ([0.1, 0.1, 0.6, 0.6], "xyxy", True),
            ([0.1, 0.1, 0.5, 0.5], "xywh", True),
        ],
    )
    def test_every_layout_gives_the_same_corners(self, coords: list[float], layout: str, normalised: bool) -> None:
        row = SimpleNamespace(coords=coords, format=layout, is_normalized=normalised)

        assert normalized_corners(row, *SIZE) == pytest.approx((0.1, 0.1, 0.6, 0.6))


class TestCovered:
    PERSON = ((0.0, 0.0, 0.5, 1.0), "car")

    def test_the_same_object_of_the_same_class_is_covered(self) -> None:
        assert covered([0.0, 0.0, 0.5, 1.0], "Car", [self.PERSON], 0.5)

    def test_another_class_is_not(self) -> None:
        assert not covered([0.0, 0.0, 0.5, 1.0], "dog", [self.PERSON], 0.5)

    def test_a_box_without_a_class_covers_any(self) -> None:
        assert covered([0.0, 0.0, 0.5, 1.0], "dog", [((0.0, 0.0, 0.5, 1.0), "")], 0.5)

    def test_below_the_threshold_it_is_not(self) -> None:
        assert not covered([0.0, 0.0, 0.5, 1.0], "car", [((0.0, 0.0, 0.25, 1.0), "car")], 0.6)
