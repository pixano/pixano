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
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Callable, Protocol, Sequence

from pixano.schemas import NOT_REVIEWED_STATUSES, AnnotationSourceKind, ReviewStatus


logger = logging.getLogger("pixano-worker")

# The provenance vocabulary of the Pixano schemas that means "a model produced this", and the
# review status such a row arrives with. Read from the schemas, as is which stored statuses mean
# "not reviewed yet" (`NOT_REVIEWED_STATUSES`): the application reviews what the writer writes,
# and both must read a row the same way.
MODEL_SOURCE = AnnotationSourceKind.MODEL.value
PENDING_REVIEW = ReviewStatus.PENDING.value

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
# the table. Decided for step 2 (backend-processing §19): the policy stays as it is until a
# compaction outlasts a chunk, and then moves out of the write lock; to measure at 500,000
# rows once a kind produces that volume.
COMPACT_EVERY_WRITES = 64
# One hour: longer than any read from a Pixano client holds a version — an explorer page, an
# export — so that no reader sees the version it is reading disappear. Shorter would risk
# failing a read in progress; longer only costs disk, until the old versions are erased.
KEEP_OLD_VERSIONS_FOR = timedelta(hours=1)

# Below this many vectors, a dataset's embeddings get no vector index: LanceDB's exact search
# answers fast enough there, and an index would only make the results approximate. A "similar
# to" runs one search per medium of the record — six on a nuScenes record —, so the line is drawn
# where six exact searches stay well inside the API's 500 ms p99 target: 25 ms each at 50,000
# vectors of 512 dimensions, 61 ms at 100,000, 162 ms at 300,000 (scripts/measure_vector_index.py,
# backend-processing §12). LanceDB's own guidance, for a single search, is twice as high.
VECTOR_INDEX_MIN_ROWS = 50_000

# The vector index the worker declares for the embeddings tables it creates. Measured on 100,000
# and 300,000 vectors of 512 dimensions (backend-processing §12): with the search's re-ranking
# (`Dataset._SEARCH_REFINE_FACTOR`), every type tried brings back 99.9% to 100% of the exact
# nearest records, in 8 to 17 ms; IVF_SQ trains in 2 to 3 s, where IVF_PQ takes 28 s and
# IVF_HNSW_SQ 35 to 89 s. A model's table created earlier keeps the type its space names — IVF_PQ,
# `Dataset`'s default — until that model is recomputed with `replace_existing_embeddings`: it trains
# slower, and finds 97% to 100% of the exact nearest records re-ranked, where IVF_SQ finds all of
# them at 50,000 vectors.
EMBEDDING_INDEX_TYPE = "IVF_SQ"

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
    """The only operations reading a job's dataset needs, to plan the job and process its chunks.

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

    def record_embedding_space(self, model: str | None = None) -> dict[str, Any] | None:
        """One model's embeddings, by its space's id or its name — the default ones when None —, or None."""
        ...

    def record_embeddings_fully_read(self) -> bool:
        """Whether the description of the embeddings was read entirely: if not, no job may change it."""
        ...

    def record_embedding_spaces(self) -> list[dict[str, Any]]:
        """Every embeddings space of the dataset, one per model and checkpoint."""
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

    def record_embedding_spaces(self) -> list[dict[str, Any]]:
        """Every embeddings space of the dataset, one per model and checkpoint."""
        ...

    def upsert_record_embeddings(
        self, model_id: str, checkpoint: str, rows: list[dict[str, Any]], *, index_type: str = ...
    ) -> dict[str, Any]:
        """Write a model's vectors into its space, created — with its vector index — if there is none."""
        ...

    def empty_model_record_embeddings(
        self, model_id: str, checkpoint: str = "", index_type: str | None = None
    ) -> dict[str, Any] | None:
        """Empty a model's embeddings, keeping its space, the other models' left as they are."""
        ...

    def open_table(self, name: str) -> Any:
        """The LanceDB table itself, to compact it."""
        ...

    @property
    def info(self) -> Any:
        """The dataset's metadata, including the table schemas."""
        ...


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
    outputs add to a kind's rather than replace them: two models, two sets of
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


def is_reviewed(row: Any) -> bool:
    """Whether a person accepted this row: then a rerun must leave it alone.

    Read as the application reads it (`pixano.schemas.NOT_REVIEWED_STATUSES`): a model's row
    without a status, re-imported from JSONL, was never reviewed.
    """
    return getattr(row, "review_status", "") not in NOT_REVIEWED_STATUSES


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
            dataset_id: The dataset's identifier, key of the write count that decides
                compactions. Without it, the writer counts for itself alone.
            params: The job's validated parameters, as the provenance records them — those that
                say what was computed, not how the engine ran it.
            model: The model the job ran, when the kind runs one.
        """
        self._open_dataset = open_dataset
        self._dataset_id = dataset_id
        # What counts this writer's writes: its dataset's, shared with every writer of the dataset,
        # or a key of its own — not its address, which a freed writer's may have been.
        self._count_key = dataset_id or f"writer-{uuid.uuid4().hex}"
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
        prefix its identifiers share. **Rows a person accepted are frozen**: they keep their rank
        and are not touched — a rerun replaces what is still pending, never what someone
        accepted. The new rows take the free ranks, in order, and are upserted; then **the
        pending rows of the previous run that no new row replaced are deleted**. Without that
        last step, a replay that produced fewer outputs than before — a model that detects two
        objects where it used to see five — would leave three orphan rows that nothing would
        ever clean up.

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
        frozen = {_rank_of(row.id) for row in previous if is_reviewed(row)}

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
        key = (self._count_key, table_name)
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

    def empty_embeddings(self, model: str, checkpoint: str = "") -> None:
        """Empty the embeddings of the job's model, so that it computes them again from nothing.

        Only for a kind's `prepare`, and only on an explicit parameter: this destroys every vector
        this model — this checkpoint of it — computed on the dataset. Its space keeps its place
        and the default; it gets the vector index this worker builds. The other models' vectors
        are left as they are. Harmless when the dataset holds none.

        Raises:
            AmbiguousModelError: Which of the model's spaces is this one's cannot be told.
        """
        emptied = self.dataset.empty_model_record_embeddings(model, checkpoint, index_type=EMBEDDING_INDEX_TYPE)
        if emptied is not None:
            logger.info("job %s: embeddings %s emptied before recomputing", self.job_id, emptied["id"])

    def write_media_embeddings(
        self,
        record_ids: Sequence[str],
        view_ids: Sequence[str],
        vectors: Sequence[Any],
        model: str,
        checkpoint: str = "",
    ) -> dict[str, Any] | None:
        """Write one vector per medium into its model's embeddings, replacing the previous one.

        An embedding belongs to a medium — one camera of a nuScenes record, not the record: a
        record with six images has six vectors, each carrying its `view_id`, and a search that
        finds a medium returns its record. The medium is the replacement key.

        Each model has a table of its own, a model being its name and its checkpoint: two models
        never share a table, which would skew every search silently when their dimensions
        coincide. The table's width depends on the model, so it is created with the first vectors:
        a kind need not know its model's dimension. The space is found or created, and the
        vectors written, under one acquisition of the dataset's write lock, which reads the
        dataset's description again (`Dataset.upsert_record_embeddings`): a space another worker
        created meanwhile is found, one it deleted is created again, never written into from what
        this worker read before.

        Args:
            record_ids: Each vector's record.
            view_ids: Each vector's medium.
            vectors: The vectors, all of one dimension.
            model: The model's name, as the inference serves it.
            checkpoint: The weights the inference loaded under that name; empty when it could not
                tell.

        Returns:
            The space written into; None without vectors.

        Raises:
            ValueError: The vectors do not match the media, the dataset holds this very model at
                another dimension, or its description of the embeddings cannot be read entirely.
            AmbiguousModelError: The checkpoint is not told, and the dataset holds several of the
                model's at that dimension.
        """
        if not len(record_ids) == len(view_ids) == len(vectors):
            raise ValueError(f"{len(record_ids)} records, {len(view_ids)} media for {len(vectors)} vectors")
        if not vectors:
            return None

        rows = [
            {
                "id": derive_id(self.kind, view_id, 0),
                "record_id": record_id,
                "view_id": view_id,
                "vector": list(vector),
            }
            for record_id, view_id, vector in zip(record_ids, view_ids, vectors)
        ]
        space = self.dataset.upsert_record_embeddings(model, checkpoint, rows, index_type=EMBEDDING_INDEX_TYPE)
        self._count_write(space["table"])
        return space

    def index_embeddings(self, model: str, min_rows: int | None = None) -> list[str]:
        """Index a model's embeddings for search, once a job has filled them.

        For a kind's `finalize`: an index is trained on every vector, so it is built once the job
        wrote them all, not chunk by chunk. The closing step has no chunk to tell it which of the
        model's checkpoints the job wrote — the weights may even have changed during the job —, so
        every space of the model's name is indexed: the job's among them. Two checkpoints of one
        name are rare, and indexing another one again costs time, never a vector.

        For each:

        - The last writes are compacted first, so that the index is trained on one tidy table.
        - The `record_id` index is always built: a search restricted to some records, and the
          lookup of a record's vectors for "similar to", filter on it.
        - The vector index only from `min_rows` vectors: below, exact search is fast enough, and
          an index would only make the results approximate. Its type and metric are those the
          space declares.

        Every index is rebuilt whole, never extended: one trained on the previous run's vectors
        would partition this run's badly. Training is random, so a rebuild gives an equivalent
        index rather than the same one, and a final chunk replayed after its worker died leaves
        the table as one run would. A table that shrank below `min_rows` keeps the vector index
        it had: still valid, and the search re-ranks what it finds. A space that cannot be indexed
        does not keep the others from being: its failure is raised once they all were tried.

        Not under the dataset's own write lock, as compaction is not: building an index changes
        no row, Lance commits it as a version of its own, and a person's save is never refused
        for its sake. A commit that conflicts with another writer of the table — the
        application's computation, a recompute, a rollback, another worker — fails the build,
        and the kind tries again later. The runner's lock still keeps this worker's other writes
        to the dataset out of the way. The runner reopens the dataset past the worker's cache
        before the closing step: the chunks may have created the model's space in another worker.

        Args:
            model: The model's name, as the inference serves it.
            min_rows: The table size from which a vector index is built; `VECTOR_INDEX_MIN_ROWS`
                by default, read at call time.

        Returns:
            The types of the vector indexes built: none when the model's spaces hold too few vectors.

        Raises:
            Exception: The first failure of a space's indexing, once every space was tried.
        """
        min_rows = VECTOR_INDEX_MIN_ROWS if min_rows is None else min_rows
        spaces = [space for space in self.dataset.record_embedding_spaces() if space["model_id"] == model]
        if not spaces:
            logger.warning("job %s: no embeddings of %s to index", self.job_id, model)
        built: list[str] = []
        failure: Exception | None = None
        for space in spaces:
            try:
                index_type = self._index_space(space, min_rows)
            except Exception as error:  # noqa: BLE001 — the model's other spaces are indexed all the same
                logger.warning("job %s: the embeddings %s could not be indexed: %s", self.job_id, space["id"], error)
                failure = failure or error
                continue
            if index_type is not None:
                built.append(index_type)
        if failure is not None:
            raise failure
        return built

    def _index_space(self, space: dict[str, Any], min_rows: int) -> str | None:
        """Index one space's table; the vector index built, if it holds enough vectors for one."""
        table_name = space["table"]
        self.compact(table_name)
        table = self.dataset.open_table(table_name)
        table.create_scalar_index("record_id", index_type="BTREE", replace=True)
        rows = table.count_rows()
        if rows < min_rows:
            logger.info(
                "job %s: %d vector(s) of %s, under the %d that call for a vector index: exact search",
                self.job_id,
                rows,
                space["id"],
                min_rows,
            )
            return None
        index_type = space.get("index_type", EMBEDDING_INDEX_TYPE)
        table.create_index(
            metric=space.get("metric", "cosine"), index_type=index_type, vector_column_name="vector", replace=True
        )
        logger.info(
            "job %s: %s vector index built over %d vector(s) of %s", self.job_id, index_type, rows, space["id"]
        )
        return index_type
