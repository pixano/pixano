# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pydantic import model_validator

from pixano.utils import issubclass_strict

from ...types.schema_reference import EntityRef, ItemRef, SourceRef, ViewRef
from ..registry import _register_schema_internal
from .annotation import Annotation


@_register_schema_internal
class Classification(Annotation):
    """Classification at the media level (Image or Text).

    Attributes:
        labels: List of class names.
        confidences: List of prediction confidences.
    """

    labels: list[str]
    confidences: list[float]

    @model_validator(mode="after")
    def _validate_fields(self):
        if len(self.labels) != len(self.confidences):
            raise ValueError("Labels and confidences lists should have the same length")
        return self

    @classmethod
    def none(cls) -> "Classification":
        """Utility function to get a `None` equivalent.
        Should be removed as soon as Lance manages `None` value.

        Returns:
            "None" Classification.
        """
        return cls(
            id="",
            item=ItemRef.none(),
            view=ViewRef.none(),
            entity=EntityRef.none(),
            labels=[],
            confidences=[],
        )

    @property
    def predictions(self) -> list[tuple[str, float]]:
        """Get list of zipped predictions (labels and confidences)."""
        return list(zip(self.labels, self.confidences))


def is_classification(cls: type, strict: bool = False) -> bool:
    """Check if a class is a `Classification` or subclass of `Classification`."""
    return issubclass_strict(cls, Classification, strict)


def create_classification(
    labels: list[str],
    confidences: list[float],
    id: str = "",
    item_ref: ItemRef = ItemRef.none(),
    view_ref: ViewRef = ViewRef.none(),
    entity_ref: EntityRef = EntityRef.none(),
    source_ref: SourceRef = SourceRef.none(),
) -> Classification:
    """Create a `Classification` instance.

    Args:
        labels: List of class names.
        confidences: List of prediction confidences.
        id: `Classification` ID.
        item_ref: Item reference.
        view_ref: View reference.
        entity_ref: Entity reference.
        source_ref: Source reference.

    Returns:
        The created `Classification` instance.
    """
    return Classification(
        labels=labels,
        confidences=confidences,
        id=id,
        item_ref=item_ref,
        view_ref=view_ref,
        entity_ref=entity_ref,
        source_ref=source_ref,
    )
