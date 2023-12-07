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

from abc import ABC
from datetime import datetime, timedelta
from math import ceil
from pathlib import Path

import duckdb
import lance
import lancedb
import pyarrow as pa
from tqdm.auto import tqdm

from pixano.data import Dataset, DatasetTable, Fields

# Disable warning for InferenceModel "id" attribute
# NOTE: Rename attribute? Will need to update Pixano Inference
# pylint: disable=redefined-builtin


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

    def preannotate(
        self,
        batch: pa.RecordBatch,
        views: list[str],
        uri_prefix: str,
        threshold: float = 0.0,
    ) -> list[dict]:
        """Preannotate dataset rows

        Args:
            batch (pa.RecordBatch): Input batch
            views (list[str]): Dataset views
            uri_prefix (str): URI prefix for media files
            threshold (float, optional): Confidence threshold. Defaults to 0.0.

        Returns:
            list[dict]: Annotation rows
        """

    def precompute_embeddings(
        self,
        batch: pa.RecordBatch,
        views: list[str],
        uri_prefix: str,
    ) -> list[dict]:
        """Precompute embeddings for dataset rows

        Args:
            batch (pa.RecordBatch): Input batch
            views (list[str]): Dataset views
            uri_prefix (str): URI prefix for media files

        Returns:
            list[dict]: Embedding rows
        """

    def process_dataset(
        self,
        dataset_dir: Path,
        process_type: str,
        views: list[str],
        splits: list[str] = None,
        batch_size: int = 1,
        threshold: float = 0.0,
    ) -> Dataset:
        """Process dataset for preannotation or embedding precomputing

        Args:
            dataset_dir (Path): Dataset directory
            process_type (str): Process type
                                - 'obj' for preannotation
                                - 'segment_emb' for segmentation embedding precomputing
                                - 'search_emb' for semantic search embedding precomputing
            views (list[str]): Dataset views
            splits (list[str], optional): Dataset splits, all if None. Defaults to None.
            batch_size (int, optional): Rows per batch. Defaults to 1.
            threshold (float, optional): Confidence threshold for predictions. Defaults to 0.0.

        Returns:
            Dataset: Dataset
        """

        if splits:
            split_ids = "'" + "', '".join(splits) + "'"
        if process_type not in ["obj", "segment_emb", "search_emb"]:
            raise ValueError(
                "Please choose a valid process type ('obj' for preannotation, 'segment_emb' or 'search_emb'"
                "for segmentation or semantic search embedding precomputing)"
            )

        output_filename = (
            f"emb_{self.id}" if "emb" in process_type else f"obj_{self.id}"
        )

        # Load dataset
        dataset = Dataset(dataset_dir)
        ds = dataset.connect()

        # Load dataset tables
        ds_tables = dataset.open_tables()

        # Create URI prefix
        uri_prefix = dataset.media_dir.absolute().as_uri()

        # Objects preannotation schema
        if process_type == "obj":
            table_group = "objects"
            table_type = None
            table_fields = {
                "id": "str",
                "item_id": "str",
                "view_id": "str",
                "bbox": "bbox",
                "mask": "compressedrle",
                "category_id": "int",
                "category_name": "str",
            }
        # Segmentation Embedding precomputing schema
        elif process_type == "segment_emb":
            table_group = "embeddings"
            table_type = "segment"
            table_fields = {"id": "str"}
            # Add embedding column for each selected view
            for view in views:
                table_fields[view] = "bytes"
        # Semantic Search Embedding precomputing schema
        elif process_type == "search_emb":
            table_group = "embeddings"
            table_type = "search"
            table_fields = {"id": "str"}
            # Add vector column for each selected view
            for view in views:
                table_fields[view] = "vector(512)"

        # Add new table to DatasetInfo
        table = DatasetTable(
            name=output_filename,
            fields=table_fields,
            source=self.name,
            type=table_type,
        )

        if table_group in dataset.info.tables:
            dataset.info.tables[table_group].append(table)
        else:
            dataset.info.tables[table_group] = [table]
        dataset.save_info()

        # Create new Lance table
        # Disable warning for create_table() "mode" argument
        # pylint: disable=unexpected-keyword-arg
        ds_table: lancedb.db.LanceTable = ds.create_table(
            output_filename,
            schema=Fields(table_fields).to_schema(),
            mode="overwrite",
        )
        output_batch = []
        save_batch_size = 1024

        # Add rows to tables
        with tqdm(desc="Processing dataset", total=dataset.num_rows) as progress:
            for i in range(ceil(dataset.num_rows / save_batch_size)):
                # Load rows
                offset = i * save_batch_size
                limit = min(dataset.num_rows, offset + save_batch_size)
                pyarrow_table = ds_tables["main"]["db"].to_lance()
                pyarrow_table = duckdb.query(
                    f"SELECT * FROM pyarrow_table ORDER BY len(id), id LIMIT {limit} OFFSET {offset}"
                ).to_arrow_table()
                for media_table in ds_tables["media"].values():
                    pyarrow_media_table = media_table.to_lance().to_table(
                        limit=limit, offset=offset
                    )
                    pyarrow_media_table = duckdb.query(
                        f"SELECT * FROM pyarrow_media_table ORDER BY len(id), id LIMIT {limit} OFFSET {offset}"
                    ).to_arrow_table()
                    pyarrow_table = duckdb.query(
                        "SELECT * FROM pyarrow_table LEFT JOIN pyarrow_media_table USING (id) ORDER BY len(id), id"
                    ).to_arrow_table()
                # Filter splits
                if splits:
                    pyarrow_table = duckdb.query(
                        f"SELECT * FROM pyarrow_table WHERE split in ({split_ids})"
                    ).to_arrow_table()
                # Convert to RecordBatch
                input_batches = pyarrow_table.to_batches(max_chunksize=batch_size)

                # Store rows in a batch
                for input_batch in input_batches:
                    output_batch.extend(
                        self.preannotate(input_batch, views, uri_prefix, threshold)
                        if process_type == "obj"
                        else self.precompute_embeddings(input_batch, views, uri_prefix)
                        if process_type in ["segment_emb", "search_emb"]
                        else []
                    )
                    progress.update(batch_size)

                # If batch reaches 1024 rows, store in table
                if len(output_batch) >= save_batch_size:
                    pa_batch = pa.Table.from_pylist(
                        output_batch,
                        schema=Fields(table.fields).to_schema(),
                    )
                    lance.write_dataset(
                        pa_batch,
                        uri=ds_table.to_lance().uri,
                        mode="append",
                    )
                    output_batch = []

        # Store final batch
        if len(output_batch) > 0:
            pa_batch = pa.Table.from_pylist(
                output_batch,
                schema=Fields(table.fields).to_schema(),
            )
            lance.write_dataset(
                pa_batch,
                uri=ds_table.to_lance().uri,
                mode="append",
            )
            output_batch = []

        # Optimize and clear creation history
        ds_table.to_lance().optimize.compact_files()
        ds_table.to_lance().cleanup_old_versions(older_than=timedelta(0))

        return dataset

    def export_to_onnx(self, library_dir: Path):
        """Export Torch model to ONNX

        Args:
            library_dir (Path): Dataset library directory
        """
