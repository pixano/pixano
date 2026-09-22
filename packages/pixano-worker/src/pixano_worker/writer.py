# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The single write point for job results.

Every write of a job kind goes through here, for two reasons.

**Idempotence.** Results go to LanceDB while progress goes to PostgreSQL — two stores, hence
two writes that cannot share a transaction. A worker that dies between the two will redo the
chunk, and a chunk whose lease has expired can be picked up by another worker. Replaying must
therefore produce exactly the same content, never duplicates. For that, identifiers are
derived **from the work**, not from its execution: two runs of the same processing on the
same item write to the same rows.

**The single writer, later.** LanceDB does not have PostgreSQL's concurrency control, and
coordinating several workers writing to the same dataset is an open question. Having every
write go through one place is what will make that coordination possible without touching a
single job kind.
"""

import hashlib
import json
import logging
import threading
from collections import defaultdict
from datetime import timedelta
from typing import Any, Callable, Iterable, Protocol, Sequence


logger = logging.getLogger("pixano-worker")

# Length of derived identifiers. Long enough that a collision is out of reach, short enough to
# stay readable in a table.
_ID_LENGTH = 22

# Number of ranks probed beyond the current output when cleaning up. An output that shrinks
# does so by a few rows, not by a hundred; beyond that, leftovers remain, which is better than
# sweeping the table on every write.
_LEFTOVER_PROBE = 32

# Every write creates a version of the Lance table; a job of 50,000 images in chunks of 8
# creates 6,250 of them, and nothing reclaimed them — 101 versions measured after two jobs on
# 400 images. A fragmented table slows down every read from the explorer. So we compact at a
# regular interval, counted in writes, and we erase the versions old enough that no reader
# still holds them.
#
# Compaction runs under the dataset's write lock, in the chunk that triggers it. Measured
# (scripts/measure_compaction.py) on a classification table filled in batches of eight:
# 0.12 s median at 10,000 rows, 0.30 s at 30,000, with a maximum of 0.9 s — and it grows with
# the table. Acceptable for step 1; the policy — every N chunks, at the end of the job, or
# handed to a writer role — is decided before step 2's kinds write into tables that users are
# annotating at the same time.
COMPACT_EVERY_WRITES = 64
# One hour: longer than any read from a Pixano client holds a version — an explorer page, an
# export — so that no reader sees the version it is reading disappear. Shorter would risk
# failing a read in progress; longer only costs disk, until the old versions are erased.
KEEP_OLD_VERSIONS_FOR = timedelta(hours=1)

# The write count per table, per dataset. The runner serialises a dataset's writes, so the
# lock here only protects the counter itself.
_writes_since_compaction: defaultdict[tuple[str, str], int] = defaultdict(int)
_writes_guard = threading.Lock()


class DatasetReadSource(Protocol):
    """The only operations planning a job needs.

    A job kind must be able to enumerate what it is going to process without opening a dataset
    itself: the same reason as for writing — a single point, so that serialising or caching
    accesses one day remains a change to a single file.
    """

    def count_rows_where(self, table_name: str, where: str | None = None) -> int:
        """Count the rows of a table, without materialising it."""
        ...

    # The parameters mirror those of `Dataset` one to one, names included. A `**kwargs` here
    # would require a dataset to accept any keyword argument, which the real one does not: the
    # protocol no longer described the class it abstracts, and only mypy run on the whole
    # repository noticed.
    def get_data(
        self,
        table_name: str,
        ids: list[str] | None = None,
        limit: int | None = None,
        skip: int = 0,
        where: str | None = None,
        record_ids: list[str] | None = None,
    ) -> list[Any]:
        """Read rows from a table."""
        ...

    def get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str] | None:
        """The bytes of an embedded view, and their type."""
        ...

    def record_embedding_space(self) -> dict[str, Any] | None:
        """The model and dimension of the embeddings already computed, or None if there are none."""
        ...


class DatasetWriteTarget(Protocol):
    """The only operations writing a job needs.

    Depending on this contract rather than on `Dataset` follows the project rule — boundaries
    depend on interfaces — and lets a test provide a stand-in that behaves like LanceDB without
    having to pretend to be a complete dataset.
    """

    def update_data(self, table_name: str, data: list[Any]) -> Any:
        """Write rows, replacing those that already carry their identifier."""
        ...

    def delete_data(self, table_name: str, ids: list[str]) -> Any:
        """Delete rows by identifier."""
        ...

    def get_data(self, table_name: str, ids: list[str]) -> list[Any]:
        """Read the rows carrying these identifiers."""
        ...

    def has_record_embeddings(self) -> bool:
        """Whether a record embeddings table already exists."""
        ...

    def create_record_embedding_table(self, dim: int, model_id: str) -> None:
        """Create the embeddings table for a given vector width."""
        ...

    def record_embedding_space(self) -> dict[str, Any] | None:
        """The model and dimension of the embeddings already computed, or None if there are none."""
        ...

    def open_table(self, name: str) -> Any:
        """The LanceDB table itself, to compact it."""
        ...

    @property
    def info(self) -> Any:
        """The dataset's metadata, including the table schemas."""
        ...


def check_embedding_space(space: dict[str, Any] | None, model: str, dim: int | None = None) -> None:
    """Refuse to add vectors from another model to an embeddings table.

    Args:
        space: What the dataset declares about its table, or None if it has none.
        model: The job's model.
        dim: The dimension of the vectors, when known.

    Raises:
        ValueError: The table carries another model or another dimension.
    """
    if space is None:
        return
    existing_model = space.get("model_id")
    if existing_model != model:
        raise ValueError(
            f"this dataset already carries embeddings from model '{existing_model}': adding those of "
            f"'{model}' would mix two models in a single table and skew the search. "
            "Delete the existing embeddings table, or rerun the job with that model."
        )
    existing_dim = space.get("dim")
    if dim is not None and existing_dim is not None and int(existing_dim) != dim:
        raise ValueError(
            f"model '{model}' returns vectors of dimension {dim}, the existing table has dimension {existing_dim}"
        )


def derive_id(kind: str, key: str, index: int = 0) -> str:
    """Build a stable identifier for an output.

    Identity comes from the **work** — which processing, on what, which output — and not from
    the execution that produced it. This is what makes a rerun job replace its results instead
    of duplicating them: an identifier that carried the job would produce new rows on every
    submission.

    Args:
        kind: The job kind, so that two processings do not step on each other.
        key: What the output is about — an item's identifier, generally.
        index: The rank of the output when there are several for the same key.

    Returns:
        A deterministic identifier.
    """
    digest = hashlib.blake2b(f"{kind}\x00{key}\x00{index}".encode(), digest_size=16).hexdigest()
    return digest[:_ID_LENGTH]


class JobWriter:
    """Writes a job's outputs into a dataset, in a replayable way.

    Attributes:
        dataset: The target dataset.
        kind: The job kind that writes, to derive the identifiers.
        job_id: The job, kept as provenance.
    """

    def __init__(
        self,
        open_dataset: Callable[[], DatasetWriteTarget],
        kind: str,
        job_id: str,
        source_type: str = "model",
        reopen_dataset: Callable[[], DatasetWriteTarget] | None = None,
        dataset_id: str | None = None,
    ) -> None:
        """Bind a writer to a job and to its dataset.

        The dataset is opened on first use, not at construction: a job kind that writes nothing
        must not require a dataset to exist, and the runner builds a writer for every chunk
        without knowing whether that chunk will use it.

        Args:
            open_dataset: Opens the dataset — from a cache, generally.
            kind: The job kind that writes.
            job_id: The job, kept as provenance.
            source_type: What the kind declares it produces.
            reopen_dataset: Reopens the dataset **bypassing any cache**, to reread what another
                process may have created in it meanwhile. Without it, `open_dataset` is
                authoritative.
            dataset_id: The dataset's identifier, key of the write count that decides
                compactions. Without it, the writer counts for itself alone.
        """
        self._open_dataset = open_dataset
        self._dataset_id = dataset_id
        self._reopen_dataset = reopen_dataset or open_dataset
        self._dataset: DatasetWriteTarget | None = None
        self.kind = kind
        self.job_id = job_id
        self.source_type = source_type

    @property
    def dataset(self) -> DatasetWriteTarget:
        """The target dataset, opened on demand."""
        if self._dataset is None:
            self._dataset = self._open_dataset()
        return self._dataset

    def provenance(self) -> dict[str, str]:
        """What it takes to trace an output back to the processing that produced it.

        The annotation schemas carry `source_type`, `source_name` and `source_metadata`;
        filling them here rather than in every job kind guarantees that no job output lands in
        a dataset without knowing where it came from. The `source_type` vocabulary is that of
        the schemas — `model`, `human`, `ground_truth`, `other` — and it is the job kind that
        declares which one describes it.
        """
        return {
            "source_type": self.source_type,
            "source_name": self.kind,
            "source_metadata": json.dumps({"job_id": self.job_id}),
        }

    def ids_for(self, key: str, count: int) -> list[str]:
        """The identifiers a key will occupy for `count` outputs."""
        return [derive_id(self.kind, key, index) for index in range(count)]

    def replace(self, table_name: str, key: str, rows: Sequence[Any]) -> list[str]:
        """Write a key's outputs, fully replacing the previous ones.

        Two operations, and both are necessary: the rows are upserted on their derived
        identifier, then **the surplus rows of a previous run are deleted**. Without that second
        step, a replay that produced fewer outputs than before — a model that detects two
        objects where it used to see five — would leave three orphan rows that nothing would
        ever clean up.

        Args:
            table_name: The target table.
            key: What these outputs are about, typically an item identifier.
            rows: The rows to write. Their `id` field is overwritten.

        Returns:
            The identifiers written.
        """
        written = self.ids_for(key, len(rows))
        for row, row_id in zip(rows, written):
            row.id = row_id

        if rows:
            self.dataset.update_data(table_name, list(rows))
            self._count_write(table_name)

        self._drop_leftovers(table_name, key, kept=len(rows))
        return written

    def _count_write(self, table_name: str) -> None:
        """Count a write, and compact the table once enough have accumulated."""
        # An identifier rather than the object: a reopened dataset is another object for the
        # same table, and the address of a freed object gets reused.
        key = (self._dataset_id or f"writer-{id(self)}", table_name)
        with _writes_guard:
            _writes_since_compaction[key] += 1
            due = _writes_since_compaction[key] >= COMPACT_EVERY_WRITES
            if due:
                _writes_since_compaction[key] = 0
        if due:
            self.compact(table_name)

    def compact(self, table_name: str) -> None:
        """Merge a table's fragments and erase its old versions.

        A failed compaction is not a chunk failure: its rows are written. We log it, and the
        next one will retry.
        """
        try:
            self.dataset.open_table(table_name).optimize(cleanup_older_than=KEEP_OLD_VERSIONS_FOR)
        except Exception as error:
            logger.warning("job %s: cannot compact %s (%s)", self.job_id, table_name, error)

    def _drop_leftovers(self, table_name: str, key: str, kept: int) -> None:
        """Erase what a previous run had written beyond `kept`.

        Since identifiers are derived from a sequence of indices, the survivors of a shorter
        replay are exactly the next ranks. We probe a bounded number of them: beyond that, an
        output that shrank by more than `_LEFTOVER_PROBE` rows would leave leftovers, which is
        preferable to sweeping the table on every write.
        """
        candidates = [derive_id(self.kind, key, index) for index in range(kept, kept + _LEFTOVER_PROBE)]
        existing = self._existing(table_name, candidates)
        if existing:
            self.dataset.delete_data(table_name, existing)
            logger.debug("job %s: %d stale row(s) removed for %s", self.job_id, len(existing), key)

    def _existing(self, table_name: str, ids: Iterable[str]) -> list[str]:
        """Among these identifiers, those actually in the table."""
        wanted = list(ids)
        if not wanted:
            return []
        found = self.dataset.get_data(table_name, ids=wanted)
        return [row.id for row in found]

    # The canonical name of the record embeddings table in Pixano.
    EMBEDDING_TABLE = "embeddings"

    def write_record_embeddings(self, record_ids: Sequence[str], vectors: Sequence[Any], model: str) -> None:
        """Write one vector per record, replacing the previous one.

        The table is not an ordinary one: its width depends on the model, so it can only be
        created once a first vector is known. Creating on the first pass avoids requiring the
        job kind to know its model's dimension.

        An existing table only accepts vectors of the model and dimension it declares. Mixing
        two models in a single table raises no error on write when their dimensions coincide —
        and silently skews every similarity search, since the table keeps announcing the old
        model.

        Raises:
            ValueError: The vectors do not match the records, or the existing table was
                computed with another model or another dimension.
        """
        if len(record_ids) != len(vectors):
            raise ValueError(f"{len(record_ids)} records for {len(vectors)} vectors")
        if not vectors:
            return

        dataset = self.dataset
        dim = len(vectors[0])
        if not dataset.has_record_embeddings():
            # Reread the dataset bypassing the cache before creating: creation overwrites a
            # table that would already exist, and another worker may have created it since this
            # one opened the dataset. Two workers creating at the same instant are not covered —
            # that is the per-dataset writer role that step 4 must decide.
            dataset = self._dataset = self._reopen_dataset()
        if not dataset.has_record_embeddings():
            dataset.create_record_embedding_table(dim=dim, model_id=model)
        else:
            check_embedding_space(dataset.record_embedding_space(), model, dim)

        schema = dataset.info.tables[self.EMBEDDING_TABLE]
        rows = [
            schema(id=derive_id(self.kind, record_id, 0), record_id=record_id, vector=list(vector))
            for record_id, vector in zip(record_ids, vectors)
        ]
        dataset.update_data(self.EMBEDDING_TABLE, rows)
        self._count_write(self.EMBEDDING_TABLE)
