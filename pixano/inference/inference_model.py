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

from pixano.core.models import ObjectAnnotation


class InferenceModel:
    """Inference Model class for preannotation

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
        self, batch: pa.RecordBatch, media_dir: Path, threshold: float = 0.0
    ) -> list[list[ObjectAnnotation]]:
        """Returns model predictions for a given batch of images

        Args:
            batch (pa.RecordBatch): Batch of input in parquet format
            media_dir (Path): Media location
            threshold (float, optional): Confidence threshold for model predictions. Defaults to 0.0.

        Returns:
            list[list[ObjectAnnotation]]: Model predictions in Pixano format
        """

        raise NotImplementedError("Model inference needs to be implemented")

    def process_dataset(
        self,
        dataset_dir: Path,
        splits: list[str] = None,
        batch_size: int = 1,
        threshold: float = 0.0,
    ) -> Path:
        """Write predictions to parquet dataset

        Args:
            dataset_dir (Path): Dataset parquet location
            splits (list[str], optional): Dataset splits to infer on, will infer on all splits if None. Defaults to None.
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

        # Iterate on splits
        for split in splits:
            # List dataset files
            files = sorted((dataset_dir / "db" / split).glob("*.parquet"))

            # List already processed files
            processed = [p.name for p in (inference_dir / split).glob("*.parquet")]

            # Iterate on files
            for file in tqdm(files, desc=split, position=0):
                # Process only remaining files
                if file.name not in processed:
                    # Create folder
                    (inference_dir / split).mkdir(parents=True, exist_ok=True)

                    # Load file
                    table = pq.read_table(file)
                    num_elements = 0

                    # Iterate on batches
                    data = {"id": [], "objects": []}
                    batches = table.to_batches(max_chunksize=batch_size)
                    for batch in tqdm(batches, position=1, desc=file.name):
                        batch_inference = self(batch, dataset_dir / "media", threshold)
                        for img_index, img_inference in enumerate(batch_inference):
                            data["id"].append(str(batch["id"][img_index]))
                            data["objects"].append([o.dict() for o in img_inference])

                    # Save inference
                    inference_table = pa.Table.from_pydict(data)
                    pq.write_table(inference_table, inference_dir / split / file.name)
                    num_elements += inference_table.num_rows

                    # Load existing infer.json
                    if (inference_dir / "infer.json").is_file():
                        with open(inference_dir / "infer.json", "r") as f:
                            infer_json = json.load(f)
                        infer_json["num_elements"] += num_elements

                    # Or create infer.json from scratch
                    else:
                        infer_json = {
                            "id": spec_json["id"],
                            "name": spec_json["name"],
                            "description": spec_json["description"],
                            "num_elements": num_elements,
                            "model_id": self.id,
                            "model_name": self.name,
                            "model_source": self.source,
                            "model_info": self.info,
                        }

                    # Save infer.json
                    with open(inference_dir / "infer.json", "w") as f:
                        json.dump(infer_json, f)

        return inference_dir
