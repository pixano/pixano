# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from pathlib import Path

from pydantic import BaseModel

from pixano.features import Image


class DatasetInfo(BaseModel):
    """Information of a dataset.

    Attributes:
        id: Dataset ID
        name: Dataset name
        description: Dataset description
        estimated_size: Dataset estimated size
        preview: Path to a preview thumbnail
    """

    id: str = ""
    name: str = ""
    description: str = ""
    size: str = "Unknown"
    preview: str = ""

    def to_json(self, json_fp: Path) -> None:
        """Writes the DatasetInfo object to a JSON file.

        Args:
            json_fp: The path to the file where the DatasetInfo object
                will be written.
        """
        json_fp.write_text(json.dumps(self.model_dump(), indent=4), encoding="utf-8")

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
        info = DatasetInfo.model_validate(info_json)

        return info

    @staticmethod
    def load_directory(
        directory: Path,
    ) -> list["DatasetInfo"]:
        """Load list of DatasetInfo from directory.

        Args:
            directory: Directory to load.

        Returns:
            the list of DatasetInfo.
        """
        library: list[DatasetInfo] = []

        # Browse directory
        for json_fp in sorted(directory.glob("*/info.json")):
            info = DatasetInfo.from_json(json_fp)
            info.preview = Image.open_url(
                str(json_fp.parent / "previews/dataset_preview.jpg"),
                json_fp.parent / "media",
            )  # TODO choose correct preview name / path / extension
            library.append(info)

        if library == []:
            raise FileNotFoundError(f"No dataset found in {directory}.")

        return library

    @staticmethod
    def load_id(id: str, directory: Path) -> "DatasetInfo":
        """Load a DatasetInfo from directory.

        Args:
            id: Dataset ID.
            directory: Directory to load.

        Returns:
            the DatasetInfo.
        """
        for json_fp in sorted(directory.glob("*/info.json")):
            info = DatasetInfo.from_json(json_fp)
            if info.id == id:
                info.preview = Image.open_url(
                    str(json_fp.parent / "previews/dataset_preview.jpg"),
                    json_fp.parent / "media",
                )  # TODO choose correct preview name / path / extension
                return info
        raise FileNotFoundError(f"No dataset found with ID {id}")
