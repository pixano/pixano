# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import json
from typing import Any

from fastapi.encoders import jsonable_encoder
from lancedb.pydantic import LanceModel

from ..dataset_info import DatasetInfo
from ..dataset_schema import build_model_dump_exclude_timestamps
from .dataset_exporter import DatasetExporter


_TIMESTAMP_EXCLUDE = {"created_at", "updated_at"}


class DefaultJSONLDatasetExporter(DatasetExporter):
    """Default JSON Lines dataset exporter."""

    def initialize_export_data(self, info: DatasetInfo) -> list[dict[str, Any]]:
        """Initialize a list of dictionaries to be exported.

        The first line contains the dataset info.

        Args:
            info: The dataset information.

        Returns:
            A list of dictionaries containing the data to be exported.
        """
        export_data = [
            {
                "info": info.model_dump(exclude={"tables"}),
            }
        ]
        return export_data

    def export_record(
        self,
        export_data: list[dict[str, Any]],
        record_data: dict[str, LanceModel | list[LanceModel] | None],
    ) -> list[dict[str, Any]]:
        """Store the record data in the `export_data` list of dictionaries.

        Args:
            export_data: A list of dictionaries containing the records to be exported.
            record_data: Dict of table_name → row(s) for this record.

        Returns:
            A list of dictionaries containing the records to be exported.
        """
        # Flatten all table data into a single dict for this record
        record_dict: dict[str, Any] = {}
        for table_name, schema_data in record_data.items():
            if schema_data is None:
                continue
            if isinstance(schema_data, list):
                for row in schema_data:
                    exclude = build_model_dump_exclude_timestamps(row)
                    dumped = row.model_dump(exclude=exclude)
                    record_dict.setdefault(table_name, []).append(dumped)
            else:
                exclude = build_model_dump_exclude_timestamps(schema_data)
                record_dict[table_name] = schema_data.model_dump(exclude=exclude)
        export_data.append(record_dict)
        return export_data

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
