# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Literal

from pydantic import model_validator

from pixano.datasets.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation


@_register_schema_internal
class KeyPoints(Annotation):
    """A set of keypoints.

    Attributes:
        template_id (str): id of keypoint template
        coords (list[float]): List of 2D coordinates of the keypoints.
        states (list[str]): Status for each keypoint. ("visible", "invisible", "hidden")
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
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            KeyPoints: "None" KeyPoints
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

        Args:
            keypoints (KeyPoints): Keypoints to map

        Raises:
            ValueError: if keypoints is ill-formed

        Returns:
            dict: keypoint list for vertices front format
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
        template_id (str): id of keypoint template
        coords (list[float]): List of 3D coordinates of the keypoints.
        states: Literal["visible", "invisible", "hidden"]: Status for each keypoint.
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
        """Utility function to get a None equivalent.
        Should be removed when Lance could manage None value.

        Returns:
            KeyPoints3D: "None" KeyPoints3D
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

        .. warning::
            Not implemented for 3D keypoints.
        """
        raise NotImplementedError("Not implemented for 3D keypoints.")


def is_keypoints(cls: type, strict: bool = False) -> bool:
    """Check if a class is a KeyPoints or subclass of KeyPoints."""
    return issubclass_strict(cls, KeyPoints, strict)


def is_keypoints3d(cls: type, strict: bool = False) -> bool:
    """Check if a class is Keypoints3D or a subclass of Keypoints3D."""
    return issubclass_strict(cls, KeyPoints3D, strict)


def create_keypoints(
    template_id: str,
    coords: list[float],
    states: list[str],
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
) -> KeyPoints:
    """Create a KeyPoints instance.

    Args:
        template_id (str): id of keypoint template
        coords (list[float]): List of 2D coordinates of the keypoints.
        states (list[str]): Status for each keypoint. ("visible", "invisible", "hidden")
        id (str, optional): Keypoints ID.
        item_ref (ItemRef, optional): Item reference.
        view_ref (ViewRef, optional): View reference.
        entity_ref (EntityRef, optional): Entity reference.

    Returns:
        KeyPoints: The created KeyPoints instance.
    """
    return KeyPoints(
        template_id=template_id,
        coords=coords,
        states=states,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
    )


def create_keypoints3d(
    template_id: str,
    coords: list[float],
    states: list[Literal["visible", "invisble", "hidden"]],
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
) -> KeyPoints3D:
    """Create a KeyPoints3D instance.

    Args:
        template_id (str): The id of the keypoint template.
        coords (list[float]): The 3D coordinates of the keypoints.
        states (list[Literal["visible", "invisble", "hidden"]]): The visibility status for each keypoint.
        id (str, optional): Keypoints3D ID.
        item_ref (ItemRef, optional): Item reference.
        view_ref (ViewRef, optional): View reference.
        entity_ref (EntityRef, optional): Entity reference.

    Returns:
        KeyPoints3D: The created KeyPoints3D instance.
    """
    return KeyPoints3D(
        template_id=template_id,
        coords=coords,
        states=states,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
    )
