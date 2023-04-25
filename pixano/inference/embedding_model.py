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
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from tqdm.auto import tqdm

from .pixano_model import PixanoModel


class EmbeddingModel(PixanoModel):
    """Model class for embedding precomputing

    Attributes:
        name (str): Model name
        id (str): Model ID
        device (str): Model GPU or CPU device
        source (str): Model source
        info (str): Additional model info
    """

    @abstractmethod
    def __call__(
        self,
        batch: pa.RecordBatch,
        view: str,
        media_dir: Path,
    ) -> list[np.ndarray]:
        """Process batch

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
        splits: list[str] = None,
        batch_size: int = 1,
        compression: str = "none",
    ) -> Path:
        """Precompute embeddings for a parquet dataset

        Args:
            input_dir (Path): Input parquet location
            views (list[str]): Dataset views
            splits (list[str], optional): Dataset splits, all if None. Defaults to None.
            batch_size (int, optional): Rows per batch. Defaults to 1.
            compression (str, optional): Output parquet compression format. Defaults to "none".

        Returns:
            Path: Output parquet location
        """

        output_dir = input_dir / f"db_embed_{self.id}"

        # Load spec.json
        with open(input_dir / "spec.json", "r") as f:
            spec_json = json.load(f)

        # If no splits given, select all splits
        if splits == None:
            splits = [s.name for s in os.scandir(input_dir / "db") if s.is_dir()]

        # Create schema
        fields = [pa.field("id", pa.string())]
        fields.extend(
            [pa.field(f"{view}_embedding", pa.list_(pa.float32())) for view in views]
        )
        schema = pa.schema(fields)

        # Create embedding shapes dict
        shapes = {}

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
                            view_emb = self(batch, view, input_dir / "media")
                            data[f"{view}_embedding"].extend(
                                [e.flatten() for e in view_emb]
                            )
                            shapes[f"{view}_embedding_shape"] = list(view_emb[0].shape)

                    # Save to file
                    pq.write_table(
                        pa.Table.from_pydict(data, schema=schema),
                        split_dir / file.name,
                        compression=compression,
                    )

                    # Save.json
                    super().save_json(
                        output_dir=output_dir,
                        filename="embed",
                        spec_json=spec_json,
                        num_elements=pq.read_metadata(split_dir / file.name).num_rows,
                        additional_info=shapes,
                    )

        return output_dir
