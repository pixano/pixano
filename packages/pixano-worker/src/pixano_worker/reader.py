# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The single read point of a dataset, for planning a job.

Symmetric to the writer, and for the same reason: a job kind enumerates what it is going to
process without opening a dataset itself. This keeps a single door into LanceDB, which will
make it possible to put a cache or a coordination there without touching a single kind.

The dataset is opened on first use: a kind whose work fits in its parameters has nothing to
read, and must not require a dataset to exist.
"""

import io
import logging
import os
from dataclasses import dataclass
from typing import Any, BinaryIO, Callable, Iterator, Sequence

import numpy as np
import pyarrow.compute as pc

from pixano.schemas import MEDIA_TYPES, MediaType, media_type_of

from .media import MediaResolver, ResolvedMedia
from .progress import ChunkProgress
from .writer import DatasetReadSource


__all__ = ["MEDIA_TYPES", "JobReader", "MediaType", "media_type_of"]


logger = logging.getLogger("pixano-worker")

# How many rows we fetch per request when enumerating a table. Enough to amortise the round
# trip, small enough that a dataset of several million items is never held in memory at once.
PAGE_SIZE = 2_000


@dataclass(frozen=True)
class RecordVectors:
    """Every vector of a dataset's embeddings, with the record and the medium it belongs to.

    Attributes:
        record_ids: The record of each vector. A record holds one per medium, so it may come several
            times.
        view_ids: The medium of each vector; empty for one of a whole record, written before
            embeddings were per medium.
        vectors: The vectors, as the rows of a matrix, in the order of the two lists.
    """

    record_ids: list[str]
    view_ids: list[str]
    vectors: np.ndarray


class JobReader:
    """Reads a dataset on behalf of a job kind.

    Attributes:
        media: How to designate a media for the inference.
        progress: The running chunk's progress: a long chunk says here how far it got, and stops
            between two of its steps when its job was cancelled. Planning has no chunk: its
            progress counts nothing.
    """

    def __init__(
        self,
        open_dataset: Callable[[], DatasetReadSource],
        media: MediaResolver,
        progress: ChunkProgress | None = None,
    ) -> None:
        """Bind a reader to a dataset, to the way its media are resolved, and to a running chunk."""
        self._open_dataset = open_dataset
        self._dataset: DatasetReadSource | None = None
        self.media = media
        self.progress = progress if progress is not None else ChunkProgress(0)

    @property
    def dataset(self) -> DatasetReadSource:
        """The target dataset, opened on demand."""
        if self._dataset is None:
            self._dataset = self._open_dataset()
        return self._dataset

    def count(self, table_name: str, where: str | None = None) -> int:
        """How many rows a table contains, without materialising it."""
        return self.dataset.count_rows_where(table_name, where)

    def ids(self, table_name: str, where: str | None = None) -> Iterator[str]:
        """Enumerate a table's identifiers, by pages.

        By pages, because a job may target hundreds of thousands of items and planning must
        stay tractable in memory.
        """
        total = self.count(table_name, where)
        for offset in range(0, total, PAGE_SIZE):
            rows = self.dataset.get_data(table_name, limit=PAGE_SIZE, skip=offset, where=where)
            for row in rows:
                yield row.id

    def media_tables(self, media_type: str) -> list[str]:
        """The dataset's tables that hold media of this type, in a stable order.

        Pixano stores every view of a type in one canonical table — nuScenes' six cameras are
        all rows of `images`, told apart by their logical name — so this is usually one table.
        """
        return sorted(name for name, schema in self.dataset.info.tables.items() if media_type_of(schema) == media_type)

    def rows(self, table_name: str, ids: Sequence[str]) -> list[Any]:
        """Read specific rows, by identifier."""
        return self.dataset.get_data(table_name, ids=list(ids))

    def record_vectors(self, model: str | None = None) -> RecordVectors | None:
        """Every vector of one model's embeddings, with its record and its medium, for a computation
        over the whole dataset.

        One read of their three columns (`Dataset.read_record_vectors`): a clustering groups every
        record at once. The vectors are held in memory once, as a matrix: 2 GB for a million of 512
        dimensions.

        Args:
            model: The model — its space's id or its name —; the dataset's default one when None.

        Returns:
            The vectors, or None when the dataset has no embeddings of that model.
        """
        table = self.dataset.read_record_vectors(model)
        if table is None:
            return None
        # A vector another writer of the table left empty points nowhere: left out, as one of zeros is.
        # Filtered only then: a filter copies every vector.
        if table.column("vector").null_count:
            table = table.filter(pc.is_valid(table.column("vector")))
        vectors = table.column("vector").combine_chunks()
        matrix = vectors.flatten().to_numpy(zero_copy_only=False).reshape(len(vectors), vectors.type.list_size)
        return RecordVectors(
            record_ids=table.column("record_id").to_pylist(),
            view_ids=[view_id or "" for view_id in table.column("view_id").to_pylist()],
            vectors=matrix,
        )

    def all_ids(self, table_name: str) -> list[str]:
        """Every identifier of a table, read at once, for a computation over the whole dataset: the
        records a clustering checks its vectors against. `ids` reads a table by pages.

        Args:
            table_name: The table.

        Returns:
            Its identifiers.
        """
        return self.dataset.get_all_ids(table_name)

    def resolve_media(self, table_name: str, view: Any) -> ResolvedMedia | None:
        """Designate a media for the inference — a path if possible, the bytes otherwise."""
        return self.media.resolve(self.dataset, table_name, view)

    def open_media(self, table_name: str, view: Any) -> BinaryIO | None:
        """The media itself, for what a kind must read rather than send: its file, else its bytes.

        Returns:
            An open binary stream the caller closes, or None if this worker can reach neither.
        """
        path = self.media.local_path(view)
        if path is not None and os.path.isfile(path):
            return open(path, "rb")
        found = self.dataset.get_view_binary(table_name, view.id)
        if found is None or not found[0]:
            return None
        return io.BytesIO(found[0])
