# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Declarative import/export specs (spec §4) — the GUI-safe replacement for `--info file.py:attr`.

One Pydantic model built identically from a YAML/JSON file (`pixano.yaml`),
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
    Record,
    SequenceFrame,
    Text,
    TextSpan,
    Tracklet,
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


class SchemaSpec(BaseModel):
    """Hand-authorable schema shorthand (spec §4).

    Held as raw data in this slice; ``compile()`` into a ``DatasetInfo`` lands
    with the pixano_jsonl format (plan P2.1).
    """

    model_config = ConfigDict(extra="forbid")

    views: dict[str, Any] = Field(default_factory=dict)
    record: dict[str, Any] = Field(default_factory=dict)
    entity: dict[str, Any] = Field(default_factory=dict)
    annotations: list[Any] | dict[str, Any] = Field(default_factory=list)

    def compile(self, workspace: WorkspaceType = WorkspaceType.UNDEFINED) -> DatasetInfo:
        """Compile the shorthand into a DatasetInfo. Implemented in plan P2.1."""
        raise NotImplementedError("SchemaSpec.compile lands with the pixano_jsonl format (plan P2.1).")


class ImportSpec(BaseModel):
    """Declarative description of one import job (spec §4)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    pixano: Literal[2] = 2
    dataset: DatasetSpec = Field(default_factory=DatasetSpec)
    format: str = "auto"
    media: MediaPolicy = Field(default_factory=MediaPolicy)
    schema_: SchemaSpec | None = Field(default=None, alias="schema")
    defaults: dict[str, Any] = Field(default_factory=dict)
    ids: IdPolicy = Field(default_factory=IdPolicy)
    mode: Literal["create", "overwrite", "add"] = "create"
    options: dict[str, Any] = Field(default_factory=dict)

    @classmethod
    def from_yaml(cls, path: Path) -> "ImportSpec":
        """Load a spec from a `pixano.yaml` file with provenance-carrying errors."""
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
