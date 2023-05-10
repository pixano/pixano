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
from abc import abstractmethod
from io import BytesIO
from pathlib import Path

import cv2
import duckdb
import numpy as np
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq
from onnxruntime import InferenceSession
from tqdm.auto import tqdm

from pixano.transforms import binary_to_base64

from .inference_model import InferenceModel


class OnlineModel(InferenceModel):
    """InferenceModel class for online interactive annotation

    Attributes:
        name (str): Model name
        id (str): Model ID
        device (str): Model GPU or CPU device
        source (str): Model source
        info (str): Additional model info
        onnx_path (Path): ONNX Model Path
        onnx_session (onnxruntime.InferenceSession): ONNX session
        working (dict): Dictionary of current working data
    """

    def __init__(
        self,
        name: str,
        id: str = "",
        device: str = "",
        source: str = "",
        info: str = "",
    ) -> None:
        super().__init__(name, id, device, source, info)
        self.working = {}

    @abstractmethod
    def __call__(self, input: dict[str, np.ndarray]) -> np.ndarray:
        """Return model annotation based on user input

        Args:
            input (dict[str, np.ndarray]): User input

        Returns:
            np.ndarray: Model annotation masks
        """

        pass

    @abstractmethod
    def process_batch(
        self,
        batch: pa.RecordBatch,
        view: str,
        media_dir: Path,
    ) -> list[np.ndarray]:
        """Precompute embeddings for a batch

        Args:
            batch (pa.RecordBatch): Input batch
            view (str): Dataset view
            media_dir (Path): Media location

        Returns:
            list[np.ndarray]: Model embeddings as NumPy arrays
        """

        pass

    def process_dataset(
        self,
        input_dir: Path,
        views: list[str],
        splits: list[str] = [],
        batch_size: int = 1,
    ) -> Path:
        """Precompute embeddings for a parquet dataset

        Args:
            input_dir (Path): Input parquet location
            views (list[str]): Dataset views
            splits (list[str], optional): Dataset splits, all if []. Defaults to [].
            batch_size (int, optional): Rows per batch. Defaults to 1.

        Returns:
            Path: Output parquet location
        """

        output_dir = input_dir / f"db_embed_{self.id}"

        # Load spec.json
        with open(input_dir / "spec.json", "r") as f:
            spec_json = json.load(f)

        # If no splits given, select all splits
        if splits == []:
            splits = [s.name for s in os.scandir(input_dir / "db") if s.is_dir()]

        # Create schema
        fields = [pa.field("id", pa.string())]
        fields.extend([pa.field(f"{view}_embedding", pa.binary()) for view in views])
        schema = pa.schema(fields)

        # Iterate on splits
        for split in splits:
            # List dataset files
            files = sorted((input_dir / "db" / split).glob("*.parquet"))

            # Create folder
            split_dir = output_dir / split
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
                        # Iterate on views
                        for view in views:
                            view_emb = self.process_batch(
                                batch, view, input_dir / "media"
                            )
                            for emb in view_emb:
                                emb_bytes = BytesIO()
                                np.save(emb_bytes, emb)
                                data[f"{view}_embedding"].append(emb_bytes.getvalue())

                    # Save to file
                    pq.write_table(
                        pa.Table.from_pydict(data, schema=schema),
                        split_dir / file.name,
                    )

                    # Save.json
                    super().save_json(
                        output_dir=output_dir,
                        filename="embed",
                        spec_json=spec_json,
                        num_elements=pq.read_metadata(split_dir / file.name).num_rows,
                    )

        return output_dir

    @abstractmethod
    def export_onnx_model(self) -> Path:
        """Export Torch model to ONNX

        Returns:
            Path: ONNX model path
        """

        pass

    def set_onnx_model(self, onnx_path: Path = None):
        """Set existing ONNX model path or export model to ONNX

        Args:
            onnx_path (Path, optional): ONNX Model path. Defaults to None.
        """

        if onnx_path == None:
            onnx_path = self.export_onnx_model()

        self.onnx_path = Path(onnx_path)

    def set_dataset(self, input_dir: Path):
        """Set current working dataset

        Args:
            input_dir (Path): Dataset path
        """

        self.working["input_dir"] = Path(input_dir)
        self.working["embed_dir"] = Path(input_dir) / f"db_embed_{self.id}"

    def set_image(self, id: str, view: str) -> str:
        """Set current working image and return embedding

        Args:
            id (str): Row ID
            view (str): View ID

        Returns:
            str: Image embedding in base 64
        """

        # Load datasets
        split = ds.partitioning(pa.schema([("split", pa.string())]), flavor="hive")
        input_ds = ds.dataset(
            self.working["input_dir"] / "db",
            partitioning=split,
        )
        embed_ds = ds.dataset(
            self.working["embed_dir"],
            partitioning=split,
            ignore_prefixes=["info", "embed.json"],
        )

        # Set working image
        input_row = duckdb.query(f"SELECT * FROM input_ds WHERE id={id}").arrow()
        image = cv2.imread(
            str(self.working["input_dir"] / "media" / input_row[view][0].as_py()["uri"])
        )
        self.working["image"] = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Get embedding
        embed_row = duckdb.query(f"SELECT * FROM embed_ds WHERE id={id}").arrow()
        embedding = binary_to_base64(embed_row["image_embedding"][0].as_py())

        # Reshape and return embedding
        return embedding

    def open_onnx_session(self):
        """Open an ONNX session for interactive annotation"""

        self.onnx_session = InferenceSession(self.onnx_path.as_posix())

    def close_onnx_session(self):
        """Close the ONNX session for interactive annotation"""

        del self.onnx_session
