# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import json
from typing import Any

from fastapi.encoders import jsonable_encoder
from lancedb.pydantic import LanceModel

from pixano.schemas import SchemaGroup, group_to_str, schema_to_group

from ..dataset_info import DatasetInfo
from .dataset_exporter import DatasetExporter


_TIMESTAMP_EXCLUDE = {"created_at", "updated_at"}


class DefaultJSONDatasetExporter(DatasetExporter):
    """Default JSON dataset exporter."""

    def initialize_export_data(self, info: DatasetInfo) -> dict[str, Any]:
        """Initialize the dictionary or list of dictionaries to be exported.

        Args:
            info: The dataset information.

        Returns:
            A dictionary containing the data to be exported.
        """
        export_data = {"info": info.model_dump(exclude={"tables"})}

        for group, table_names in info.groups.items():
            if group == SchemaGroup.EMBEDDING:
                continue
            elif group == SchemaGroup.RECORD:
                export_data[group_to_str(group, plural=True)] = []
            else:
                export_data[group_to_str(group, plural=True)] = {name: [] for name in table_names}
        return export_data

    def export_record(
        self, export_data: dict[str, Any], record_data: dict[str, LanceModel | list[LanceModel] | None]
    ) -> dict[str, Any]:
        """Store the record data in the `export_data` dictionary.

        Args:
            export_data: A dictionary containing the data to be exported.
            record_data: Dict of table_name → row(s) for this record.

        Returns:
            A dictionary containing the data to be exported.
        """
        for schema_name, schema_data in record_data.items():
            if schema_data:
                schema_data_list = schema_data if isinstance(schema_data, list) else [schema_data]
                group = schema_to_group(schema_data_list[0])
                if group == SchemaGroup.RECORD:
                    export_data[group_to_str(group, plural=True)].extend(
                        [s.model_dump(exclude=_TIMESTAMP_EXCLUDE) for s in schema_data_list]
                    )
                else:
                    group_key = group_to_str(group, plural=True)
                    if group_key in export_data and schema_name in export_data[group_key]:
                        export_data[group_key][schema_name].extend(
                            [s.model_dump(exclude=_TIMESTAMP_EXCLUDE) for s in schema_data_list]
                        )
        return export_data

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
