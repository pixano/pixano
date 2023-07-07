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
from abc import ABC
from datetime import datetime
from io import BytesIO
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm.auto import tqdm

from pixano.core import arrow_types
from pixano.transforms import natural_key


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
        view: str,
        uri_prefix: str,
        threshold: float = 0.0,
    ) -> list[list[arrow_types.ObjectAnnotation]]:
        """Inference preannotation for a batch

        Args:
            batch (pa.RecordBatch): Input batch
            view (str): Dataset view
            uri_prefix (str): URI prefix for media files
            threshold (float, optional): Confidence threshold. Defaults to 0.0.

        Returns:
            list[list[arrow_types.ObjectAnnotation]]: Model inferences as lists of ObjectAnnotation
        """

        pass

    def embedding_batch(
        self,
        batch: pa.RecordBatch,
        view: str,
        uri_prefix: str,
    ) -> list[np.ndarray]:
        """Embedding precomputing for a batch

        Args:
            batch (pa.RecordBatch): Input batch
            view (str): Dataset view
            uri_prefix (str): URI prefix for media files

        Returns:
            list[np.ndarray]: Model embeddings as NumPy arrays
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

        # Load spec.json
        with open(input_dir / "spec.json", "r") as f:
            spec_json = json.load(f)

        # Create URI prefix
        media_dir = input_dir / "media"
        uri_prefix = media_dir.absolute().as_uri()

        # If no splits provided, select all splits
        if not splits:
            splits = [s.name for s in os.scandir(input_dir / "db") if s.is_dir()]
        # Else, format provided splits
        else:
            splits = [f"split={s}" if not s.startswith("split=") else s for s in splits]
        # Check if the splits exist
        for split in splits:
            split_dir = input_dir / "db" / split
            if not split_dir.exists():
                raise Exception(f"{split_dir} does not exist.")
            if not any(split_dir.iterdir()):
                raise Exception(f"{split_dir} is empty.")

        # Create schema
        fields = [pa.field("id", pa.string())]
        if process_type == "infer":
            fields.extend(
                [
                    pa.field("objects", pa.list_(arrow_types.ObjectAnnotationType())),
                ]
            )
        elif process_type == "embed":
            fields.extend(
                [
                    pa.field(f"{view}_embedding", arrow_types.EmbeddingType())
                    for view in views
                ]
            )
        schema = pa.schema(fields)

        # Iterate on splits
        for split in splits:
            # List split files
            files = (input_dir / "db" / split).glob("*.parquet")
            files = sorted(files, key=lambda x: natural_key(x.name))

            # Create output split directory
            split_dir = output_dir / split
            split_dir.mkdir(parents=True, exist_ok=True)
            split_name = split.replace("split=", "")

            # Check for already processed files
            processed = [p.name for p in split_dir.glob("*.parquet")]

            # Iterate on files
            for file in tqdm(files, desc=f"Processing {split_name} split", position=0):
                # Process only remaining files
                if file.name not in processed:
                    # Load file into batches
                    table = pq.read_table(file)
                    batches = table.to_batches(max_chunksize=batch_size)

                    # Iterate on batches
                    data = {field.name: [] for field in schema}
                    for batch in tqdm(
                        batches, desc=f"Processing {file.name}", position=1
                    ):
                        # Add row IDs
                        data["id"].extend([str(row) for row in batch["id"]])
                        # For inferences
                        if process_type == "infer":
                            # Iterate on views
                            batch_inf = []
                            for view in views:
                                batch_inf.append(
                                    self.inference_batch(
                                        batch, view, uri_prefix, threshold
                                    )
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
                        # For embeddings
                        elif process_type == "embed":
                            # Iterate on views
                            for view in views:
                                view_emb = self.embedding_batch(batch, view, uri_prefix)
                                for emb in view_emb:
                                    emb_bytes = BytesIO()
                                    np.save(emb_bytes, emb)
                                    data[f"{view}_embedding"].append(
                                        emb_bytes.getvalue()
                                    )

                    # Convert ExtensionTypes
                    arrays = []
                    for field in schema:
                        arrays.append(
                            arrow_types.convert_field(
                                field_name=field.name,
                                field_type=field.type,
                                field_data=data[field.name],
                            )
                        )

                    # Save to file
                    pq.write_table(
                        pa.Table.from_arrays(arrays, schema=schema),
                        split_dir / file.name,
                    )

                    # Save.json
                    self.create_json(
                        output_dir=output_dir,
                        filename=process_type,
                        spec_json=spec_json,
                        num_elements=pq.read_metadata(split_dir / file.name).num_rows,
                    )

        return output_dir

    def create_json(
        self,
        output_dir: Path,
        filename: str,
        spec_json: dict,
        num_elements: int,
    ):
        """Save output .json

        Args:
            output_dir (Path): Output dataset directory
            filename (str): Output .json filename
            spec_json (dict): Input dataset .json
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
                "id": spec_json["id"],
                "name": spec_json["name"],
                "description": spec_json["description"],
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
