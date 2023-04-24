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
import os
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm.auto import tqdm

from pixano.core import arrow_types
from pixano.core.models import ObjectAnnotation


class InferenceModel:
    """Model class for inference generation

    Args:
        name (str): Model name
        id (str): Model ID
        device (str): Device to run model on
        source (str): Model source
        info (str): Any additional model info
    """

    def __init__(
        self,
        name: str,
        id: str = "",
        device: str = "",
        source: str = "Not provided",
        info: str = "Not provided",
    ) -> None:
        """Initialize model name and ID

        Args:
            name (str): Model name
            id (str, optional): Use previously defined model by providing its ID. Defaults to "".
            device (str, optional): Device to run model on (e.g. "cuda" for PyTorch, "/GPU:0" for TensorFlow). Defaults to "".
            source (str, optional): Model source (e.g. "PyTorch Hub", "GitHub", "Local Model"). Defaults to "Not provided".
            info (str, optional): Any additional model info. Defaults to "Not provided".
        """

        self.name = name
        if id == "":
            self.id = datetime.now().strftime("%y%m%d_%H%M%S") + "_" + name
        else:
            self.id = id
        self.device = device
        self.source = source
        self.info = info

    def __call__(
        self, batch: pa.RecordBatch, view: str, media_dir: Path, threshold: float = 0.0
    ) -> list[list[ObjectAnnotation]]:
        """Returns model inferences for a given batch of images

        Args:
            batch (pa.RecordBatch): Batch of input in PyArrow format
            view (str): Dataset view to generate inferences on
            media_dir (Path): Media location
            threshold (float, optional): Confidence threshold for inferences. Defaults to 0.0.

        Returns:
            list[list[ObjectAnnotation]]: Model inferences in Pixano format
        """

        raise NotImplementedError("Model inference generation needs to be implemented")

    def process_dataset(
        self,
        dataset_dir: Path,
        views: list[str],
        splits: list[str] = None,
        batch_size: int = 1,
        threshold: float = 0.0,
    ) -> Path:
        """Generate inferences for a parquet dataset

        Args:
            dataset_dir (Path): Dataset parquet location
            views (list[str]): Dataset views to generate inferences on
            splits (list[str], optional): Dataset splits to generate inferences on, will generate on all splits if None. Defaults to None.
            batch size (int, optional): Number of images per batch. Defaults to 1.
            threshold (float, optional): Confidence threshold for model predictions. Defaults to 0.0.

        Returns:
            Path: Inference parquet location
        """

        inference_dir = dataset_dir / str("db_infer_" + self.id)

        # Load spec.json
        with open(dataset_dir / "spec.json", "r") as f:
            spec_json = json.load(f)

        # If no splits given, select all splits
        if splits == None:
            splits = [s.name for s in os.scandir(dataset_dir / "db") if s.is_dir()]

        # Create inference schema
        schema = pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("objects", pa.list_(arrow_types.ObjectAnnotationType())),
            ]
        )

        # Iterate on splits
        for split in splits:
            # List dataset files
            files = sorted((dataset_dir / "db" / split).glob("*.parquet"))

            # Create folder
            split_dir = inference_dir / split
            split_dir.mkdir(parents=True, exist_ok=True)

            # Check for already processed files
            processed = [p.name for p in split_dir.glob("*.parquet")]

            # Iterate on files
            for file in tqdm(files, desc=split, position=0):
                # Process only remaining files
                if file.name not in processed:
                    # Load file into batches
                    table = pq.read_table(file)
                    batches = table.to_batches(max_chunksize=batch_size)

                    # Iterate on batches
                    data = {field.name: [] for field in schema}
                    for batch in tqdm(batches, position=1, desc=file.name):
                        # Add row IDs
                        data["id"].extend([str(row) for row in batch["id"]])
                        # Batch inference generation on each view
                        batch_inf = []
                        for view in views:
                            batch_inf.append(
                                self(batch, view, dataset_dir / "media", threshold)
                            )
                        # Regroup view inferences by row
                        data["objects"].append(
                            [
                                inf.dict()
                                for row in range(len(batch["id"]))
                                for view_inf in batch_inf
                                for inf in view_inf[row]
                            ]
                        )

                    # Convert ExtensionTypes
                    arrays = []
                    for field_name, field_data in data.items():
                        arrays.append(
                            arrow_types.convert_field(
                                field_name=field_name,
                                field_type=schema.field(field_name).type,
                                field_data=field_data,
                            )
                        )

                    # Save to file
                    pq.write_table(
                        pa.Table.from_arrays(arrays, schema=schema),
                        split_dir / file.name,
                    )
                    processed_file = pq.read_metadata(split_dir / file.name)

                    # Load existing infer.json
                    if (inference_dir / "infer.json").is_file():
                        with open(inference_dir / "infer.json", "r") as f:
                            infer_json = json.load(f)
                        infer_json["num_elements"] += processed_file.num_rows

                    # Or create infer.json from scratch
                    else:
                        infer_json = {
                            "id": spec_json["id"],
                            "name": spec_json["name"],
                            "description": spec_json["description"],
                            "num_elements": processed_file.num_rows,
                            "model_id": self.id,
                            "model_name": self.name,
                            "model_source": self.source,
                            "model_info": self.info,
                        }

                    # Save infer.json
                    with open(inference_dir / "infer.json", "w") as f:
                        json.dump(infer_json, f)

        return inference_dir
