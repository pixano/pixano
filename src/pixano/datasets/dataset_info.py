# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, overload

import PIL.Image
from lancedb.pydantic import LanceModel
from pydantic import BaseModel, Field, field_serializer, field_validator, model_validator
from typing_extensions import Self

# ---------------------------------------------------------------------------
# Schema serialization helpers (moved from dataset_schema.py)
# ---------------------------------------------------------------------------
from pixano.datasets.dataset_schema import (
    _deserialize_table_schema,
    _serialize_table_schema,
)
from pixano.datasets.workspaces import WorkspaceType
from pixano.features.utils.image import get_image_thumbnail, image_to_base64
from pixano.schemas import (
    BBox,
    CompressedRLE,
    Entity,
    EntityDynamicState,
    KeyPoints,
    Message,
    PDF,
    Record,
    RecordComponent,
    SequenceFrame,
    Text,
    TextSpan,
    Tracklet,
    View,
    canonical_table_name_for_schema,
    canonical_table_name_for_slot,
    is_supported_view_schema,
    supported_dataset_info_slots,
)
from pixano.schemas.schema_group import SchemaGroup, schema_to_group


_DATASET_INFO_SLOT_TYPES: dict[str, type[LanceModel]] = {
    "record": Record,
    "entity": Entity,
    "entity_dynamic_state": EntityDynamicState,
    "bbox": BBox,
    "mask": CompressedRLE,
    "keypoint": KeyPoints,
    "tracklet": Tracklet,
    "message": Message,
    "text_span": TextSpan,
}


class DatasetInfo(BaseModel):
    """Information and schema definition of a dataset.

    Users declare schemas by role and Pixano derives canonical physical table
    names internally. Multiple logical views may share the same physical table
    and are distinguished by the view ``logical_name`` field.

    Attributes:
        id: Dataset ID. Must be unique.
        name: Dataset name.
        description: Dataset description.
        size: Dataset estimated size.
        preview: Path to a preview thumbnail.
        workspace: Workspace type.
        storage_mode: How media data is stored.
        record: Main record schema.
        entity: Entity schema.
        entity_dynamic_state: Entity dynamic state schema.
        bbox: Bounding box schema.
        mask: Mask schema.
        keypoint: Keypoint schema.
        tracklet: Tracklet schema.
        message: Message schema.
        text_span: Text span schema.
        views: Mapping of logical view names to view schema classes.
    """

    id: str = ""
    name: str = ""
    description: str = ""
    size: str = "Unknown"
    preview: str = ""
    workspace: WorkspaceType = WorkspaceType.UNDEFINED
    storage_mode: Literal["filesystem", "embedded", "mixed"] = "filesystem"
    record: type[Record] | None = None
    entity: type[Entity] | None = None
    entity_dynamic_state: type[EntityDynamicState] | None = None
    bbox: type[BBox] | None = None
    mask: type[CompressedRLE] | None = None
    keypoint: type[KeyPoints] | None = None
    tracklet: type[Tracklet] | None = None
    message: type[Message] | None = None
    text_span: type[TextSpan] | None = None
    views: dict[str, type[View]] = Field(default_factory=dict)
    tables: dict[str, type[LanceModel]] = Field(default_factory=dict, exclude=True)

    model_config = {"arbitrary_types_allowed": True}

    # ------------------------------------------------------------------
    # Validators
    # ------------------------------------------------------------------

    @field_serializer("workspace")
    def serialize_workspace(self, workspace: WorkspaceType):
        """Dump workspace as string value, not enum."""
        return workspace.value

    @field_validator("id", mode="after")
    @classmethod
    def _id_validator(cls, v: str) -> str:
        if " " in v:
            raise ValueError("id must not contain spaces")
        return v

    @model_validator(mode="before")
    @classmethod
    def _normalize_input(cls, data: object) -> object:
        if not isinstance(data, dict):
            return data

        normalized = dict(data)
        if normalized.get("tables"):
            raise ValueError("DatasetInfo no longer accepts a 'tables' mapping. Use fixed schema slots and 'views'.")
        return normalized

    @model_validator(mode="after")
    def _validate_tables(self) -> Self:
        """Validate schema slots and derive canonical physical tables."""
        slot_values: dict[str, type[LanceModel] | None] = {
            slot_name: getattr(self, slot_name) for slot_name in supported_dataset_info_slots()
        }

        for slot_name, schema_cls in slot_values.items():
            if schema_cls is None:
                continue
            expected_schema = _DATASET_INFO_SLOT_TYPES[slot_name]
            if not (isinstance(schema_cls, type) and issubclass(schema_cls, expected_schema)):
                raise ValueError(
                    f"DatasetInfo.{slot_name} must be a subclass of {expected_schema.__name__}, got {schema_cls}."
                )

        derived_tables: dict[str, type[LanceModel]] = {}
        for slot_name, schema_cls in slot_values.items():
            if schema_cls is None:
                continue
            table_name = canonical_table_name_for_slot(slot_name)
            derived_tables[table_name] = schema_cls

        for logical_name, schema_cls in self.views.items():
            if not logical_name.strip():
                raise ValueError("View logical names must be non-empty.")
            if not (
                isinstance(schema_cls, type) and issubclass(schema_cls, View) and is_supported_view_schema(schema_cls)
            ):
                raise ValueError(
                    "DatasetInfo.views values must be subclasses of Image, SequenceFrame, Text, or PDF. "
                    f"Got {schema_cls} for logical view '{logical_name}'."
                )
            table_name = canonical_table_name_for_schema(schema_cls)
            existing_schema = derived_tables.get(table_name)
            if existing_schema is not None and existing_schema is not schema_cls:
                raise ValueError(
                    f"Logical views sharing table '{table_name}' must use the same schema class. "
                    f"Got {existing_schema} and {schema_cls}."
                )
            derived_tables[table_name] = schema_cls

        if derived_tables:
            if "records" not in derived_tables:
                raise ValueError("A record schema is required when defining dataset tables.")
            for table_name, schema_cls in derived_tables.items():
                if not (isinstance(schema_cls, type) and issubclass(schema_cls, LanceModel)):
                    raise ValueError(f"Table '{table_name}' schema must be a LanceModel subclass, got {schema_cls}.")
                if table_name != "records" and not issubclass(schema_cls, RecordComponent):
                    raise ValueError(
                        f"Table '{table_name}' schema must be a RecordComponent subclass, got {schema_cls}."
                    )

        self.tables = derived_tables
        return self

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def groups(self) -> dict[SchemaGroup, set[str]]:
        """Compute schema groups dynamically from the tables mapping."""
        groups: dict[SchemaGroup, set[str]] = {g: set() for g in SchemaGroup}
        for table_name, schema_cls in self.tables.items():
            try:
                group = schema_to_group(schema_cls)
                if group in groups:
                    groups[group].add(table_name)
            except ValueError:
                pass
        return groups

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_json(self, json_fp: Path) -> None:
        """Writes the DatasetInfo object to a JSON file.

        Args:
            json_fp: The path to the file where the DatasetInfo object
                will be written.
        """
        model_dumped = self.model_dump(exclude={"tables", *supported_dataset_info_slots(), "views"})
        for slot_name in supported_dataset_info_slots():
            schema_cls = getattr(self, slot_name)
            model_dumped[slot_name] = _serialize_table_schema(schema_cls) if schema_cls is not None else None
        model_dumped["views"] = {
            logical_name: _serialize_table_schema(schema_cls) for logical_name, schema_cls in self.views.items()
        }
        json_fp.write_text(json.dumps(model_dumped, indent=4), encoding="utf-8")

    @staticmethod
    def from_json(
        json_fp: Path,
    ) -> "DatasetInfo":
        """Read DatasetInfo from JSON file.

        Args:
            json_fp: JSON file path.

        Returns:
            the dataset info object.
        """
        info_json = json.loads(json_fp.read_text(encoding="utf-8"))

        info_json["workspace"] = (
            WorkspaceType(info_json["workspace"]) if "workspace" in info_json else WorkspaceType.UNDEFINED
        )

        for slot_name in supported_dataset_info_slots():
            schema_payload = info_json.get(slot_name)
            if schema_payload is not None:
                info_json[slot_name] = _deserialize_table_schema(schema_payload)
        views_json = info_json.get("views", {})
        info_json["views"] = {
            logical_name: _deserialize_table_schema(schema_payload)
            for logical_name, schema_payload in views_json.items()
        }

        info = DatasetInfo.model_validate(info_json)
        return info

    # ------------------------------------------------------------------
    # Directory / ID loading helpers
    # ------------------------------------------------------------------

    @overload
    @staticmethod
    def load_directory(
        directory: Path,
        return_path: Literal[False] = False,
    ) -> list["DatasetInfo"]: ...
    @overload
    @staticmethod
    def load_directory(
        directory: Path,
        return_path: Literal[True],
    ) -> list[tuple["DatasetInfo", Path]]: ...
    @staticmethod
    def load_directory(
        directory: Path,
        return_path: bool = False,
    ) -> list[tuple["DatasetInfo", Path]] | list["DatasetInfo"]:
        """Load list of DatasetInfo from directory.

        Args:
            directory: Directory to load.
            return_path: Return the paths of the datasets.

        Returns:
            The list of DatasetInfo and the paths of the datasets.
        """
        library: list[DatasetInfo] | list[tuple[DatasetInfo, Path]] = []

        # Browse directory
        for json_fp in sorted(directory.glob("*/info.json")):
            info: DatasetInfo = DatasetInfo.from_json(json_fp)
            try:
                preview_path = json_fp.parent.resolve() / "previews/dataset_preview.jpg"
                if not preview_path.exists():
                    from pixano.datasets.dataset import Dataset

                    dataset = Dataset(json_fp.parent)
                    info.preview = dataset.generate_preview()
                else:
                    thumb = get_image_thumbnail(PIL.Image.open(preview_path), (350, 150))
                    info.preview = image_to_base64(thumb, "JPEG")
            except Exception:  # TODO: specify exception URL and Value
                info.preview = ""
            if return_path:
                library.append((info, json_fp.parent))  #  type: ignore[arg-type]
            else:
                library.append(info)

        if library == []:
            raise FileNotFoundError(f"No dataset found in {directory}.")

        return library

    @overload
    @staticmethod
    def load_id(
        id: str,
        directory: Path,
        return_path: Literal[False] = False,
    ) -> "DatasetInfo": ...
    @overload
    @staticmethod
    def load_id(
        id: str,
        directory: Path,
        return_path: Literal[True] = True,
    ) -> tuple["DatasetInfo", Path]: ...
    @staticmethod
    def load_id(
        id: str,
        directory: Path,
        return_path: bool = False,
    ) -> tuple["DatasetInfo", Path] | "DatasetInfo":
        """Load a specific DatasetInfo from directory.

        Args:
            id: The ID of the dataset to load.
            directory: Directory to load.
            return_path: Return the path of the dataset.

        Returns:
            The DatasetInfo.
        """
        for json_fp in directory.glob("*/info.json"):
            info = DatasetInfo.from_json(json_fp)
            if info.id == id:
                try:
                    preview_path = json_fp.parent / "previews/dataset_preview.jpg"
                    if not preview_path.exists():
                        from pixano.datasets.dataset import Dataset

                        dataset = Dataset(json_fp.parent)
                        info.preview = dataset.generate_preview()
                    else:
                        thumb = get_image_thumbnail(PIL.Image.open(preview_path), (350, 150))
                        info.preview = image_to_base64(thumb, "JPEG")
                except Exception:
                    info.preview = ""
                return (info, json_fp.parent) if return_path else info
        raise FileNotFoundError(f"No dataset found with ID {id}")
