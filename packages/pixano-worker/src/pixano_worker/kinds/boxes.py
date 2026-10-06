# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The geometry of detected boxes: where a detection lands, and whether a person's box covers it.

Pure functions, no dataset and no inference: the detection kind decides what to do, these say
where things are.
"""

from typing import Any, Sequence


#: A box as normalised corners: left, top, right, bottom, each in [0, 1].
Box = tuple[float, float, float, float]

#: The layout the boxes are written in: the one the annotation interface draws from.
BOX_FORMAT = "xywh"


def placed(
    corners: Sequence[Sequence[float]],
    scores: Sequence[float],
    classes: Sequence[str],
    size: tuple[int, int],
    wanted: Sequence[str] = (),
) -> tuple[list[list[float]], list[float], list[str]]:
    """Detections placed as the dataset stores them: normalised, top-left and size.

    The server answers in pixels, corners. A box is cut at the image's edges, and one those
    edges reduce to nothing is not one. Only the classes asked for are kept, when some are, case
    aside.

    Args:
        corners: Each box as left, top, right, bottom, in pixels.
        scores: Each box's score.
        classes: Each box's class.
        size: The image's width and height, in pixels.
        wanted: The classes to keep; all when empty.

    Returns:
        The kept boxes as normalised `xywh`, their scores, their classes.
    """
    width, height = size
    kept = {name.casefold() for name in wanted}
    boxes, kept_scores, kept_classes = [], [], []
    for (x1, y1, x2, y2), score, name in zip(corners, scores, classes, strict=True):
        if kept and str(name).casefold() not in kept:
            continue
        left, top = min(max(x1, 0), width), min(max(y1, 0), height)
        right, bottom = min(max(x2, 0), width), min(max(y2, 0), height)
        if right <= left or bottom <= top:
            continue
        boxes.append([left / width, top / height, (right - left) / width, (bottom - top) / height])
        kept_scores.append(float(score))
        kept_classes.append(str(name))
    return boxes, kept_scores, kept_classes


def normalized_corners(row: Any, width: int, height: int) -> Box:
    """A stored box as normalised corners, whatever layout it was stored in."""
    x, y, a, b = row.coords
    if row.format == BOX_FORMAT:
        a, b = x + a, y + b
    if not row.is_normalized:
        x, a = x / width, a / width
        y, b = y / height, b / height
    return x, y, a, b


def covered(coords: Sequence[float], name: str, protected: Sequence[tuple[Box, str]], threshold: float) -> bool:
    """Whether a person's box already says what this detection says.

    Args:
        coords: The detection, as normalised `xywh`.
        name: Its class.
        protected: The boxes it must not contradict, as normalised corners, with their class —
            empty for a box without one, which stands for any class.
        threshold: The intersection over union from which a box covers the detection.
    """
    x, y, w, h = coords
    box = (x, y, x + w, y + h)
    return any(
        (not other_class or other_class.casefold() == name.casefold()) and iou(box, other) >= threshold
        for other, other_class in protected
    )


def iou(first: Box, second: Box) -> float:
    """Intersection over union of two boxes given as corners."""
    width = min(first[2], second[2]) - max(first[0], second[0])
    height = min(first[3], second[3]) - max(first[1], second[1])
    if width <= 0 or height <= 0:
        return 0.0
    intersection = width * height
    union = _area(first) + _area(second) - intersection
    return intersection / union if union > 0 else 0.0


def _area(box: Box) -> float:
    return (box[2] - box[0]) * (box[3] - box[1])
