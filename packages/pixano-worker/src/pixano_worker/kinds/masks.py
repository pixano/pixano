# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The geometry of masks: where a box prompts a model, and whether a person's mask covers a model's.

Pure functions, no dataset and no inference, beside `boxes`: a kind decides what to do, these say
where things are.

A mask is held the way COCO compresses it, which is how Pixano stores it (`CompressedRLE`), how
the inference answers and how both annotation interfaces write it: `size` is its pixel grid as
[height, width], and `counts` the lengths of the runs of its column-major pixels, background
first, written as a string. Here a mask is any object carrying `size` and `counts` — a dataset
row, an inference answer — or a mapping with those two keys.

pycocotools computes the overlaps, but it trusts what it is given: on a string whose runs do not
fill the grid exactly, its intersection over union loops forever (measured with pycocotools
2.0.11, holding the GIL — the whole worker freezes). Masks a person wrote reach these functions,
so every mask is read and checked here before pycocotools sees it.
"""

import functools
import math
import numbers
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Sequence

from pycocotools import mask as mask_api

from .boxes import Box, iou, normalized_corners


# The compressed string, as pycocotools writes it (`rleToString`, maskApi.c) and both interfaces
# copy it (`rleToString`, maskUtils.ts): each character carries five bits of a run, low bits
# first, offset from '0' so that the string stays printable. A sixth bit says the run goes on in
# the next character; the fifth bit of a run's last character is its sign. From the fourth run
# on, a run is written as its difference with the run two before it.
_FIRST_CHARACTER = ord("0")
_CHARACTERS = 64
_BITS_PER_CHARACTER = 5
_VALUE_BITS = 0x1F
_SIGN_BIT = 0x10
_CONTINUES_BIT = 0x20
_DELTA_FROM_RUN = 3
_DELTA_STRIDE = 2

# pycocotools reads a grid as [height, width].
_GRID_DIMENSIONS = 2

# pycocotools compares masks to masks, not to crowd regions.
_NOT_A_CROWD = [0]

# How many masks stay read from one call to the next. Each of a view's new masks is compared with
# every protected mask of the view, so the same masks are read over and over; kept, each is
# decoded once — measured on a 1920 × 1080 mask: half a millisecond for a clean outline, two and a
# half for a ragged one, 900 comparisons for 30 masks against 30. Enough for several views' masks
# at once, a few kilobytes of string each.
_MASKS_KEPT_READ = 256


@dataclass(frozen=True)
class _Read:
    """A mask that passed the checks: its grid, its compressed string, how many pixels it paints."""

    height: int
    width: int
    counts: bytes
    area: int

    @property
    def rle(self) -> dict[str, Any]:
        """The mask as pycocotools takes it: a plain dict, its type checked exactly."""
        return {"size": [self.height, self.width], "counts": self.counts}


def pixel_prompt(row: Any, width: int, height: int) -> list[int] | None:
    """A stored box as a prompt for a segmentation model: whole pixels, left, top, right, bottom.

    Rounded to the nearest pixel rather than truncated: a corner stored normalised comes back a
    hair below its pixel (0.29 × 100 is 28.999…), and truncation would move it by one. Cut at
    the image's edges, as the model reads nothing beyond them.

    Args:
        row: A box as the dataset stores it, in any layout.
        width: The image's width, in pixels.
        height: The image's height, in pixels.

    Returns:
        The prompt, or None when the box is reduced to nothing — within the image, or rounded —
        or is not a box at all: a model asked about an empty box answers anyway.
    """
    if width <= 0 or height <= 0:
        return None
    left, top, right, bottom = normalized_corners(row, width, height)
    if not all(math.isfinite(value) for value in (left, top, right, bottom)):
        return None
    x1, x2 = (min(max(round(value * width), 0), width) for value in (left, right))
    y1, y2 = (min(max(round(value * height), 0), height) for value in (top, bottom))
    if x2 <= x1 or y2 <= y1:
        return None
    return [x1, y1, x2, y2]


def is_readable(mask: Any) -> bool:
    """Whether a mask is one: a grid of two dimensions, and runs that fill it exactly.

    Uncompressed runs — a list of numbers — are not what Pixano stores, and are not read here.
    """
    return _read(mask) is not None


def is_empty(mask: Any) -> bool:
    """Whether a mask paints no pixel.

    An unreadable mask (see `is_readable`) counts as empty: no pixel of it can be relied on, so
    nothing should be written or compared from it.
    """
    read = _read(mask)
    return read is None or read.area == 0


def mask_iou(first: Any, second: Any) -> float:
    """Intersection over union of two masks.

    Pixel by pixel when both lie on the same grid. On different grids — a mask drawn on a
    resized copy of the image, an import — no pixel matches another, and pycocotools answers -1:
    the masks' bounding boxes, each relative to its own grid, are compared instead.

    An empty or unreadable mask overlaps nothing: 0.
    """
    read_first, read_second = _read(first), _read(second)
    if read_first is None or read_second is None:
        return 0.0
    return _iou(read_first, read_second)


def covered(mask: Any, name: str, protected: Sequence[tuple[Any, str]], threshold: float) -> bool:
    """Whether a person's mask already says what this model's mask says.

    The rule detection follows for boxes (`boxes.covered`), on masks.

    Args:
        mask: The model's mask.
        name: The class of the object it names.
        protected: The masks it must not contradict, with the class of their object — empty for
            an object without one, which stands for any class.
        threshold: The intersection over union from which a mask covers the model's.
    """
    read = _read(mask)
    if read is None:
        return False
    for other, other_class in protected:
        if other_class and other_class.casefold() != (name or "").casefold():
            continue
        read_other = _read(other)
        if read_other is not None and _iou(read, read_other) >= threshold:
            return True
    return False


def _iou(first: _Read, second: _Read) -> float:
    """Intersection over union of two masks already read."""
    if first.area == 0 or second.area == 0:
        return 0.0
    if (first.height, first.width) == (second.height, second.width):
        return float(mask_api.iou([first.rle], [second.rle], _NOT_A_CROWD)[0][0])
    return iou(_normalized_bounds(first), _normalized_bounds(second))


def _normalized_bounds(read: _Read) -> Box:
    """A mask's bounding box as corners relative to its own grid."""
    x, y, width, height = (float(value) for value in mask_api.toBbox(read.rle))
    return x / read.width, y / read.height, (x + width) / read.width, (y + height) / read.height


def _read(mask: Any) -> _Read | None:
    """A mask's grid and runs, checked; None when it is not a mask pycocotools can safely read."""
    size, counts = _field(mask, "size"), _field(mask, "counts")
    if isinstance(counts, str):
        counts = counts.encode()
    if not isinstance(counts, (bytes, bytearray, memoryview)) or not _is_grid(size):
        return None
    height, width = (int(value) for value in size)
    return _checked(height, width, bytes(counts))


@functools.lru_cache(maxsize=_MASKS_KEPT_READ)
def _checked(height: int, width: int, counts: bytes) -> _Read | None:
    """A grid and its string, checked once: `_read`, past the fields."""
    runs = _runs(counts)
    if runs is None or any(run < 0 for run in runs) or sum(runs) != height * width:
        return None
    # The runs alternate background and foreground, background first.
    return _Read(height, width, counts, sum(runs[1::2]))


def _field(mask: Any, name: str) -> Any:
    """One of a mask's two fields, whether it is a row or a mapping."""
    return mask.get(name) if isinstance(mask, Mapping) else getattr(mask, name, None)


def _is_grid(size: Any) -> bool:
    """Whether a size is a grid: two whole numbers, none negative."""
    if isinstance(size, (str, bytes)) or not isinstance(size, Sequence) or len(size) != _GRID_DIMENSIONS:
        return False
    return all(
        isinstance(value, numbers.Integral) and not isinstance(value, bool) and int(value) >= 0 for value in size
    )


def _runs(counts: bytes) -> list[int] | None:
    """The run lengths a compressed string holds, or None when it is not one.

    The inverse of the encoding the module describes, as pycocotools reads it (`rleFrString`),
    except that a character outside the encoding or a run cut short refuses the string instead of
    reading something else.
    """
    runs: list[int] = []
    value = shift = 0
    for character in counts:
        bits = character - _FIRST_CHARACTER
        if not 0 <= bits < _CHARACTERS:
            return None
        value |= (bits & _VALUE_BITS) << shift
        shift += _BITS_PER_CHARACTER
        if bits & _CONTINUES_BIT:
            continue
        if bits & _SIGN_BIT:
            value |= -1 << shift
        if len(runs) >= _DELTA_FROM_RUN:
            value += runs[-_DELTA_STRIDE]
        runs.append(value)
        value = shift = 0
    return None if shift else runs
