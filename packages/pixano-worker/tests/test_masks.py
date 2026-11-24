# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The geometry of masks, on its own: box prompts, emptiness, the box around a mask, overlaps.

The overlap is that of a model's mask with a person's — whichever interface wrote the person's.
"""

import subprocess
import sys
import textwrap
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from pixano_worker.kinds import masks
from pixano_worker.kinds.masks import covered, is_empty, is_readable, mask_iou, normalized_bounds, pixel_prompt
from pycocotools import mask as mask_api


# Every grid here is wider than it is tall: a square one would hide [height, width] read the
# wrong way round, or pixels read row by row instead of column by column.
HEIGHT, WIDTH = 6, 10
IMAGE_WIDTH, IMAGE_HEIGHT = 200, 100

# A person's masks on the HEIGHT × WIDTH grid, as each annotation interface writes them. Each
# string comes out of the interface's own encoder (ui/apps/*/src/lib/utils/maskUtils.ts), run
# under Node on the shape described; none is the output of pycocotools.
#
# The new interface, as it encodes a brush stroke or a moved mask (`encodeMask` in maskRaster.ts:
# `canvasAlphaToRle` on the canvas, then `rleToString`): an L — rows 1 to 3 over columns 2 to 5,
# and row 4 over columns 2 and 3. 14 pixels.
WEB_STRING = "=4200O10g0"
# The legacy interface, as it saves a segmenter's mask (`maskDataToFortranArrayToRle` on the
# row-major scores, then `rleToString` in resourcePayloads.ts): rows 2 to 4 over columns 4 to 8.
# 15 pixels.
LEGACY_STRING = "j03300000004"
# The new interface's own test (maskRaster.test.ts, "encodes painted pixels in column-major
# order"): a grid of 3 rows and 2 columns whose second column is painted — runs [3, 3].
WEB_TEST_HEIGHT, WEB_TEST_WIDTH = 3, 2
WEB_TEST_STRING = "33"

# Beyond this, a comparison that should take a millisecond is taken to loop forever.
HANG_TIMEOUT_S = 60


def _painted(height: int, width: int, *regions: tuple[slice, slice]) -> np.ndarray:
    """A grid with these regions — rows, columns — painted."""
    pixels = np.zeros((height, width), dtype=np.uint8)
    for rows, columns in regions:
        pixels[rows, columns] = 1
    return pixels


def _encoded(pixels: np.ndarray) -> dict[str, Any]:
    """A mask as the inference encodes one: pycocotools, on the pixels in column-major order."""
    rle = mask_api.encode(np.asfortranarray(pixels))
    return {"size": list(rle["size"]), "counts": rle["counts"]}


WEB_PIXELS = _painted(HEIGHT, WIDTH, (slice(1, 4), slice(2, 6)), (slice(4, 5), slice(2, 4)))
LEGACY_PIXELS = _painted(HEIGHT, WIDTH, (slice(2, 5), slice(4, 9)))
# The model's mask: rows 1 to 4 over columns 2 to 5, 16 pixels. The web L lies inside it, so their
# bounding boxes are the same while their pixels are not.
MODEL = _encoded(_painted(HEIGHT, WIDTH, (slice(1, 5), slice(2, 6))))


def _column(column: int) -> dict[str, Any]:
    """A mask painting one whole column of the grid."""
    return _encoded(_painted(HEIGHT, WIDTH, (slice(0, HEIGHT), slice(column, column + 1))))


def _box(coords: list[float], layout: str = "xyxy", normalised: bool = False) -> SimpleNamespace:
    return SimpleNamespace(coords=coords, format=layout, is_normalized=normalised)


class TestPixelPrompt:
    @pytest.mark.parametrize(
        ("coords", "layout", "normalised"),
        [
            ([20, 10, 120, 60], "xyxy", False),
            ([20, 10, 100, 50], "xywh", False),
            ([0.1, 0.1, 0.6, 0.6], "xyxy", True),
            ([0.1, 0.1, 0.5, 0.5], "xywh", True),
        ],
    )
    def test_every_layout_gives_the_same_pixels(self, coords: list[float], layout: str, normalised: bool) -> None:
        assert pixel_prompt(_box(coords, layout, normalised), IMAGE_WIDTH, IMAGE_HEIGHT) == [20, 10, 120, 60]

    def test_a_corner_is_rounded_to_the_nearest_pixel_not_truncated(self) -> None:
        """0.29 × 100 is 28.999…: truncated, the box would lose its top row."""
        row = _box([0.1, 0.29, 0.5, 0.5], "xywh", True)

        assert pixel_prompt(row, IMAGE_WIDTH, IMAGE_HEIGHT) == [20, 29, 120, 79]

    def test_a_box_past_the_image_is_cut_at_its_edges(self) -> None:
        assert pixel_prompt(_box([-30, -5, 250, 150]), IMAGE_WIDTH, IMAGE_HEIGHT) == [0, 0, 200, 100]

    @pytest.mark.parametrize(
        "coords",
        [
            [300, 10, 400, 60],  # beyond the right edge
            [20, 10, 20, 60],  # no width
            [20, 10, 20.4, 60],  # less than half a pixel wide, nothing once rounded
            [20, 10, 10, 60],  # right of its right edge
            [float("nan"), 10, 120, 60],
        ],
    )
    def test_a_box_reduced_to_nothing_prompts_nothing(self, coords: list[float]) -> None:
        assert pixel_prompt(_box(coords), IMAGE_WIDTH, IMAGE_HEIGHT) is None

    def test_an_image_without_a_size_prompts_nothing(self) -> None:
        assert pixel_prompt(_box([20, 10, 120, 60]), 0, IMAGE_HEIGHT) is None


class TestIsEmpty:
    def test_a_painted_mask_is_not_empty(self) -> None:
        assert not is_empty(MODEL)

    def test_a_grid_painted_nowhere_is_empty(self) -> None:
        blank = _encoded(_painted(HEIGHT, WIDTH))

        assert is_readable(blank)
        assert is_empty(blank)

    def test_the_empty_mask_the_dataset_stores_is_empty(self) -> None:
        """`CompressedRLE.none()`: a grid of nothing, and no run."""
        assert is_readable({"size": [0, 0], "counts": b""})
        assert is_empty({"size": [0, 0], "counts": b""})

    def test_a_row_holding_a_string_is_read_like_a_mapping_holding_bytes(self) -> None:
        """A dataset row carries bytes, an inference answer may carry a string: both are masks."""
        row = SimpleNamespace(size=[HEIGHT, WIDTH], counts=MODEL["counts"].decode())

        assert is_readable(row)
        assert not is_empty(row)


class TestNormalizedBounds:
    def test_the_box_around_a_mask_is_relative_to_its_grid(self) -> None:
        """Rows 1 to 4 over columns 2 to 5: the box's far edges lie past the last painted pixels."""
        assert normalized_bounds(MODEL) == pytest.approx((2 / WIDTH, 1 / HEIGHT, 6 / WIDTH, 5 / HEIGHT))

    def test_a_mask_whose_first_pixel_is_painted_starts_on_the_edge(self) -> None:
        """Its runs open on an empty run of background, which must not be read as a pixel."""
        corner = _encoded(_painted(HEIGHT, WIDTH, (slice(0, 2), slice(0, 3))))

        assert normalized_bounds(corner) == pytest.approx((0.0, 0.0, 3 / WIDTH, 2 / HEIGHT))

    def test_the_box_around_a_persons_mask_follows_its_outline(self) -> None:
        """The web L lies inside the model's rectangle: the same box goes around both."""
        assert normalized_bounds({"size": [HEIGHT, WIDTH], "counts": WEB_STRING}) == normalized_bounds(MODEL)

    def test_no_box_goes_around_a_mask_painted_nowhere(self) -> None:
        assert normalized_bounds(_encoded(_painted(HEIGHT, WIDTH))) is None

    @pytest.mark.parametrize("mask", [{"size": [HEIGHT, WIDTH], "counts": "=3"}, {"size": None, "counts": "33"}])
    def test_no_box_goes_around_a_mask_that_cannot_be_read(self, mask: dict[str, Any]) -> None:
        assert normalized_bounds(mask) is None


# Masks that are not one, each over the model's mask. pycocotools takes every one of them: compared
# with the model's mask, each string but the empty one loops forever (measured); the rest it
# misreads or fails on.
UNREADABLE = [
    {"size": [HEIGHT, WIDTH], "counts": "=3"},  # runs 13 and 3: 16 pixels of 60
    {"size": [HEIGHT, WIDTH], "counts": "=3T3"},  # runs 13, 3 and 100: 116 pixels of 60
    {"size": [HEIGHT, WIDTH], "counts": ""},  # no run at all, on a grid of 60
    {"size": [HEIGHT, WIDTH], "counts": "=42!0O10g0"},  # a character outside the encoding
    {"size": [HEIGHT, WIDTH], "counts": "=4200O10g"},  # its last run cut short
    {"size": [HEIGHT, WIDTH], "counts": [13, 4, 43]},  # uncompressed runs: not what Pixano stores
    {"size": [HEIGHT, WIDTH, 1], "counts": WEB_STRING},
    {"size": [-HEIGHT, -WIDTH], "counts": WEB_STRING},
    {"size": None, "counts": WEB_STRING},
]


class TestUnreadable:
    @pytest.mark.parametrize("mask", UNREADABLE)
    def test_is_refused_and_counts_as_empty(self, mask: dict[str, Any]) -> None:
        assert not is_readable(mask)
        assert is_empty(mask)

    def test_overlaps_nothing_and_does_not_hang_the_worker(self) -> None:
        """pycocotools loops forever, holding the GIL, comparing runs that do not fill their grid
        with a mask whose box they overlap. Run in a process of its own, so that a regression
        fails here instead of freezing the suite. A threshold of 0 would let any readable mask
        cover the model's."""
        script = textwrap.dedent(
            f"""
            from pixano_worker.kinds.masks import covered, mask_iou
            for mask in {UNREADABLE!r}:
                print(mask_iou(mask, {MODEL!r}), covered({MODEL!r}, "car", [(mask, "car")], threshold=0.0))
            """
        )

        done = subprocess.run(
            [sys.executable, "-c", script], capture_output=True, text=True, timeout=HANG_TIMEOUT_S, check=True
        )

        assert done.stdout.splitlines() == ["0.0 False"] * len(UNREADABLE)


class TestMaskIou:
    def test_on_the_same_grid_pixels_are_compared_not_bounding_boxes(self) -> None:
        """The web L lies inside the model's rectangle: same bounding box, 14 pixels of 16."""
        assert mask_iou({"size": [HEIGHT, WIDTH], "counts": WEB_STRING}, MODEL) == pytest.approx(14 / 16)

    def test_a_mask_with_itself(self) -> None:
        assert mask_iou(MODEL, MODEL) == pytest.approx(1.0)

    def test_disjoint_masks(self) -> None:
        apart = _encoded(_painted(HEIGHT, WIDTH, (slice(0, 2), slice(7, 10))))

        assert mask_iou(MODEL, apart) == 0.0

    def test_an_empty_mask_overlaps_nothing(self) -> None:
        assert mask_iou(MODEL, _encoded(_painted(HEIGHT, WIDTH))) == 0.0

    def test_across_grids_the_same_region_is_the_same_object(self) -> None:
        """A person's mask drawn at half the image's resolution: no pixel lines up, the region does."""
        model = _encoded(_painted(60, 100, (slice(12, 36), slice(20, 60))))
        person = _encoded(_painted(30, 50, (slice(6, 18), slice(10, 30))))

        assert mask_iou(model, person) == pytest.approx(1.0)

    def test_across_grids_bounding_boxes_are_compared_relative_to_each_grid(self) -> None:
        """The whole image against its left half, each on its own grid: one half."""
        whole = _encoded(_painted(60, 100, (slice(0, 60), slice(0, 100))))
        left_half = _encoded(_painted(30, 50, (slice(0, 30), slice(0, 25))))

        assert mask_iou(whole, left_half) == pytest.approx(0.5)


class TestCovered:
    PERSON = ({"size": [HEIGHT, WIDTH], "counts": WEB_STRING}, "car")

    def test_the_same_object_of_the_same_class_is_covered_case_aside(self) -> None:
        assert covered(MODEL, "Car", [self.PERSON], threshold=0.5)

    def test_another_class_is_not(self) -> None:
        assert not covered(MODEL, "dog", [self.PERSON], threshold=0.5)

    def test_a_mask_without_a_class_covers_any(self) -> None:
        assert covered(MODEL, "dog", [(self.PERSON[0], "")], threshold=0.5)

    def test_below_the_threshold_it_is_not(self) -> None:
        assert not covered(MODEL, "car", [self.PERSON], threshold=0.9)

    def test_nothing_to_contradict(self) -> None:
        assert not covered(MODEL, "car", [], threshold=0.5)

    def test_each_mask_is_decoded_once_however_often_it_is_compared(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every new mask of a view meets every protected mask of the view: three against three
        decode six strings, not twelve. Masks one column wide, apart, so every pair is compared."""
        decoded: list[bytes] = []
        decode = masks._runs

        def counted(counts: bytes) -> list[int] | None:
            decoded.append(counts)
            return decode(counts)

        monkeypatch.setattr(masks, "_runs", counted)
        masks._checked.cache_clear()
        new = [_column(column) for column in (0, 1, 2)]
        protected = [(_column(column), "car") for column in (5, 6, 7)]

        assert not any(covered(mask, "car", protected, threshold=0.5) for mask in new)
        assert len(decoded) == len(new) + len(protected)


class TestWhatTheInterfacesWrite:
    """A person's mask is written by an interface, not by pycocotools: the worker must read it as
    the pixels the person painted, on a grid that is not square."""

    @pytest.mark.parametrize(
        ("size", "counts", "pixels"),
        [
            ([HEIGHT, WIDTH], WEB_STRING, WEB_PIXELS),
            ([HEIGHT, WIDTH], LEGACY_STRING, LEGACY_PIXELS),
            (
                [WEB_TEST_HEIGHT, WEB_TEST_WIDTH],
                WEB_TEST_STRING,
                _painted(WEB_TEST_HEIGHT, WEB_TEST_WIDTH, (slice(0, WEB_TEST_HEIGHT), slice(1, 2))),
            ),
        ],
        ids=["web", "legacy", "web-test"],
    )
    def test_pycocotools_reads_the_pixels_the_person_painted(self, size: list[int], counts: str, pixels: Any) -> None:
        mask = {"size": size, "counts": counts}

        assert is_readable(mask)
        assert np.array_equal(mask_api.decode({"size": size, "counts": counts.encode()}), pixels)

    def test_the_overlap_with_a_web_mask(self) -> None:
        web = {"size": [HEIGHT, WIDTH], "counts": WEB_STRING}

        assert mask_iou(MODEL, web) == pytest.approx(14 / 16)
        assert covered(MODEL, "car", [(web, "car")], threshold=0.5)

    def test_the_overlap_with_a_legacy_mask(self) -> None:
        """Rows 2 to 4 over columns 4 and 5 in common: 6 pixels, of 16 + 15 - 6."""
        legacy = SimpleNamespace(size=[HEIGHT, WIDTH], counts=LEGACY_STRING.encode())

        assert mask_iou(MODEL, legacy) == pytest.approx(6 / 25)
        assert not covered(MODEL, "car", [(legacy, "car")], threshold=0.5)
        assert covered(MODEL, "car", [(legacy, "car")], threshold=0.2)
