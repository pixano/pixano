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
from pydantic import BaseModel, field_serializer, field_validator, model_validator
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
from pixano.schemas import Record, RecordComponent, is_record
from pixano.schemas.schema_group import SchemaGroup, schema_to_group


class DatasetInfo(BaseModel):
    """Information and schema definition of a dataset.

    The ``tables`` mapping stores the table name to schema class mapping.
    Exactly one table must map to a :class:`Record` subclass (the main table,
    always named ``"record"``).  All other tables must map to
    :class:`RecordComponent` subclasses.

    Attributes:
        id: Dataset ID. Must be unique.
        name: Dataset name.
        description: Dataset description.
        size: Dataset estimated size.
        preview: Path to a preview thumbnail.
        workspace: Workspace type.
        storage_mode: How media data is stored.
        tables: Mapping of table name to schema class.
    """

    id: str = ""
    name: str = ""
    description: str = ""
    size: str = "Unknown"
    preview: str = ""
    workspace: WorkspaceType = WorkspaceType.UNDEFINED
    storage_mode: Literal["filesystem", "embedded", "mixed"] = "filesystem"
    tables: dict[str, type[LanceModel]] = {}

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

    @model_validator(mode="after")
    def _validate_tables(self) -> Self:
        """Validate that tables contains exactly one Record and the rest are RecordComponent."""
        if not self.tables:
            # Empty tables is allowed (e.g. when creating DatasetInfo before tables are added)
            return self

        record_count = 0
        for table_name, schema_cls in self.tables.items():
            if is_record(schema_cls):
                if table_name != "record":
                    raise ValueError(f"The Record table must be named 'record', got '{table_name}'.")
                record_count += 1
            else:
                if not (isinstance(schema_cls, type) and issubclass(schema_cls, RecordComponent)):
                    raise ValueError(
                        f"Table '{table_name}' schema must be a RecordComponent subclass, got {schema_cls}."
                    )
        if record_count != 1:
            raise ValueError(f"Exactly one Record table is required, found {record_count}.")
        return self

    # ------------------------------------------------------------------
    # Derived properties
    # ------------------------------------------------------------------

    @property
    def groups(self) -> dict[SchemaGroup, set[str]]:
        """Compute schema groups dynamically from the tables mapping."""
        groups: dict[SchemaGroup, set[str]] = {g: set() for g in SchemaGroup if g != SchemaGroup.SOURCE}
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
        model_dumped = self.model_dump(exclude={"tables"})
        # Serialize tables using the schema serialization helpers
        if self.tables:
            model_dumped["tables"] = {
                table_name: _serialize_table_schema(schema_cls) for table_name, schema_cls in self.tables.items()
            }
        else:
            model_dumped["tables"] = {}
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

        # Deserialize tables
        tables_json = info_json.pop("tables", {})
        tables: dict[str, type[LanceModel]] = {}
        for table_name, schema_payload in tables_json.items():
            tables[table_name] = _deserialize_table_schema(schema_payload)

        info = DatasetInfo.model_validate({**info_json, "tables": tables})
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
