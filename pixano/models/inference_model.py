# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

import json
from abc import ABC
from datetime import datetime
from pathlib import Path

import lance
import pyarrow as pa
from tqdm.auto import tqdm

from pixano.core import EmbeddingType, ObjectAnnotationType, pyarrow_array_from_list
from pixano.data import Dataset, DatasetInfo, Fields


class InferenceModel(ABC):
    """Abstract parent class for OfflineModel and OnlineModel

    Attributes:
        name (str): Model name
        id (str): Model ID
        device (str): Model GPU or CPU device
        description (str): Model description
    """

    def __init__(
        self,
        name: str,
        id: str = "",
        device: str = "",
        description: str = "",
    ) -> None:
        """Initialize model name and ID

        Args:
            name (str): Model name
            id (str, optional): Model ID. Defaults to "".
            device (str, optional): Model GPU or CPU device. Defaults to "".
            description (str, optional): Model description. Defaults to "".
        """

        self.name = name
        if id == "":
            self.id = f"{datetime.now().strftime('%y%m%d_%H%M%S')}_{name}"
        else:
            self.id = id
        self.device = device
        self.description = description

    def inference_batch(
        self,
        batch: pa.RecordBatch,
        views: list[str],
        uri_prefix: str,
        threshold: float = 0.0,
    ) -> pa.RecordBatch:
        """Inference preannotation for a batch

        Args:
            batch (pa.RecordBatch): Input batch
            views (list[str]): Dataset views
            uri_prefix (str): URI prefix for media files
            threshold (float, optional): Confidence threshold. Defaults to 0.0.

        Returns:
            pa.RecordBatch: Inference rows
        """

        pass

    def embedding_batch(
        self,
        batch: pa.RecordBatch,
        views: list[str],
        uri_prefix: str,
    ) -> pa.RecordBatch:
        """Embedding precomputing for a batch

        Args:
            batch (pa.RecordBatch): Input batch
            views (list[str]): Dataset views
            uri_prefix (str): URI prefix for media files

        Returns:
            pa.RecordBatch: Embedding rows
        """

        pass

    def process_dataset(
        self,
        dataset_dir: Path,
        process_type: str,
        views: list[str],
        splits: list[str] = [],
        batch_size: int = 1,
        threshold: float = 0.0,
    ) -> Path:
        """Process dataset for inference preannotation or embedding precomputing

        Args:
            dataset_dir (Path): Input dataset directory
            process_type (str): Process type ('infer' for inference preannotation or 'embed' for embedding precomputing)
            views (list[str]): Dataset views
            splits (list[str], optional): Dataset splits, all if []. Defaults to [].
            batch_size (int, optional): Rows per batch. Defaults to 1.
            threshold (float, optional): Confidence threshold for predictions. Defaults to 0.0.

        Returns:
            Path: Output dataset directory
        """

        output_filename = f"db_{process_type}_{self.id}"

        # Input dataset
        dataset = Dataset(dataset_dir)

        # Create URI prefix
        media_dir = dataset_dir / "media"
        uri_prefix = media_dir.absolute().as_uri()

        # Create inference schema
        self.schema = pa.schema(
            [pa.field("id", pa.string()), pa.field("split", pa.string())]
        )
        fields_dict = {"id": "str", "split": "str"}

        # Inference generation schema
        if process_type == "infer":
            self.schema = self.schema.append(
                pa.field("objects", pa.list_(ObjectAnnotationType)),
            )
            fields_dict["objects"] = "[objectannotation]"

        # Embedding precomputing schema
        elif process_type == "embed":
            for view in views:
                self.schema = self.schema.append(
                    pa.field(f"{view}_embedding", EmbeddingType)
                )
                fields_dict[f"{view}_embedding"] = "embedding"

        # Create fields
        self.fields = Fields.from_dict(fields_dict)

        # Load dataset
        input_ds = dataset.load()
        split_filter = f"split IN {splits}" if splits else None
        batches = input_ds.to_batches(filter=split_filter, batch_size=batch_size)

        # Process dataset
        reader = pa.RecordBatchReader.from_batches(
            self.schema,
            [
                self.inference_batch(batch, views, uri_prefix, threshold)
                if process_type == "infer"
                else self.embedding_batch(batch, views, uri_prefix)
                if process_type == "embed"
                else None
                for batch in batches
            ],
        )

        # Save inference dataset
        inference_ds = lance.write_dataset(
            reader,
            dataset_dir / f"{output_filename}.lance",
            mode="overwrite",
        )

        # Save.json
        self.create_json(
            output_filename=output_filename,
            dataset_info=dataset.info,
            num_elements=inference_ds.count_rows(),
        )

        return Path(dataset_dir / f"{output_filename}.lance")

    def dicts_to_recordbatch(self, rows: list[dict[str, list]]) -> pa.RecordBatch:
        """Convert a dataset row from a Python dict to a PyArrow RecordBatch

        Args:
            rows (list[dict[str, list]]): Dataset row as Python dict. Dict keys must match the names of the dataset fields.

        Returns:
            pa.RecordBatch: PyArrow RecordBatch
        """

        # Compare dict keys to field names
        if set(rows[0].keys()) != set(self.fields.to_dict().keys()):
            raise ValueError("Dict keys do not match the names of the dataset fields")

        # Convert the dict to a list of PyArrow arrays
        arrays = [
            pyarrow_array_from_list([row[field.name] for row in rows], field.type)
            for field in self.schema
        ]

        # Create the RecordBatch from PyArrow arrays
        return pa.RecordBatch.from_struct_array(pa.StructArray.from_arrays(arrays))

    def create_json(
        self,
        output_filename: str,
        dataset_info: DatasetInfo,
        num_elements: int,
    ):
        """Save output .json

        Args:
            output_filename (str): Output filename
            dataset_info (DatasetInfo): Dataset info
            num_elements (int): Number of processed rows
        """

        # Load existing .json
        if (f"{output_filename}.json").is_file():
            with open(f"{output_filename}.json", "r") as f:
                output_json = json.load(f)
            output_json["num_elements"] += num_elements

        # Or create .json from scratch
        else:
            output_json = {
                "id": dataset_info.id,
                "name": dataset_info.name,
                "description": dataset_info.description,
                "num_elements": num_elements,
                "model_id": self.id,
                "model_name": self.name,
                "model_description": self.description,
            }

        # Save .json
        with open(f"{output_filename}.json", "w") as f:
            json.dump(output_json, f)

    def export_to_onnx(self, library_dir: Path):
        """Export Torch model to ONNX

        Args:
            library_dir (Path): Dataset library directory
        """

        pass
