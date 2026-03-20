# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import warnings

from pydantic import model_validator
from typing_extensions import Self

from pixano.utils import issubclass_strict

from .entity_annotation import EntityAnnotation


class TextSpan(EntityAnnotation):
    """Designation of a text span in a text view."""

    mention: str
    spans_start: list[int]
    spans_end: list[int]

    @model_validator(mode="after")
    def _validate_fields(self) -> Self:
        if len(self.spans_start) != len(self.spans_end):
            raise ValueError("Spans offset lists should have the same length")
        if len(self.spans_start) == 0:
            warnings.warn("To ground a TextSpan in a text, spans offsets should not be empty", category=UserWarning)
        if not all(span[0] >= 0 and span[1] >= 0 for span in zip(self.spans_start, self.spans_end)):
            raise ValueError("Spans offset must be positive")
        if not all(span[0] <= span[1] for span in zip(self.spans_start, self.spans_end)):
            raise ValueError("End offsets must be greater or equal to their corresponding start offset")
        return self

    @classmethod
    def none(cls) -> Self:
        """Return a Lance-compatible empty text span."""
        return cls(
            id="",
            mention="",
            spans_start=[],
            spans_end=[],
        )

    @property
    def spans(self) -> list[tuple[int, int]]:
        """Get the list of zipped spans offsets."""
        return list(zip(self.spans_start, self.spans_end))

    @property
    def spans_length(self) -> list[int]:
        """Get the computed list of spans lengths."""
        return [end - start for start, end in zip(self.spans_start, self.spans_end)]


def is_text_span(cls: type, strict: bool = False) -> bool:
    """Check if a class is a ``TextSpan`` or subclass of ``TextSpan``."""
    return issubclass_strict(cls, TextSpan, strict)


def create_text_span(
    mention: str,
    spans_start: list[int],
    spans_end: list[int],
    id: str = "",
    record_id: str = "",
    view_id: str = "",
    entity_id: str = "",
    source_type: str = "",
    source_name: str = "",
    source_metadata: str = "{}",
) -> TextSpan:
    """Create a ``TextSpan`` instance."""
    return TextSpan(
        mention=mention,
        spans_start=spans_start,
        spans_end=spans_end,
        id=id,
        record_id=record_id,
        view_id=view_id,
        entity_id=entity_id,
        source_type=source_type,
        source_name=source_name,
        source_metadata=source_metadata,
    )
