# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Sidecar annotation-file decoders (spec §5): normative shapes, decoded once per file.

Pure ports of the useful parts of the v1 ``processors.py`` with the heuristics
stripped: indexed PNGs split by pixel value (0 = background), per-frame track
JSON files with the now-normative ``{"view_name"?, "objects": [...]}`` shape.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import numpy as np
import PIL.Image
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ...errors import MetadataError
from ...plan import Provenance


class TrackObject(BaseModel):
    """One tracked object in a per-frame track_json file."""

    model_config = ConfigDict(extra="allow")  # extra keys become entity attrs downstream

    track_id: int
    bbox: list[float] = Field(min_length=4, max_length=4)
    category: str = ""


class TrackFrame(BaseModel):
    """The normative per-frame track_json payload."""

    model_config = ConfigDict(extra="forbid")

    view_name: str | None = None
    objects: list[TrackObject] = Field(default_factory=list)


def decode_track_json(path: Path) -> TrackFrame:
    """Decode one per-frame bbox-track JSON file (stem-matched to its frame)."""
    try:
        return TrackFrame.model_validate_json(path.read_text(encoding="utf-8"))
    except (OSError, ValidationError) as exc:
        raise MetadataError(f"Invalid track_json sidecar: {exc}", Provenance(file=str(path))) from None


def decode_index_png(path: Path, entity_map: dict[str, str] | Literal["auto"] = "auto") -> dict[str, "np.ndarray"]:
    """Decode one indexed PNG mask into per-entity binary masks.

    The PNG is decoded once; pixel value 0 is background, every other value is
    one object. ``entity_map`` maps pixel values (as strings) to entity keys;
    ``"auto"`` derives the key ``object_{value}``. Pixel values missing from an
    explicit map are an error — silent dropping is what v1 did.
    """
    try:
        with PIL.Image.open(path) as image:
            mask_array = np.array(image)
    except OSError as exc:
        raise MetadataError(f"Invalid index_png sidecar: {exc}", Provenance(file=str(path))) from None

    masks: dict[str, np.ndarray] = {}
    for pixel_value in sorted(int(v) for v in np.unique(mask_array) if int(v) != 0):
        if entity_map == "auto":
            entity_key = f"object_{pixel_value}"
        else:
            entity_key = entity_map.get(str(pixel_value), "")
            if not entity_key:
                raise MetadataError(
                    f"Pixel value {pixel_value} has no entry in entity_map (declared: {sorted(entity_map)}).",
                    Provenance(file=str(path)),
                )
        masks[entity_key] = (mask_array == pixel_value).astype(np.uint8)
    return masks
