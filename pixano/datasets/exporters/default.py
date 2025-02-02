# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import json
from typing import Any

from fastapi.encoders import jsonable_encoder

from pixano.features import (
    BaseSchema,
    SchemaGroup,
    Source,
    group_to_str,
    schema_to_group,
)

from ..dataset_info import DatasetInfo
from ..dataset_schema import DatasetItem
from .dataset_exporter import DatasetExporter


class DefaultJSONDatasetExporter(DatasetExporter):
    """Default JSON dataset exporter."""

    def initialize_export_data(self, info: DatasetInfo, sources: list[Source]) -> dict[str, Any]:
        """Initialize the dictionary or list of dictionaries to be exported.

        Args:
            info: The dataset information.
            sources: The list of sources.

        Returns:
            A dictionary containing the data to be exported.
        """
        export_data = {"info": info.model_dump()}

        for group, schemas in self.dataset.schema.groups.items():
            if group == SchemaGroup.EMBEDDING:
                continue
            elif group == SchemaGroup.ITEM:
                export_data[group_to_str(group, plural=True)] = []
            else:
                export_data[group_to_str(group, plural=True)] = {schema: [] for schema in schemas}
        export_data[group_to_str(SchemaGroup.SOURCE, plural=True)] = [
            s.model_dump(exclude_timestamps=True) for s in sources
        ]
        return export_data

    def export_dataset_item(self, export_data: dict[str, Any], dataset_item: DatasetItem) -> None:
        """Store the dataset item in the `export_data` dictionary.

        Args:
            export_data: A dictionary containing the data to be exported.
            dataset_item: The dataset item to be exported.
        """
        data: dict[str, BaseSchema | list[BaseSchema] | None] = dataset_item.to_schemas_data(self.dataset.schema)
        for schema_name, schema_data in data.items():
            if schema_data is None or isinstance(schema_data, list) and len(schema_data) == 0:
                continue
            elif isinstance(schema_data, list):
                group = schema_to_group(schema_data[0])
                if group == SchemaGroup.ITEM:
                    list_ = export_data[group_to_str(group, plural=True)]
                else:
                    list_ = export_data[group_to_str(group, plural=True)][schema_name]
                list_.extend([s.model_dump(exclude_timestamps=True) for s in schema_data])
            else:
                group = schema_to_group(schema_data)
                if group == SchemaGroup.ITEM:
                    list_ = export_data[group_to_str(group, plural=True)]
                else:
                    print(group, export_data[group_to_str(group, plural=True)])
                    list_ = export_data[group_to_str(group, plural=True)][schema_name]

                list_.append(schema_data.model_dump(exclude_timestamps=True))

    def save_data(self, export_data: dict[str, Any], split: str, file_name: str, file_num: int) -> None:
        """Save data to the specified directory.

        The saved directory has the following structure:
            export_dir/{split}_{file_name}_0.json
                      /...
                      /{split}_{file_name}_{file_num}.json
                      /...
                      /{split}_{file_name}_n.json


        Args:
            export_data: The dictionary containing the data to be saved.
            split: The split of the dataset item being saved.
            file_name: The name of the file to save the data in.
            file_num: The number of the file to save the data in.
        """
        json_path = self.export_dir / f"{split}_{file_name}_{file_num}.json"
        json_path.write_text(json.dumps(jsonable_encoder(export_data), indent=4), encoding="utf-8")


class DefaultJSONLDatasetExporter(DatasetExporter):
    """Default JSON Lines dataset exporter."""

    def initialize_export_data(self, info: DatasetInfo, sources: list[Source]) -> list[dict[str, Any]]:
        """Initialize a list of dictionaries to be exported.

        The first line contains the following elements:
        - dataset info
        - the sources

        Args:
            info: The dataset information.
            sources: The list of sources.

        Returns:
            A list of dictionaries containing the data to be exported.
        """
        export_data = [
            {"info": info.model_dump(), "sources": [s.model_dump(exclude_timestamps=True) for s in sources]}
        ]
        return export_data

    def export_dataset_item(self, export_data: list[dict[str, Any]], dataset_item: DatasetItem) -> None:
        """Store the dataset item in the `export_data` list of dictionaries.

        Args:
            export_data: A list of dictionaries containing the dataset items to be exported.
            dataset_item: The dataset item to be exported.
        """
        export_data.append(dataset_item.model_dump(exclude_timestamps=True))

    def save_data(self, export_data: list[dict[str, Any]], split: str, file_name: str, file_num: int) -> None:
        """Save data to the specified directory.

        The saved directory has the following structure:
            export_dir/{split}_{file_name}_0.jsonl
                      /...
                      /{split}_{file_name}_{file_num}.jsonl
                      /...
                      /{split}_{file_name}_n.jsonl


        Args:
            export_data: The list of dictionaries containing the data to be saved.
            split: The split of the dataset item being saved.
            file_name: The name of the file to save the data in.
            file_num: The number of the file to save the data in.
        """
        info, data = export_data[0], export_data[1:]

        info_path = self.export_dir / "info.json"
        info_path.write_text(json.dumps(info), encoding="utf-8")

        json_path = self.export_dir / f"{split}_{file_name}_{file_num}.jsonl"
        json_path.write_text("\n".join([json.dumps(jsonable_encoder(d)) for d in data]), encoding="utf-8")
