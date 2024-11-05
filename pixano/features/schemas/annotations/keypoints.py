# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Literal

from pydantic import model_validator

from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation


@_register_schema_internal
class KeyPoints(Annotation):
    """A set of keypoints.

    Attributes:
        template_id: Id of the keypoint template.
        coords: List of 2D coordinates of the keypoints.
        states: Status for each keypoint. ("visible", "invisible", "hidden").
    """

    template_id: str
    coords: list[float]
    states: list[str]  # replace by features: list[dict] ?

    @model_validator(mode="after")
    def _validate_fields(self):
        if len(self.coords) % 2 != 0:
            raise ValueError("There must be an even number of coords")
        elif any(coord < 0 for coord in self.coords):
            raise ValueError("Coordinates must be positive")
        elif len(self.states) != len(self.coords) // 2:
            raise ValueError("There must be the same number of states than points")
        elif any(state not in ["visible", "invisible", "hidden"] for state in self.states):
            raise ValueError("States must be 'visible', 'invisible' or 'hidden'")
        return self

    @classmethod
    def none(cls) -> "KeyPoints":
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" KeyPoints.
        """
        return cls(
            id="",
            item=ItemRef.none(),
            view=ViewRef.none(),
            entity=EntityRef.none(),
            template_id="",
            coords=[0, 0],
            states=["invisible"],
        )

    def map_back2front_vertices(self) -> list:
        """Utility function to map back format for KeyPoint to front vertices format.

        Raises:
            ValueError: If keypoints is ill-formed.

        Returns:
            keypoint list for vertices front format.
        """
        # Check coords are even
        if len(self.coords) % 2 != 0:
            raise ValueError("There must be an even number of coords")

        result = []
        if self.states is not None:
            num_points = len(self.coords) // 2
            if len(self.states) != num_points:
                raise ValueError("There must be the same number of states than points")

            result = [
                {"x": x, "y": y, "features": {"state": state}}
                for (x, y), state in zip(zip(self.coords[0::2], self.coords[1::2]), self.states)
            ]
        else:
            result = [{"x": x, "y": y} for x, y in zip(self.coords[0::2], self.coords[1::2])]
        return result


@_register_schema_internal
class KeyPoints3D(Annotation):
    """A set of 3D keypoints.

    Attributes:
        template_id: id of keypoint template.
        coords: List of 3D coordinates of the keypoints.
        states: Status for each keypoint.
    """

    template_id: str
    coords: list[float]
    states: list[str]  # replace by features: list[dict] ?

    @model_validator(mode="after")
    def _validate_fields(self):
        if len(self.coords) % 3 != 0:
            raise ValueError("There must be a multiple of 3 coords")
        elif any(coord < 0 for coord in self.coords):
            raise ValueError("Coordinates must be positive")
        if len(self.states) != len(self.coords) // 3:
            raise ValueError("There must be the same number of states than points")
        elif any(state not in ["visible", "invisible", "hidden"] for state in self.states):
            raise ValueError("States must be 'visible', 'invisible' or 'hidden'")
        return self

    @classmethod
    def none(cls) -> "KeyPoints3D":
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" KeyPoints3D.
        """
        return cls(
            id="",
            item=ItemRef.none(),
            view=ViewRef.none(),
            entity=EntityRef.none(),
            template_id="",
            coords=[0, 0, 0],
            states=["visible"],
        )

    def map_back2front_vertices(self) -> list:
        """Utility function to map back format for KeyPoint3D to front vertices format.

        Warn:
            Not implemented for 3D keypoints.
        """
        raise NotImplementedError("Not implemented for 3D keypoints.")


def is_keypoints(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `KeyPoints` or subclass of `KeyPoints`."""
    return issubclass_strict(cls, KeyPoints, strict)


def is_keypoints3d(cls: type, strict: bool = False) -> bool:
    """Check if a class is `Keypoints3D` or a subclass of `Keypoints3D`."""
    return issubclass_strict(cls, KeyPoints3D, strict)


def create_keypoints(
    template_id: str,
    coords: list[float],
    states: list[str],
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
) -> KeyPoints:
    """Create a `KeyPoints` instance.

    Args:
        template_id: id of keypoint template.
        coords: List of 2D coordinates of the keypoints.
        states: Status for each keypoint. ("visible", "invisible", "hidden").
        id: Keypoints ID.
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.
        source_ref: Source reference.

    Returns:
        The created `KeyPoints` instance.
    """
    return KeyPoints(
        template_id=template_id,
        coords=coords,
        states=states,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
    )


def create_keypoints3d(
    template_id: str,
    coords: list[float],
    states: list[Literal["visible", "invisble", "hidden"]],
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
) -> KeyPoints3D:
    """Create a `KeyPoints3D` instance.

    Args:
        template_id: The id of the keypoint template.
        coords: The 3D coordinates of the keypoints.
        states: The visibility status for each keypoint.
        id: Keypoints3D ID.
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.
        source_ref: Source reference.

    Returns:
        The created `KeyPoints3D` instance.
    """
    return KeyPoints3D(
        template_id=template_id,
        coords=coords,
        states=states,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
    )
