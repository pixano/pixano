# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""JSONL v2 line grammar (spec §5): strict, closed vocabulary, no aliases, no inference.

Every model forbids unknown keys; annotation payload keys are exactly the
canonical schema field names, so the format is self-documenting against the
schema reference. Kind discrimination is explicit (``"kind"``); view payloads
are discriminated by the *declared* view kind, never by value shape.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


HEADER_KEY = "$pixano"
HEADER_VERSION = "jsonl/2"

# Kinds documented in the grammar but shipping later: 3D kinds with the 0.9
# 3D workstream, relation with the relation import path.
RESERVED_KINDS = frozenset({"bbox3d", "keypoints3d", "relation"})


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# ---------------------------------------------------------------------------
# Header line
# ---------------------------------------------------------------------------


class SourceSpec(_Strict):
    """Annotation source stamped on imported rows."""

    type: Literal["model", "human", "ground_truth", "other"] = "ground_truth"
    name: str = "import"


class BBoxDefaults(_Strict):
    """File-scoped bbox defaults (defined defaulting — never [0,1]-sniffing)."""

    format: Literal["xywh", "xyxy"] | None = None
    is_normalized: bool | None = None


class HeaderDefaults(_Strict):
    """File-scoped defaults declared by the optional header line."""

    bbox: BBoxDefaults = Field(default_factory=BBoxDefaults)
    source: SourceSpec = Field(default_factory=SourceSpec)


class HeaderLine(_Strict):
    """Optional first line: `{"$pixano": "jsonl/2", "defaults": {...}}`."""

    pixano: Literal["jsonl/2"] = Field(alias=HEADER_KEY)
    defaults: HeaderDefaults = Field(default_factory=HeaderDefaults)


# ---------------------------------------------------------------------------
# View payloads (validated against the DECLARED view kind)
# ---------------------------------------------------------------------------


class ImageViewPayload(_Strict):
    """Image view: `"path.jpg"` shorthand or `{"uri": ..., "width"?, "height"?}`."""

    uri: str
    width: int | None = None
    height: int | None = None


class VideoViewPayload(_Strict):
    """Video view: a time window inside the media file (spec §11.1)."""

    uri: str
    fps: float | None = None
    from_timestamp: float = 0.0
    to_timestamp: float = -1.0


class FrameItem(_Strict):
    """One explicit frame of a sequence view."""

    uri: str
    frame_index: int | None = None
    timestamp: float | None = None


class SequenceFramesPayload(_Strict):
    """Sequence view: explicit `frames` list or a lexicographically-ordered `frame_pattern`."""

    frames: list[FrameItem] | None = None
    frame_pattern: str | None = None
    fps: float | None = None

    @model_validator(mode="after")
    def _frames_xor_pattern(self) -> Self:
        if (self.frames is None) == (self.frame_pattern is None):
            raise ValueError("exactly one of 'frames' or 'frame_pattern' must be set")
        return self


class TextViewPayload(_Strict):
    """Text view: a file reference XOR inline content (kills the MEL doc-vs-code split)."""

    uri: str | None = None
    content: str | None = None

    @model_validator(mode="after")
    def _uri_xor_content(self) -> Self:
        if (self.uri is None) == (self.content is None):
            raise ValueError("exactly one of 'uri' or 'content' must be set")
        return self


class PointCloudViewPayload(_Strict):
    """Point-cloud view (viewer support tracked separately)."""

    uri: str


VIEW_PAYLOAD_MODELS: dict[str, type[_Strict]] = {
    "image": ImageViewPayload,
    "video": VideoViewPayload,
    "sequence_frames": SequenceFramesPayload,
    "text": TextViewPayload,
    "point_cloud": PointCloudViewPayload,
}


# ---------------------------------------------------------------------------
# Annotations (flat list, discriminated on "kind"; payload keys = schema fields)
# ---------------------------------------------------------------------------


class _AnnBase(_Strict):
    view: str | None = None  # required iff the schema declares more than one view
    id: str | None = None
    frame_index: int | None = None
    source: SourceSpec | None = None


class BBoxAnn(_AnnBase):
    """2D bounding box (`format`/`is_normalized` required unless header-defaulted)."""

    kind: Literal["bbox"]
    coords: list[float] = Field(min_length=4, max_length=4)
    format: Literal["xywh", "xyxy"] | None = None  # required unless header defaults supply it
    is_normalized: bool | None = None  # required unless header defaults supply it
    confidence: float = 1.0


class RLEPayload(_Strict):
    """Compressed RLE mask payload."""

    size: list[int] = Field(min_length=2, max_length=2)
    counts: str


class MaskAnn(_AnnBase):
    """Segmentation mask: RLE or hand-authorable polygons (converted at ingest)."""

    kind: Literal["mask"]
    rle: RLEPayload | None = None
    polygons: list[list[float]] | None = None  # hand-authorable; converted to RLE at ingest

    @model_validator(mode="after")
    def _rle_xor_polygons(self) -> Self:
        if (self.rle is None) == (self.polygons is None):
            raise ValueError("exactly one of 'rle' or 'polygons' must be set")
        return self


class KeypointsAnn(_AnnBase):
    """Keypoints against a registered template."""

    kind: Literal["keypoints"]
    template_id: str
    coords: list[float]
    states: list[str]

    @model_validator(mode="after")
    def _coords_match_states(self) -> Self:
        if len(self.coords) != 2 * len(self.states):
            raise ValueError("'coords' must hold exactly 2 values per state")
        return self


class MultiPathAnn(_AnnBase):
    """Multi-segment polyline/polygon annotation."""

    kind: Literal["multi_path"]
    coords: list[float]
    num_points: list[int]
    closed: bool


class TextSpanAnn(_AnnBase):
    """Character spans linking a mention inside a text view."""

    kind: Literal["text_span"]
    mention: str
    spans_start: list[int]
    spans_end: list[int]

    @model_validator(mode="after")
    def _spans_align(self) -> Self:
        if len(self.spans_start) != len(self.spans_end):
            raise ValueError("'spans_start' and 'spans_end' must have the same length")
        return self


class ClassificationAnn(_AnnBase):
    """Label classification with optional per-label confidences."""

    kind: Literal["classification"]
    labels: list[str]
    confidences: list[float] | None = None


Ann = Annotated[
    Union[BBoxAnn, MaskAnn, KeypointsAnn, MultiPathAnn, TextSpanAnn, ClassificationAnn],
    Field(discriminator="kind"),
]

KNOWN_KINDS = frozenset({"bbox", "mask", "keypoints", "multi_path", "text_span", "classification"})


# ---------------------------------------------------------------------------
# Entities, conversations, sidecars
# ---------------------------------------------------------------------------


class TrackletSpec(_Strict):
    """A tracked segment of an entity inside one view."""

    id: str | None = None
    view: str
    start_timestep: int
    end_timestep: int
    start_timestamp: float | None = None
    end_timestamp: float | None = None


class StateSpec(_Strict):
    """Per-frame dynamic entity state → `EntityDynamicState` rows."""

    frame_index: int
    attrs: dict[str, Any] = Field(default_factory=dict)


class EntitySpec(_Strict):
    """One annotated object with its annotations, tracklets, and per-frame states."""

    id: str | None = None
    parent_id: str | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)
    annotations: list[Ann] = Field(default_factory=list)
    tracklets: list[TrackletSpec] = Field(default_factory=list)
    states: list[StateSpec] = Field(default_factory=list)


class MessageSpec(_Strict):
    """One conversation turn (VQA)."""

    type: Literal["SYSTEM", "QUESTION", "ANSWER"]
    content: str
    question_type: str | None = None  # required for QUESTION turns (checked by the parser)
    choices: list[str] | None = None
    user: str | None = None
    views: list[str] | None = None


class ConversationSpec(_Strict):
    """An ordered list of conversation messages."""

    id: str | None = None
    messages: list[MessageSpec] = Field(min_length=1)


class SidecarSpec(_Strict):
    """Record-level annotation-file references (long videos stay hand-authorable)."""

    kind: Literal["mask", "bbox"]
    view: str
    pattern: str
    encoding: Literal["index_png", "track_json"]
    entity_map: dict[str, str] | Literal["auto"] = "auto"

    @model_validator(mode="after")
    def _encoding_matches_kind(self) -> Self:
        expected = "index_png" if self.kind == "mask" else "track_json"
        if self.encoding != expected:
            raise ValueError(f"sidecar kind '{self.kind}' requires encoding '{expected}'")
        return self


# ---------------------------------------------------------------------------
# The record line
# ---------------------------------------------------------------------------


class LineModel(_Strict):
    """One JSONL v2 line = one record (spec §5 grammar)."""

    id: str | None = None
    split: str | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)
    views: dict[str, Any]
    entities: list[EntitySpec] = Field(default_factory=list)
    conversations: list[ConversationSpec] = Field(default_factory=list)
    annotation_files: list[SidecarSpec] = Field(default_factory=list)


TOP_LEVEL_KEYS = frozenset(LineModel.model_fields.keys())
