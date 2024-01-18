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

    def create_table(
        self,
        process_type: str,
        views: list[str],
        dataset: Dataset,
    ) -> DatasetTable:
        """Create inference table in dataset

        Args:
            process_type (str): Process type
                                - 'obj' for preannotation
                                - 'segment_emb' for segmentation embedding precomputing
                                - 'search_emb' for semantic search embedding precomputing
            views (list[str]): Dataset views
            dataset (Dataset): Dataset

        Returns:
            DatasetTable: Inference table
        """

        # Inference table filename
        table_filename = f"emb_{self.id}" if "emb" in process_type else f"obj_{self.id}"

        # Objects preannotation schema
        if process_type == "obj":
            table_group = "objects"
            # Create table
            table = DatasetTable(
                name=table_filename,
                fields={
                    "id": "str",
                    "item_id": "str",
                    "view_id": "str",
                    "bbox": "bbox",
                    "mask": "compressedrle",
                    "category": "str",
                },
                source=self.name,
                type=None,
            )
        # Segmentation Embedding precomputing schema
        elif process_type == "segment_emb":
            table_group = "embeddings"
            # Add embedding column for each selected view
            fields = {"id": "str"}
            for view in views:
                fields[view] = "bytes"
            # Create table
            table = DatasetTable(
                name=table_filename,
                fields=fields,
                source=self.name,
                type="segment",
            )

        # Semantic Search Embedding precomputing schema
        elif process_type == "search_emb":
            table_group = "embeddings"
            # Add vector column for each selected view
            fields = {"id": "str"}
            for view in views:
                fields[view] = "vector(512)"
            # Create table
            table = DatasetTable(
                name=table_filename,
                fields=fields,
                source=self.name,
                type="search",
            )

        # Create table
        dataset.create_table(table, table_group)

        return table

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
            batch_size (int, optional): Rows per process batch. Defaults to 1.
            threshold (float, optional): Confidence threshold for predictions. Defaults to 0.0.

        Returns:
            Dataset: Dataset
        """

        if process_type not in ["obj", "segment_emb", "search_emb"]:
            raise ValueError(
                "Please choose a valid process type ('obj' for preannotation, 'segment_emb' or 'search_emb'"
                "for segmentation or semantic search embedding precomputing)"
            )

        if not views:
            raise ValueError("Please select which views you want to process on.")

        # Load dataset
        dataset = Dataset(dataset_dir)

        # Create inference table
        table = self.create_table(process_type, views, dataset)

        # Load dataset tables
        ds_tables = dataset.open_tables()

        # Load inference table
        table_group = "objects" if process_type == "obj" else "embeddings"
        table_lance = ds_tables[table_group][table.name].to_lance()

        # Create URI prefix
        uri_prefix = dataset.media_dir.absolute().as_uri()

        # Add rows to tables
        save_batch_size = 1024
        with tqdm(desc="Processing dataset", total=dataset.num_rows) as progress:
            for save_batch_index in range(ceil(dataset.num_rows / save_batch_size)):
                # Load rows
                process_batches = self._load_rows(
                    dataset,
                    ds_tables,
                    splits,
                    batch_size,
                    save_batch_size,
                    save_batch_index,
                )

                # Process rows
                save_batch = []
                for process_batch in process_batches:
                    save_batch.extend(
                        self.preannotate(process_batch, views, uri_prefix, threshold)
                        if process_type == "obj"
                        else self.precompute_embeddings(
                            process_batch, views, uri_prefix
                        )
                        if process_type in ["segment_emb", "search_emb"]
                        else []
                    )
                    progress.update(batch_size)

                # Save rows
                pyarrow_save_batch = pa.Table.from_pylist(
                    save_batch,
                    schema=Fields(table.fields).to_schema(),
                )
                lance.write_dataset(
                    pyarrow_save_batch,
                    uri=table_lance.uri,
                    mode="append",
                )

        # Optimize and clear creation history
        table_lance.optimize.compact_files()
        table_lance.cleanup_old_versions(older_than=timedelta(0))

        return dataset

    def _load_rows(
        self,
        dataset: Dataset,
        ds_tables: dict[str, dict[str, lancedb.db.LanceTable]],
        splits: list[str],
        process_batch_size: int,
        save_batch_size: int,
        save_batch_index: int,
    ) -> list[pa.RecordBatch]:
        """Load dataset rows as list of process batches

        Args:
            dataset (Dataset): Dataset
            ds_tables (dict[str, dict[str, lancedb.db.LanceTable]]): Dataset tables
            splits (list[str]): Dataset splits
            process_batch_size (int): Rows per process batch
            save_batch_size (int): Rows per save batch (batch of process batches)
            save_batch_index (int): Save batch index

        Returns:
            list[pa.RecordBatch]: Process batches
        """

        # Batch parameters
        offset = save_batch_index * save_batch_size
        limit = min(dataset.num_rows, offset + save_batch_size)

        # Main table
        # pylint: disable=unused-variable
        pyarrow_table = ds_tables["main"]["db"].to_lance()
        pyarrow_batch = duckdb.query(
            f"SELECT * FROM pyarrow_table ORDER BY len(id), id LIMIT {limit} OFFSET {offset}"
        ).to_arrow_table()

        # Media tables
        for media_table in ds_tables["media"].values():
            # pylint: disable=unused-variable
            pyarrow_media_table = media_table.to_lance().to_table(
                limit=limit, offset=offset
            )
            # pylint: disable=unused-variable
            pyarrow_media_batch = duckdb.query(
                f"SELECT * FROM pyarrow_media_table ORDER BY len(id), id LIMIT {limit} OFFSET {offset}"
            ).to_arrow_table()
            pyarrow_batch = duckdb.query(
                "SELECT * FROM pyarrow_batch LEFT JOIN pyarrow_media_batch USING (id) ORDER BY len(id), id"
            ).to_arrow_table()

        # Filter splits
        if splits:
            split_ids = "'" + "', '".join(splits) + "'"
            pyarrow_batch = duckdb.query(
                f"SELECT * FROM pyarrow_batch WHERE split in ({split_ids})"
            ).to_arrow_table()

        # Convert to RecordBatch
        return pyarrow_batch.to_batches(max_chunksize=process_batch_size)

    def export_to_onnx(self, library_dir: Path):
        """Export Torch model to ONNX

        Args:
            library_dir (Path): Dataset library directory
        """
