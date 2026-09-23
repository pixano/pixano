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
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Protocol, Sequence


logger = logging.getLogger("pixano-worker")

# The provenance vocabulary of the Pixano schemas that means "a model produced this", and the
# review status such a row arrives with. The strings are the schemas' (`AnnotationSourceKind`,
# `ReviewStatus`); named here so that the writer does not import the application's schemas
# for two words.
MODEL_SOURCE = "model"
PENDING_REVIEW = "pending"

# Length of the digest that opens a derived identifier. Long enough that a collision is out of
# reach, short enough to stay readable in a table; the rank follows it, so that everything a
# key produced shares one prefix and can be found — and cleaned — exactly.
_ID_PREFIX_LENGTH = 16

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


@dataclass(frozen=True)
class ModelIdentity:
    """The model a job ran, as the inference declares it.

    Attributes:
        name: The model's name on the inference server — what the job's parameters name.
        version: What the server gives as the model's identity beyond its name — the checkpoint
            it loaded, typically. None when the server exposes nothing of the kind.
    """

    name: str
    version: str | None = None


class DatasetReadSource(Protocol):
    """The only operations planning a job needs.

    A job kind must be able to enumerate what it is going to process without opening a dataset
    itself: the same reason as for writing — a single point, so that serialising or caching
    accesses one day remains a change to a single file.
    """

    #: What the dataset holds: its tables and their schemas.
    info: Any

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

    def get_data(self, table_name: str, ids: list[str] | None = None, *, where: str | None = None) -> list[Any]:
        """Read the rows carrying these identifiers, or those matching a filter."""
        ...

    def has_record_embeddings(self) -> bool:
        """Whether a record embeddings table already exists."""
        ...

    def create_record_embedding_table(self, dim: int, model_id: str) -> None:
        """Create the embeddings table for a given vector width."""
        ...

    def drop_record_embeddings(self) -> None:
        """Delete the embeddings table and the model it declares."""
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


def derive_prefix(kind: str, key: str, model: str | None = None) -> str:
    """The prefix every output of (kind, model, key) shares."""
    digest = hashlib.blake2b(f"{kind}\x00{model or ''}\x00{key}".encode(), digest_size=16).hexdigest()
    return digest[:_ID_PREFIX_LENGTH]


def derive_id(kind: str, key: str, index: int = 0, model: str | None = None) -> str:
    """Build a stable identifier for an output.

    Identity comes from the **work** — which processing, with which model, on what, which
    output — and not from the execution that produced it. This is what makes a rerun job
    replace its results instead of duplicating them: an identifier that carried the job would
    produce new rows on every submission. The model is part of it because another model's
    outputs add to a kind's rather than replace them (step 2 design): two models, two sets of
    rows for the same key.

    The identifier is a prefix shared by everything the key produced, then the rank: this is
    what lets a replay find every row of a previous run by prefix, and delete exactly those
    beyond what it wrote — a bounded probe used to miss an output that shrank by more than
    its window.

    Args:
        kind: The job kind, so that two processings do not step on each other.
        key: What the output is about — an item's identifier, generally.
        index: The rank of the output when there are several for the same key.
        model: The model that produced it, when the kind runs one.

    Returns:
        A deterministic identifier.
    """
    return f"{derive_prefix(kind, key, model)}-{index}"


def _rank_of(row_id: str) -> int | None:
    """The rank a derived identifier carries after its prefix; None for an id that has none.

    The prefix is hexadecimal and fixed-length, so only a row written by hand under a derived
    identifier could lack a rank. It is left alone rather than failing every attempt of the
    chunk.
    """
    rank = row_id.rsplit("-", 1)[-1]
    return int(rank) if rank.isdigit() else None


def _is_reviewed(row: Any) -> bool:
    """Whether a human has looked at this row: then a rerun must leave it alone."""
    return getattr(row, "review_status", "") not in ("", PENDING_REVIEW)


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
        *,
        params: dict[str, Any] | None = None,
        model: ModelIdentity | None = None,
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
            params: The job's validated parameters, as the provenance records them — those that
                say what was computed, not how the engine ran it.
            model: The model the job ran, when the kind runs one.
        """
        self._open_dataset = open_dataset
        self._dataset_id = dataset_id
        self._reopen_dataset = reopen_dataset or open_dataset
        self._dataset: DatasetWriteTarget | None = None
        self.kind = kind
        self.job_id = job_id
        self.source_type = source_type
        self.params = params
        self.model = model

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

        `source_metadata` is self-contained: the job identifier is an opaque run label, since
        jobs are cleaned by truncation, and the kind, the model, its version and the
        parameters are what a reviewer needs to know how a row was produced without any
        table to look it up in.
        """
        metadata: dict[str, Any] = {"job_id": self.job_id, "kind": self.kind}
        if self.model is not None:
            metadata["model"] = self.model.name
            if self.model.version is not None:
                metadata["model_version"] = self.model.version
        if self.params is not None:
            metadata["params"] = self.params
        provenance = {
            "source_type": self.source_type,
            "source_name": self.kind,
            "source_metadata": json.dumps(metadata, sort_keys=True),
        }
        if self.source_type == MODEL_SOURCE:
            # A model's output arrives to be reviewed; a human's has nothing to review, and a
            # demonstration kind's is neither.
            provenance["review_status"] = PENDING_REVIEW
        return provenance

    def ids_for(self, key: str, count: int) -> list[str]:
        """The identifiers a key will occupy for `count` outputs."""
        return [derive_id(self.kind, key, index, self._model_name) for index in range(count)]

    @property
    def _model_name(self) -> str | None:
        return self.model.name if self.model is not None else None

    def replace(self, table_name: str, key: str, rows: Sequence[Any]) -> list[str]:
        """Write a key's outputs, fully replacing the previous ones.

        Three steps. What a previous run wrote for this (kind, model, key) is read by the
        prefix its identifiers share. **Rows a human reviewed are frozen**: accepted, corrected
        or rejected, they keep their rank and are not touched — a rerun replaces what is still
        pending, never what someone looked at (step 2 design). The new rows take the free
        ranks, in order, and are upserted; then **the pending rows of the previous run that no
        new row replaced are deleted**. Without that last step, a replay that produced fewer
        outputs than before — a model that detects two objects where it used to see five —
        would leave three orphan rows that nothing would ever clean up.

        The replacement is exact: scoped by (kind, model, key), which is what the prefix
        encodes, so another model's rows for the same key are left alone, and no output
        shrinks past what is cleaned.

        Args:
            table_name: The target table.
            key: What these outputs are about, typically an item identifier.
            rows: The rows to write. Their `id` field is overwritten.

        Returns:
            The identifiers written.
        """
        prefix = derive_prefix(self.kind, key, self._model_name)
        previous = [
            row
            for row in self.dataset.get_data(table_name, where=f"id LIKE '{prefix}-%'")
            if _rank_of(row.id) is not None
        ]
        frozen = {_rank_of(row.id) for row in previous if _is_reviewed(row)}

        written: list[str] = []
        rank = 0
        for row in rows:
            while rank in frozen:
                rank += 1
            row.id = f"{prefix}-{rank}"
            written.append(row.id)
            rank += 1

        if rows:
            self.dataset.update_data(table_name, list(rows))
            self._count_write(table_name)

        replaced = set(written)
        stale = [row.id for row in previous if row.id not in replaced and _rank_of(row.id) not in frozen]
        if stale:
            self.dataset.delete_data(table_name, stale)
            logger.debug("job %s: %d stale row(s) removed for %s", self.job_id, len(stale), key)
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

    # The canonical name of the record embeddings table in Pixano.
    EMBEDDING_TABLE = "embeddings"

    def drop_embeddings(self) -> None:
        """Delete the dataset's embeddings table, so that another model can fill it.

        Only for a kind's `prepare`, and only on an explicit parameter: this destroys every
        vector of the dataset. Harmless when there is no table.
        """
        self.dataset.drop_record_embeddings()
        logger.info("job %s: embeddings table dropped before recomputing", self.job_id)

    def write_media_embeddings(
        self, record_ids: Sequence[str], view_ids: Sequence[str], vectors: Sequence[Any], model: str
    ) -> None:
        """Write one vector per medium, replacing the previous one.

        An embedding belongs to a medium — one camera of a nuScenes record, not the record: a
        record with six images has six vectors, each carrying its `view_id`, and a search that
        finds a medium returns its record. The medium is the replacement key.

        The table is not an ordinary one: its width depends on the model, so it can only be
        created once a first vector is known. Creating on the first pass avoids requiring the
        job kind to know its model's dimension.

        An existing table only accepts vectors of the model and dimension it declares. Mixing
        two models in a single table raises no error on write when their dimensions coincide —
        and silently skews every similarity search, since the table keeps announcing the old
        model.

        Raises:
            ValueError: The vectors do not match the media, or the existing table was
                computed with another model or another dimension.
        """
        if not len(record_ids) == len(view_ids) == len(vectors):
            raise ValueError(f"{len(record_ids)} records, {len(view_ids)} media for {len(vectors)} vectors")
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
            schema(id=derive_id(self.kind, view_id, 0), record_id=record_id, view_id=view_id, vector=list(vector))
            for record_id, view_id, vector in zip(record_ids, view_ids, vectors)
        ]
        dataset.update_data(self.EMBEDDING_TABLE, rows)
        self._count_write(self.EMBEDDING_TABLE)
