# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Declarative import/export specs (spec §4) — the GUI-safe replacement for `--info file.py:attr`.

One Pydantic model built identically from a YAML/JSON file (`dataset.yaml`),
CLI flags, a GUI form (rendered from ``model_json_schema()``), or Python
kwargs. Workspace presets replace the folder builders' ``DEFAULT_INFO``
Python objects with data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from pixano.datasets.dataset_info import DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.schemas import (
    BBox,
    CompressedRLE,
    Entity,
    EntityDynamicState,
    Image,
    KeyPoints,
    Message,
    PointCloud,
    Record,
    SequenceFrame,
    Text,
    TextSpan,
    Tracklet,
    Video,
    View,
)

from .errors import SpecValidationError
from .plan import Provenance, fingerprint


class MediaPolicy(BaseModel):
    """How media is stored at import (spec §6): embedded bytes (default) or user-served URIs."""

    model_config = ConfigDict(extra="forbid")

    mode: Literal["embed", "uri"] = "embed"
    uri_prefix: str | None = None  # uri mode: prefix rewriting source-relative paths onto a served endpoint


class IdPolicy(BaseModel):
    """How row ids are produced (spec §8)."""

    model_config = ConfigDict(extra="forbid")

    policy: Literal["derive", "explicit"] = "derive"
    namespace: str | None = None  # defaults to source identity (dir name / hub repo id), resolved at analyze


class DatasetSpec(BaseModel):
    """Target-dataset metadata."""

    model_config = ConfigDict(extra="forbid")

    name: str = ""
    description: str = ""
    workspace: WorkspaceType = WorkspaceType.UNDEFINED


_VIEW_KINDS: dict[str, type[View]] = {
    "image": Image,
    "sequence_frames": SequenceFrame,
    "video": Video,
    "text": Text,
    "point_cloud": PointCloud,
}
_KIND_BY_VIEW: dict[type[View], str] = {cls: kind for kind, cls in _VIEW_KINDS.items()}

# Zero-values used when an attr declares neither a default nor required=true.
_ZERO_DEFAULTS: dict[str, Any] = {"str": "", "int": 0, "float": 0.0, "bool": False}


def _attr_field(attr_name: str, value: Any) -> tuple[Any, Any]:
    """Turn one shorthand attr into a pydantic (annotation, default) pair."""
    from pixano.datasets.dataset_schema import _MANIFEST_TYPES

    payload = {"type": value} if isinstance(value, str) else dict(value or {})
    type_name = payload.get("type")
    if not isinstance(type_name, str) or type_name not in _MANIFEST_TYPES:
        known = ", ".join(sorted(_MANIFEST_TYPES))
        raise SpecValidationError(
            f"Attr '{attr_name}': type {type_name!r} is not declarable in a spec (known: {known}). "
            "Nested dict/object attrs need a custom Python importer (spec §4)."
        )
    annotation: Any = _MANIFEST_TYPES[type_name]
    if payload.get("collection"):
        annotation = list[annotation]

    if payload.get("required"):
        return annotation, ...
    if "default" in payload:
        return annotation, payload["default"]
    if payload.get("collection"):
        # A plain [] default (pydantic v2 deep-copies) — default_factory does not
        # survive the info.json manifest dialect.
        return annotation, []
    if type_name in _ZERO_DEFAULTS:
        return annotation, _ZERO_DEFAULTS[type_name]
    return annotation, ...  # no sensible zero-value: the attr is required


def _synthesize(base: type, attrs: dict[str, Any]) -> type:
    """Create a named subclass carrying the shorthand attrs (manifest-serializable)."""
    from pydantic import create_model

    fields = {name: _attr_field(name, value) for name, value in attrs.items()}
    return create_model(f"Custom{base.__name__}", __base__=base, **fields)


def _attrs_from_schema(schema_cls: type) -> dict[str, Any]:
    """Inverse of `_synthesize`: recover the shorthand attrs of a subclass."""
    from pixano.datasets.dataset_schema import _MANIFEST_TYPES, _serialize_table_schema

    manifest = _serialize_table_schema(schema_cls)
    attrs: dict[str, Any] = {}
    for field_name, payload in manifest.get("fields", {}).items():
        type_name = payload.get("type")
        if type_name == "FixedSizeList" or type_name not in _MANIFEST_TYPES:
            raise SpecValidationError(
                f"Field '{field_name}' of {schema_cls.__name__} ({type_name!r}) is outside the declarative "
                "schema dialect; export it via ImportSpec.schema_manifest instead."
            )
        attr: dict[str, Any] = {"type": type_name}
        if payload.get("collection"):
            attr["collection"] = True
        if payload.get("required"):
            attr["required"] = True
        elif "default" in payload:
            attr["default"] = payload["default"]
        attrs[field_name] = attr
    return attrs


class SchemaSpec(BaseModel):
    """Hand-authorable schema shorthand (spec §4), compiled onto the manifest dialect."""

    model_config = ConfigDict(extra="forbid")

    views: dict[str, Any] = Field(default_factory=dict)
    record: dict[str, Any] = Field(default_factory=dict)
    entity: dict[str, Any] = Field(default_factory=dict)
    entity_dynamic_state: dict[str, Any] | None = None
    annotations: list[str] | dict[str, Any] = Field(default_factory=list)

    def compile(self, workspace: WorkspaceType = WorkspaceType.UNDEFINED) -> DatasetInfo:
        """Compile the shorthand into a `DatasetInfo` (preset-seeded, spec-overridden)."""
        from pixano.schemas import supported_dataset_info_slots
        from pixano.schemas.table_names import supported_slot_schema

        try:
            info = workspace_preset(workspace)
        except SpecValidationError:
            info = DatasetInfo(workspace=workspace, record=Record, entity=Entity, views={"image": Image})

        payload: dict[str, Any] = {
            "name": info.name,
            "workspace": workspace,
            "record": info.record,
            "entity": info.entity,
            "entity_dynamic_state": info.entity_dynamic_state,
            "views": dict(info.views),
        }
        for slot in supported_dataset_info_slots():
            if slot in ("record", "entity", "entity_dynamic_state"):
                continue
            payload[slot] = getattr(info, slot)

        if self.record.get("attrs"):
            payload["record"] = _synthesize(Record, self.record["attrs"])
        if self.entity.get("attrs"):
            payload["entity"] = _synthesize(Entity, self.entity["attrs"])
        if self.entity_dynamic_state is not None:
            payload["entity_dynamic_state"] = (
                _synthesize(EntityDynamicState, self.entity_dynamic_state["attrs"])
                if self.entity_dynamic_state.get("attrs")
                else EntityDynamicState
            )

        if self.annotations:
            slot_specs = (
                {slot: {} for slot in self.annotations} if isinstance(self.annotations, list) else self.annotations
            )
            annotation_slots = set(supported_dataset_info_slots()) - {"record", "entity", "entity_dynamic_state"}
            for slot in annotation_slots:
                payload[slot] = None  # the spec's annotation list replaces the preset's
            for slot, slot_spec in slot_specs.items():
                if slot not in annotation_slots:
                    known = ", ".join(sorted(annotation_slots))
                    raise SpecValidationError(f"Unknown annotation slot '{slot}' (known: {known}).")
                base = supported_slot_schema(slot)
                attrs = (slot_spec or {}).get("attrs") if isinstance(slot_spec, dict) else None
                payload[slot] = _synthesize(base, attrs) if attrs else base

        if self.views:
            views: dict[str, type[View]] = {}
            kind_classes: dict[str, type[View]] = {}
            for logical_name, view_spec in self.views.items():
                view_payload = {"kind": view_spec} if isinstance(view_spec, str) else dict(view_spec or {})
                kind = view_payload.get("kind")
                if kind not in _VIEW_KINDS:
                    known = ", ".join(sorted(_VIEW_KINDS))
                    raise SpecValidationError(f"View '{logical_name}': unknown kind {kind!r} (known: {known}).")
                raw_attrs = view_payload.get("attrs") or {}
                if not isinstance(raw_attrs, dict):
                    raise SpecValidationError(f"View '{logical_name}': attrs must be a mapping.")
                view_attrs: dict[str, Any] = dict(raw_attrs)
                if kind not in kind_classes:
                    kind_classes[kind] = (
                        _synthesize(_VIEW_KINDS[kind], view_attrs) if view_attrs else _VIEW_KINDS[kind]
                    )
                elif view_attrs and _attrs_from_schema(kind_classes[kind]) != _attrs_from_schema(
                    _synthesize(_VIEW_KINDS[kind], view_attrs)
                ):
                    raise SpecValidationError(
                        f"Views of kind '{kind}' share one table and must declare identical attrs."
                    )
                views[logical_name] = kind_classes[kind]
            payload["views"] = views

        return DatasetInfo.model_validate(payload)

    @classmethod
    def from_dataset_info(cls, info: DatasetInfo) -> "SchemaSpec":
        """Inverse of :meth:`compile`: recover the shorthand from a `DatasetInfo`."""
        from pixano.schemas import supported_dataset_info_slots

        views: dict[str, Any] = {}
        for logical_name, view_cls in info.views.items():
            base = next((b for b in view_cls.__mro__ if b in _KIND_BY_VIEW), None)
            if base is None:
                raise SpecValidationError(
                    f"View '{logical_name}' ({view_cls.__name__}) is outside the declarative dialect."
                )
            view_payload: dict[str, Any] = {"kind": _KIND_BY_VIEW[base]}
            if view_cls is not base:
                view_payload["attrs"] = _attrs_from_schema(view_cls)
            views[logical_name] = view_payload

        annotations: dict[str, Any] = {}
        for slot in supported_dataset_info_slots():
            if slot in ("record", "entity", "entity_dynamic_state"):
                continue
            schema_cls = getattr(info, slot)
            if schema_cls is None:
                continue
            from pixano.schemas.table_names import supported_slot_schema

            base = supported_slot_schema(slot)
            annotations[slot] = {"attrs": _attrs_from_schema(schema_cls)} if schema_cls is not base else {}

        return cls(
            views=views,
            record={"attrs": _attrs_from_schema(info.record)} if info.record and info.record is not Record else {},
            entity={"attrs": _attrs_from_schema(info.entity)} if info.entity and info.entity is not Entity else {},
            entity_dynamic_state=(
                None
                if info.entity_dynamic_state is None
                else (
                    {"attrs": _attrs_from_schema(info.entity_dynamic_state)}
                    if info.entity_dynamic_state is not EntityDynamicState
                    else {}
                )
            ),
            annotations=(sorted(annotations) if all(not payload for payload in annotations.values()) else annotations),
        )


class ImportSpec(BaseModel):
    """Declarative description of one import job (spec §4)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    pixano: Literal[2] = 2
    dataset: DatasetSpec = Field(default_factory=DatasetSpec)
    format: str = "auto"
    media: MediaPolicy = Field(default_factory=MediaPolicy)
    schema_: SchemaSpec | None = Field(default=None, alias="schema")
    schema_manifest: dict[str, Any] | None = None
    defaults: dict[str, Any] = Field(default_factory=dict)
    ids: IdPolicy = Field(default_factory=IdPolicy)
    mode: Literal["create", "overwrite", "add"] = "create"
    options: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> "ImportSpec":
        """Load a spec from a `dataset.yaml` file with provenance-carrying errors."""
        provenance = Provenance(file=str(path))
        try:
            payload = yaml.safe_load(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise SpecValidationError("Spec file not found.", provenance) from None
        except yaml.YAMLError as exc:
            raise SpecValidationError(f"Invalid YAML: {exc}", provenance) from None
        if not isinstance(payload, dict):
            raise SpecValidationError("Spec file must contain a YAML mapping.", provenance)
        try:
            return cls.model_validate(payload)
        except ValidationError as exc:
            raise SpecValidationError(f"Invalid import spec: {exc}", provenance) from None

    def fingerprint(self) -> str:
        """Stable fingerprint of the spec (identity of the import configuration)."""
        return fingerprint(self.model_dump(mode="json", by_alias=True))


class ExportSpec(BaseModel):
    """Declarative description of one export job (spec §10)."""

    model_config = ConfigDict(extra="forbid")

    format: str
    destination: str
    media: Literal["files", "uris"] = "files"
    options: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Workspace presets — data transcription of the folder builders' DEFAULT_INFOs
# ---------------------------------------------------------------------------


class MelEntity(Entity):
    """Entity used by image-text entity-linking (MEL) datasets."""

    name: str = ""


def workspace_preset(workspace: WorkspaceType) -> DatasetInfo:
    """Return a fresh default `DatasetInfo` for a workspace (spec §4).

    These replace the deleted folder builders' ``DEFAULT_INFO`` objects: they
    pre-fill views and annotation slots so a minimal spec (name + workspace)
    is enough to import the common cases.
    """
    if workspace == WorkspaceType.IMAGE:
        return DatasetInfo(
            workspace=WorkspaceType.IMAGE,
            record=Record,
            entity=Entity,
            bbox=BBox,
            keypoint=KeyPoints,
            views={"image": Image},
        )
    if workspace == WorkspaceType.VIDEO:
        return DatasetInfo(
            workspace=WorkspaceType.VIDEO,
            record=Record,
            entity=Entity,
            entity_dynamic_state=EntityDynamicState,
            bbox=BBox,
            keypoint=KeyPoints,
            tracklet=Tracklet,
            views={"image": SequenceFrame},
        )
    if workspace == WorkspaceType.IMAGE_VQA:
        return DatasetInfo(
            workspace=WorkspaceType.IMAGE_VQA,
            record=Record,
            entity=Entity,
            message=Message,
            views={"image": Image},
        )
    if workspace == WorkspaceType.IMAGE_TEXT_ENTITY_LINKING:
        return DatasetInfo(
            workspace=WorkspaceType.IMAGE_TEXT_ENTITY_LINKING,
            record=Record,
            entity=MelEntity,
            text_span=TextSpan,
            bbox=BBox,
            mask=CompressedRLE,
            views={"image": Image, "text": Text},
        )
    raise SpecValidationError(f"No workspace preset for workspace '{workspace.value}'.")


def resolve_dataset_info(spec: ImportSpec) -> DatasetInfo:
    """Resolve the target `DatasetInfo` for a spec (spec §4).

    Priority: verbatim ``schema_manifest`` payloads (the round-trip escape for
    schemas outside the authoring dialect) > the ``schema`` shorthand compiled
    onto the workspace preset > the bare workspace preset.
    """
    if spec.schema_manifest is not None:
        from pixano.datasets.dataset_schema import _deserialize_table_schema

        payload: dict[str, Any] = {"workspace": spec.dataset.workspace}
        for slot_name, manifest in spec.schema_manifest.items():
            if slot_name == "views":
                payload["views"] = {
                    logical_name: _deserialize_table_schema(view_manifest)
                    for logical_name, view_manifest in manifest.items()
                }
            else:
                payload[slot_name] = _deserialize_table_schema(manifest)
        try:
            return DatasetInfo.model_validate(payload)
        except Exception as exc:
            raise SpecValidationError(f"Invalid schema_manifest: {exc}") from None
    if spec.schema_ is not None:
        return spec.schema_.compile(spec.dataset.workspace)
    return workspace_preset(spec.dataset.workspace)
