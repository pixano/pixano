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

from pixano.core import EmbeddingType, ObjectAnnotationType
from pixano.data import Dataset, DatasetInfo


class InferenceModel(ABC):
    """Abstract parent class for OfflineModel and OnlineModel

    Attributes:
        name (str): Model name
        id (str, optional): Model ID
        device (str, optional): Model GPU or CPU device
        source (str, optional): Model source
        info (str, optional): Additional model info
    """

    def __init__(
        self,
        name: str,
        id: str = "",
        device: str = "",
        source: str = "",
        info: str = "",
    ) -> None:
        """Initialize model name and ID

        Args:
            name (str): Model name
            id (str, optional): Model ID. Defaults to "".
            device (str, optional): Model GPU or CPU device. Defaults to "".
            source (str, optional): Model source. Defaults to "".
            info (str, optional): Additional model info. Defaults to "".
        """

        self.name = name
        if id == "":
            self.id = f"{datetime.now().strftime('%y%m%d_%H%M%S')}_{name}"
        else:
            self.id = id
        self.device = device
        self.source = source
        self.info = info

    def inference_batch(
        self,
        batch: pa.RecordBatch,
        views: list[str],
        uri_prefix: str,
        threshold: float = 0.0,
    ) -> list[dict]:
        """Inference preannotation for a batch

        Args:
            batch (pa.RecordBatch): Input batch
            views (list[str]): Dataset views
            uri_prefix (str): URI prefix for media files
            threshold (float, optional): Confidence threshold. Defaults to 0.0.

        Returns:
            list[dict]: Inference rows
        """

        pass

    def embedding_batch(
        self,
        batch: pa.RecordBatch,
        views: list[str],
        uri_prefix: str,
    ) -> list[dict]:
        """Embedding precomputing for a batch

        Args:
            batch (pa.RecordBatch): Input batch
            views (list[str]): Dataset views
            uri_prefix (str): URI prefix for media files

        Returns:
            list[dict]: Inference rows
        """

        pass

    def process_dataset(
        self,
        input_dir: Path,
        process_type: str,
        views: list[str],
        splits: list[str] = [],
        batch_size: int = 1,
        threshold: float = 0.0,
    ) -> Path:
        """Process dataset for inference preannotation or embedding precomputing

        Args:
            input_dir (Path): Input dataset directory
            process_type (str): Process type ('infer' for inference preannotation or 'embed' for embedding precomputing)
            views (list[str]): Dataset views
            splits (list[str], optional): Dataset splits, all if []. Defaults to [].
            batch_size (int, optional): Rows per batch. Defaults to 1.
            threshold (float, optional): Confidence threshold for predictions. Defaults to 0.0.

        Returns:
            Path: Output dataset directory
        """

        output_dir = input_dir / f"db_{process_type}_{self.id}"

        # Input dataset
        dataset = Dataset(input_dir)

        # Create URI prefix
        media_dir = input_dir / "media"
        uri_prefix = media_dir.absolute().as_uri()

        # Create inference schema
        schema = pa.schema([pa.field("id", pa.string())])
        if process_type == "infer":
            schema.append(
                pa.field("objects", pa.list_(ObjectAnnotationType)),
            )
        elif process_type == "embed":
            for view in views:
                schema.append(pa.field(f"{view}_embedding", EmbeddingType))

        # Load dataset
        input_ds = dataset.load()
        split_filter = f"split IN {splits}" if splits else None
        batches = input_ds.to_batches(filter=split_filter, batch_size=batch_size)

        # Process dataset
        reader = pa.RecordBatchReader.from_batches(
            self.schema,
            tqdm(
                [
                    self.inference_batch(batch, views, uri_prefix, threshold)
                    if process_type == "infer"
                    else self.embedding_batch(batch, views, uri_prefix)
                    if process_type == "embed"
                    else None
                    for batch in batches
                ],
                desc="Importing dataset",
            ),
            desc="Importing dataset",
        )

        # Save inference dataset
        inference_ds = lance.write_dataset(
            reader, dataset.path / "db.lance", mode="overwrite"
        )

        # Save.json
        self.create_json(
            output_dir=output_dir,
            filename=process_type,
            dataset_info=dataset.info,
            num_elements=inference_ds.count_rows(),
        )

        return output_dir

    def create_json(
        self,
        output_dir: Path,
        filename: str,
        dataset_info: DatasetInfo,
        num_elements: int,
    ):
        """Save output .json

        Args:
            output_dir (Path): Output dataset directory
            filename (str): Output .json filename
            dataset_info (DatasetInfo): Dataset info
            num_elements (int): Number of processed rows
        """

        # Load existing .json
        if (output_dir / f"{filename}.json").is_file():
            with open(output_dir / f"{filename}.json", "r") as f:
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
                "model_source": self.source,
                "model_info": self.info,
            }

        # Save .json
        with open(output_dir / f"{filename}.json", "w") as f:
            json.dump(output_json, f)

    def export_to_onnx(self, library_dir: Path):
        """Export Torch model to ONNX

        Args:
            library_dir (Path): Dataset library directory
        """

        pass
