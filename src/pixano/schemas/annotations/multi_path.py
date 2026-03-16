# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import model_validator
from typing_extensions import Self

from pixano.utils import issubclass_strict

from .per_frame_annotation import PerFrameAnnotation


class MultiPath(PerFrameAnnotation):
    """A collection of 2D paths (polylines or polygon rings).

    Inspired by GeoJSON, both multi-polygons and multi-linestrings share the
    same data layout.  All coordinates are stored in a single flat list, and
    ``num_points`` records how many points belong to each sub-path.

    The ``is_closed`` flag distinguishes between the two semantics:

    * ``is_closed=True``  -> multi-polygon  (each sub-path is a closed ring)
    * ``is_closed=False`` -> multi-linestring (each sub-path is an open polyline)

    Attributes:
        coords: Flat list of normalised 2-D coordinates
            ``[x1, y1, x2, y2, ...]`` for **all** sub-paths concatenated.
        num_points: Number of points in each sub-path.  For example
            ``[4, 3]`` means two sub-paths with 4 and 3 points respectively.
            ``sum(num_points) * 2`` must equal ``len(coords)``.
        is_closed: Whether the paths represent closed polygons (``True``)
            or open polylines (``False``).
    """

    coords: list[float]
    num_points: list[int]
    is_closed: bool

    @model_validator(mode="after")
    def _validate_fields(self) -> Self:
        if len(self.coords) % 2 != 0:
            raise ValueError(f"coords must have an even number of elements (x,y pairs), got {len(self.coords)}.")
        total_points = len(self.coords) // 2
        declared_points = sum(self.num_points)
        if declared_points != total_points:
            raise ValueError(
                f"sum(num_points)={declared_points} does not match total coordinate pairs={total_points}."
            )
        min_pts = 3 if self.is_closed else 2
        kind = "polygon" if self.is_closed else "polyline"
        for idx, n in enumerate(self.num_points):
            if n < min_pts:
                raise ValueError(f"Sub-path {idx} has {n} point(s); a {kind} requires at least {min_pts}.")
        if self.coords and not all(0.0 <= c <= 1.0 for c in self.coords):
            raise ValueError("All coordinates must be normalised to the [0, 1] range.")
        return self

    @classmethod
    def none(cls) -> Self:
        """Return a Lance-compatible 'null' ``MultiPath``.

        Should be removed once Lance manages ``None`` values natively.
        """
        return cls(
            id="",
            coords=[],
            num_points=[],
            is_closed=False,
        )


def is_multi_path(cls: type, strict: bool = False) -> bool:
    """Check whether *cls* is ``MultiPath`` or a subclass of it."""
    return issubclass_strict(cls, MultiPath, strict)


def create_multi_path(
    id: str = "",
    coords: list[float] | None = None,
    num_points: list[int] | None = None,
    is_closed: bool = False,
    entity_id: str = "",
    view_id: str = "",
    source_type: str = "",
    source_name: str = "",
    source_metadata: str = "{}",
    tracklet_id: str = "",
    entity_dynamic_state_id: str = "",
    frame_id: str = "",
    frame_index: int = -1,
) -> MultiPath:
    """Factory function that mirrors ``create_bbox``, ``create_compressed_rle``, etc."""
    return MultiPath(
        id=id,
        coords=coords if coords is not None else [],
        num_points=num_points if num_points is not None else [],
        is_closed=is_closed,
        entity_id=entity_id,
        view_id=view_id,
        source_type=source_type,
        source_name=source_name,
        source_metadata=source_metadata,
        tracklet_id=tracklet_id,
        entity_dynamic_state_id=entity_dynamic_state_id,
        frame_id=frame_id,
        frame_index=frame_index,
    )
