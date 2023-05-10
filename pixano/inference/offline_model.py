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

import pyarrow as pa
import pyarrow.parquet as pq
from tqdm.auto import tqdm

from pixano.core import arrow_types

from .inference_model import InferenceModel


class OfflineModel(InferenceModel):
    """InferenceModel class for offline pre-annotation

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
        threshold: float = 0.0,
    ) -> list[list[arrow_types.ObjectAnnotation]]:
        """Process batch

        Args:
            batch (pa.RecordBatch): Input batch
            view (str): Dataset view
            media_dir (Path): Media location
            threshold (float, optional): Confidence threshold. Defaults to 0.0.

        Returns:
            list[list[arrow_types.ObjectAnnotation]]: Model inferences as lists of ObjectAnnotation
        """

        pass

    def process_dataset(
        self,
        input_dir: Path,
        views: list[str],
        splits: list[str] = [],
        batch_size: int = 1,
        threshold: float = 0.0,
    ) -> Path:
        """Generate inferences for a parquet dataset

        Args:
            input_dir (Path): Input parquet location
            views (list[str]): Dataset views
            splits (list[str], optional): Dataset splits, all if []. Defaults to [].
            batch_size (int, optional): Rows per batch. Defaults to 1.
            threshold (float, optional): Confidence threshold for model predictions. Defaults to 0.0.

        Returns:
            Path: Output parquet location
        """

        output_dir = input_dir / f"db_infer_{self.id}"

        # Load spec.json
        with open(input_dir / "spec.json", "r") as f:
            spec_json = json.load(f)

        # If no splits given, select all splits
        if splits == []:
            splits = [s.name for s in os.scandir(input_dir / "db") if s.is_dir()]

        # Create schema
        schema = pa.schema(
            [
                pa.field("id", pa.string()),
                pa.field("objects", pa.list_(arrow_types.ObjectAnnotationType())),
            ]
        )

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
                        batch_inf = []
                        for view in views:
                            batch_inf.append(
                                self(batch, view, input_dir / "media", threshold)
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

                    # Save.json
                    super().save_json(
                        output_dir=output_dir,
                        filename="infer",
                        spec_json=spec_json,
                        num_elements=pq.read_metadata(split_dir / file.name).num_rows,
                    )

        return output_dir
