# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import json
import tempfile
from math import ceil
from pathlib import Path

import pytest
from fastapi.encoders import jsonable_encoder

from pixano.datasets.dataset import Dataset
from pixano.datasets.exporters.dataset_exporter import DatasetExporter
from pixano.datasets.queries.table import TableQueryBuilder
from pixano.features.schemas.schema_group import SchemaGroup


class DumbDatasetExporter(DatasetExporter):
    def initialize_export_data(self, info, sources):
        return {"info": info, "sources": sources}

    def export_dataset_item(self, export_data, dataset_item):
        export_data[dataset_item.id] = dataset_item

    def save_data(self, export_data, split, file_name, file_num):
        split_folder = self.export_dir / split
        split_folder.mkdir(parents=False, exist_ok=True)
        save_file = split_folder / f"{file_name}_{file_num}.txt"
        save_file.write_text(json.dumps(jsonable_encoder(export_data)))


class TestDatasetExporter:
    @pytest.mark.parametrize("file_name,items_per_file,batch_size", [("pixano_export", 2, None), ("test_1", None, 10)])
    def test_export(
        self, dataset_image_bboxes_keypoint: Dataset, file_name: str, items_per_file: int, batch_size: int
    ):
        export_dir = Path(tempfile.mkdtemp())
        exporter = DumbDatasetExporter(export_dir=export_dir, dataset=dataset_image_bboxes_keypoint, overwrite=True)
        exporter.export(file_name, items_per_file, batch_size)

        items_per_split = [("train", 2), ("test", 3)]
        sources = dataset_image_bboxes_keypoint.get_data(SchemaGroup.SOURCE.value, limit=int(1e9))
        dataset_items = dataset_image_bboxes_keypoint.get_dataset_items(limit=int(1e9))
        dataset_items_per_split = {split: [] for split, num_items in items_per_split}
        for item in dataset_items:
            dataset_items_per_split[item.split].append(item)

        for split, num_items in items_per_split:
            split_folder = export_dir / split
            expected_file_name = file_name
            expected_dataset_items = dataset_items_per_split[split]

            assert split_folder.exists()
            if items_per_file is None:
                assert len(list(split_folder.iterdir())) == 1
                with open(split_folder / f"{expected_file_name}_0.txt") as file:
                    json_content = json.load(file)
                expected_data = jsonable_encoder(
                    {
                        "sources": sources,
                        "info": dataset_image_bboxes_keypoint.info,
                    }
                )
                for dataset_item in expected_dataset_items:
                    expected_data[dataset_item.id] = dataset_item
                expected_json = jsonable_encoder(expected_data)
                assert json_content == expected_json
            else:
                expected_num_files = ceil(num_items / items_per_file)
                assert len(list(split_folder.iterdir())) == expected_num_files
                print(list(split_folder.iterdir()))
                for i in range(expected_num_files):
                    with open(split_folder / f"{expected_file_name}_{i}.txt", "r") as file:
                        json_content = json.load(file)
                    expected_data = jsonable_encoder(
                        {
                            "sources": sources,
                            "info": dataset_image_bboxes_keypoint.info,
                        }
                    )
                    for dataset_item in expected_dataset_items[i * items_per_file : (i + 1) * items_per_file]:
                        expected_data[dataset_item.id] = dataset_item.model_dump()
                    expected_json = jsonable_encoder(expected_data)
                    assert json_content == expected_json

    def test_export_errors(self, dataset_image_bboxes_keypoint: Dataset):
        export_dir = Path(tempfile.mkdtemp())
        exporter = DumbDatasetExporter(export_dir=export_dir, dataset=dataset_image_bboxes_keypoint, overwrite=True)
        with pytest.raises(ValueError, match="Items per file must be a positive integer"):
            exporter.export(file_name="test_1", items_per_file=-1, batch_size=4)

        exporter = DumbDatasetExporter(export_dir=export_dir, dataset=dataset_image_bboxes_keypoint, overwrite=True)
        with pytest.raises(ValueError, match="Batch size must be a positive integer"):
            exporter.export(file_name="test_1", items_per_file=2, batch_size=-1)

        exporter = DumbDatasetExporter(export_dir=export_dir, dataset=dataset_image_bboxes_keypoint, overwrite=False)
        with pytest.raises(FileExistsError):
            exporter.export(file_name="test_1", items_per_file=-1, batch_size=4)
