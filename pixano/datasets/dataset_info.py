# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal, overload

from pydantic import BaseModel, field_serializer, field_validator

from pixano.datasets.workspaces import WorkspaceType
from pixano.features import Image


class DatasetInfo(BaseModel):
    """Information of a dataset.

    Attributes:
        id: Dataset ID. Must be unique.
        name: Dataset name.
        description: Dataset description.
        estimated_size: Dataset estimated size.
        preview: Path to a preview thumbnail.
        workspace: Workspace type.
    """

    id: str = ""
    name: str = ""
    description: str = ""
    size: str = "Unknown"
    preview: str = ""
    workspace: WorkspaceType = WorkspaceType.UNDEFINED

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

    def to_json(self, json_fp: Path) -> None:
        """Writes the DatasetInfo object to a JSON file.

        Args:
            json_fp: The path to the file where the DatasetInfo object
                will be written.
        """
        model_dumped = self.model_dump()
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
        info = DatasetInfo.model_validate(info_json)

        return info

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
                info.preview = Image.open_url(
                    str(json_fp.parent.resolve() / "previews/dataset_preview.jpg"),
                    Path("/"),
                )  # TODO choose correct preview name / path / extension
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
    def load_id(id: str, directory: Path, return_path: Literal[False] = False) -> "DatasetInfo": ...
    @overload
    @staticmethod
    def load_id(id: str, directory: Path, return_path: Literal[True] = True) -> tuple["DatasetInfo", Path]: ...
    @staticmethod
    def load_id(id: str, directory: Path, return_path: bool = False) -> tuple["DatasetInfo", Path] | "DatasetInfo":
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
                    info.preview = Image.open_url(
                        str(json_fp.parent / "previews/dataset_preview.jpg"),
                        json_fp.parent / "media",
                    )  # TODO choose correct preview name / path / extension
                except ValueError:
                    info.preview = ""
                return (info, json_fp.parent) if return_path else info
        raise FileNotFoundError(f"No dataset found with ID {id}")
