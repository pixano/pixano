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

import logging
from typing import Any, Callable, Iterator, Sequence

from pixano.schemas import MEDIA_TYPES, MediaType, media_type_of

from .media import MediaResolver, ResolvedMedia
from .writer import DatasetReadSource


__all__ = ["MEDIA_TYPES", "JobReader", "MediaType", "media_type_of"]


logger = logging.getLogger("pixano-worker")

# How many rows we fetch per request when enumerating a table. Enough to amortise the round
# trip, few enough that a dataset of several million items does not fit in memory at once.
PAGE_SIZE = 2_000


class JobReader:
    """Reads a dataset on behalf of a job kind.

    Attributes:
        media: How to designate a media for the inference.
    """

    def __init__(self, open_dataset: Callable[[], DatasetReadSource], media: MediaResolver) -> None:
        """Bind a reader to a dataset and to the way its media are resolved."""
        self._open_dataset = open_dataset
        self._dataset: DatasetReadSource | None = None
        self.media = media

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

    def resolve_media(self, table_name: str, view: Any) -> ResolvedMedia | None:
        """Designate a media for the inference — a path if possible, the bytes otherwise."""
        return self.media.resolve(self.dataset, table_name, view)
