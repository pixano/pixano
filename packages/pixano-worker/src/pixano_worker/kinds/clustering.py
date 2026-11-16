# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The clustering job kind: a dataset's records grouped by their embeddings (backend-processing §24).

The groups are found over the whole dataset at once, so the job is one chunk, whose tasks are the
records: a record with an embedding gets a group — or none, for HDBSCAN's noise —, one without is
skipped. A record holds a vector per medium: it is placed by their mean, each vector made of unit
length first, as the cosine distance of the search reads them.

Each run is kept: its rows hold the records' groups, keyed by the run and the record, and the
dataset records what the run was. A chunk replayed writes its rows over its own, its groups found
again from the same vectors with the same seed: alike, if not to the last record at a group's edge,
as the order the vectors are read in and the threads' sums may change.

scikit-learn and SciPy are imported with the work that needs them: a worker that cannot load them
still runs every other kind.
"""

import logging
import math
import threading
import time
from collections import Counter
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any

import numpy as np
from pydantic import Field

from pixano.clustering.runs import Clustering, ClusteringAlgorithm
from pixano.schemas import NOISE_CLUSTER

from ..progress import ChunkProgress
from ..reader import JobReader, RecordVectors
from ..writer import JobWriter
from .base import Chunk, JobKind, JobParams, Outcome


log = logging.getLogger("pixano-worker")

#: How many groups K-Means makes by default, and at most: groups of a thousand are no longer gone
#: through one by one.
DEFAULT_CLUSTERS = 8
MAX_CLUSTERS = 1_000
#: Groups need two at least.
MIN_CLUSTERS = 2
#: The fewest records HDBSCAN calls a group by default, and the bounds of that size: a group of one
#: record is no group, and groups of more than a hundred thousand records are a few on any dataset.
DEFAULT_MIN_CLUSTER_SIZE = 10
MIN_CLUSTER_SIZE = 2
MAX_MIN_CLUSTER_SIZE = 100_000

#: The dimensions HDBSCAN reads the vectors in. Its density estimates lose their meaning over many
#: dimensions, and its time grows with them: the vectors are projected on their main directions first.
HDBSCAN_DIMENSIONS = 50
#: The neighbours HDBSCAN reads a record's density from, at most. scikit-learn takes as many as the
#: fewest records a group holds, and keeps their distances for every record, 16 bytes each: 16 GB
#: over a million records asked for groups of a thousand. Fifty keep them under 800 MB there, and
#: leave groups of fifty records or fewer — the default among them — as scikit-learn finds them.
HDBSCAN_MAX_NEIGHBOURS = 50
#: The seed of every random choice, so that a run replayed groups the records alike.
SEED = 0
#: The records a chunk of weight one groups; its weight grows as the square of its records over that.
#: Measured on 2026-11-06 on a laptop, on vectors of 512 dimensions gathered around a hundred
#: directions (`scripts/measure_clustering.py`): HDBSCAN grouped 50,000 records in 100 s and 100,000
#: in 336 s, as their number to the power 1.75; K-Means grouped 200,000 in 2.7 s. A chunk of weight
#: one is given `PIXANO_WORKER_CHUNK_TIMEOUT_S`, half an hour by default: the square keeps about
#: three times the time HDBSCAN was measured to need, from 150,000 records on, for a slower machine.
RECORDS_OF_UNIT_WEIGHT = 150_000

#: How often a chunk waiting for an earlier grouping of its dataset checks that it is still awaited.
GROUPING_WAIT_CHECK_S = 2.0

# Why a job is refused.
NO_EMBEDDINGS = "this dataset has no embeddings: compute them first, with the embeddings job"
NO_VECTOR_OF_MODEL = "the embeddings of '{model}' hold no vector: compute them first, with the embeddings job"
EMBEDDINGS_GONE = "the embeddings of '{model}' went since the job was planned: compute them again"
NO_RECORDS = "this dataset has no record to group"
NO_VECTORS = "no record of this dataset has a vector to group by: compute the embeddings again"


class ClusteringParams(JobParams):
    """Parameters of the clustering job.

    Attributes:
        algorithm: How the records are grouped.
        clusters: How many groups K-Means makes.
        min_cluster_size: The fewest records HDBSCAN calls a group.
        model: The embeddings model whose vectors are grouped — its name, or its space's id —;
            empty: the dataset's default one.
    """

    algorithm: ClusteringAlgorithm = Field(
        default=ClusteringAlgorithm.KMEANS,
        description="How the records are grouped: K-Means into the number of groups asked, HDBSCAN into as "
        "many as the embeddings hold, the records between them in none.",
    )
    clusters: int = Field(
        default=DEFAULT_CLUSTERS, ge=MIN_CLUSTERS, le=MAX_CLUSTERS, description="How many groups K-Means makes."
    )
    min_cluster_size: int = Field(
        default=DEFAULT_MIN_CLUSTER_SIZE,
        ge=MIN_CLUSTER_SIZE,
        le=MAX_MIN_CLUSTER_SIZE,
        description="The fewest records HDBSCAN calls a group.",
    )
    model: str = Field(
        default="",
        description="The embeddings model to group by — its name, or its space's id; empty: the dataset's default.",
    )


class ClusteringKind(JobKind[ClusteringParams]):
    """Groups a dataset's records by their embeddings, with K-Means or HDBSCAN."""

    name = "clustering"
    params_model = ClusteringParams
    # A group found by an algorithm over vectors is no model's prediction to review.
    source_type = "other"

    def plan(self, reader: JobReader, params: ClusteringParams) -> Iterable[Chunk]:
        """One chunk over every record: the groups are found over the whole dataset at once.

        The chunk names the space whose vectors it groups, so that one run reads one model's
        vectors, whatever becomes the default meanwhile.

        Raises:
            ValueError: The dataset has no embeddings, or none of the model named, or no record.
        """
        space = reader.dataset.record_embedding_space(params.model or None)
        if space is None and params.model:
            raise ValueError(f"this dataset holds no embeddings of '{params.model}'")
        if space is None:
            raise ValueError(NO_EMBEDDINGS)
        if reader.count(space["table"]) == 0:
            raise ValueError(NO_VECTOR_OF_MODEL.format(model=space["model_id"]))
        records = reader.count("records")
        if records == 0:
            raise ValueError(NO_RECORDS)
        yield Chunk(
            payload={"model": space["model_id"], "space": space["id"]}, task_count=records, weight=_weight(records)
        )

    def prepare(self, writer: JobWriter, params: ClusteringParams) -> None:
        """Give the dataset the table of its records' clusters if it has none."""
        writer.ensure_record_clusters()

    def process(self, reader: JobReader, payload: dict[str, Any], params: ClusteringParams) -> dict[str, Any]:
        """Read every vector, place each record by their mean, and group the records.

        The chunk stops, writing nothing, when its job is cancelled: checked once the vectors are
        read, between HDBSCAN's projection and its grouping, and once the groups are found — not
        during scikit-learn's own work, which nothing interrupts. A worker groups one dataset's
        records once at a time (`_grouping_of`).

        Raises:
            ValueError: The model's embeddings went since the job was planned, or hold no vector of a
                record the dataset holds.
        """
        with _grouping_of(reader.dataset.info.id, reader.progress):
            started = time.perf_counter()
            vectors = reader.record_vectors(payload["space"])
            if vectors is None:
                raise ValueError(EMBEDDINGS_GONE.format(model=payload["model"]))
            records, places = _placed(vectors, held=set(reader.all_ids("records")))
            # The matrix read is the largest thing a chunk holds: gone before the grouping works.
            del vectors
            if not records:
                raise ValueError(NO_VECTORS)
            read_s = time.perf_counter() - started
            reader.progress.stop_if_cancelled()
            started = time.perf_counter()
            groups = _grouped(places, params, between_steps=reader.progress.stop_if_cancelled)
            reader.progress.stop_if_cancelled()
        reader.progress.advance_to(len(records))
        return {
            "model": payload["model"],
            "clusters": dict(zip(records, (int(group) for group in groups), strict=True)),
            "phases_s": {"read": read_s, "grouping": time.perf_counter() - started},
        }

    def outcome(self, result: dict[str, Any], payload: dict[str, Any], task_count: int) -> Outcome:
        """The records: produced when grouped — noise included —, skipped without a vector to group by."""
        produced = min(len(result["clusters"]), task_count)
        return Outcome(produced=produced, skipped=task_count - produced)

    def write(
        self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: ClusteringParams
    ) -> None:
        """Write the run's groups and what the run was, which the explorer names its column with."""
        started = time.perf_counter()
        clusters: dict[str, int] = result["clusters"]
        parameters: dict[str, int | float | str | bool] = (
            {"clusters": params.clusters}
            if params.algorithm is ClusteringAlgorithm.KMEANS
            else {"min_cluster_size": params.min_cluster_size}
        )
        found = Clustering(
            run_id=writer.job_id,
            algorithm=params.algorithm,
            parameters=parameters,
            model=result["model"],
            clusters=0,
            noise=0,
            records=0,
            computed_at=datetime.now(timezone.utc),
        ).counted(clusters)
        run = writer.write_clustering(found, clusters)
        phases = result.get("phases_s", {})
        log.info(
            "job %s: phases read %.3f s, grouping %.3f s, write %.3f s (%d record(s) in %d group(s), %d noise)",
            writer.job_id,
            phases.get("read", 0.0),
            phases.get("grouping", 0.0),
            time.perf_counter() - started,
            run.records,
            run.clusters,
            run.noise,
        )


# Each dataset's grouping lock, by dataset (`_grouping_of`), and what guards the dictionary.
_groupings: dict[str, threading.Lock] = {}
_groupings_guard = threading.Lock()


@contextmanager
def _grouping_of(dataset_id: str, progress: ChunkProgress) -> Iterator[None]:
    """Hold the worker's one grouping of a dataset, waiting while another attempt holds it.

    An attempt the worker stopped waiting for — past its time limit — runs on to its grouping's end,
    which nothing interrupts, then stops without writing. Its chunk's next attempt waits for it rather
    than grouping beside it: two groupings would hold every vector twice, and each attempt after them
    once more. A chunk waiting stops as soon as it is told to: its job cancelled, or no longer awaited.

    Args:
        dataset_id: The dataset whose records are grouped.
        progress: The waiting chunk's progress.

    Raises:
        ChunkCancelled: The chunk was told to stop while it waited.
    """
    with _groupings_guard:
        lock = _groupings.setdefault(dataset_id, threading.Lock())
    while not lock.acquire(timeout=GROUPING_WAIT_CHECK_S):
        progress.stop_if_cancelled()
    try:
        progress.stop_if_cancelled()
        yield
    finally:
        lock.release()


def _weight(records: int) -> int:
    """A chunk's weight: one, or the square of its records over `RECORDS_OF_UNIT_WEIGHT`, rounded up."""
    return max(1, math.ceil((records / RECORDS_OF_UNIT_WEIGHT) ** 2))


def _placed(vectors: RecordVectors, held: set[str]) -> tuple[list[str], np.ndarray]:
    """Each record the dataset holds once, placed by the mean of its vectors, each of unit length first.

    A vector counts once per medium (`_counted`). The mean is a sparse product — a matrix of the
    records by the vectors, each vector weighing the inverse of its length — so that the vectors are
    neither copied nor sorted: the places are the only matrix made, in the order of the records'
    identifiers. A record whose vectors cancel out, placed nowhere, is not grouped.

    Returns:
        The records, in the order of their identifiers, and their places as the rows of a matrix.
    """
    from scipy import sparse

    matrix = vectors.vectors
    lengths = np.sqrt(np.einsum("ij,ij->i", matrix, matrix))
    counted = _counted(vectors, held, lengths)
    if not counted.any():
        return [], np.zeros((0, matrix.shape[1]), dtype=np.float32)
    rows = np.flatnonzero(counted)
    records, record_of_row = np.unique(np.asarray(vectors.record_ids, dtype=object)[rows], return_inverse=True)
    weights = (1 / lengths[rows]).astype(np.float32)
    means = sparse.csr_matrix((weights, (record_of_row, rows)), shape=(len(records), len(matrix)))
    places = np.asarray(means @ matrix, dtype=np.float32)
    sizes = np.sqrt(np.einsum("ij,ij->i", places, places))
    nowhere = sizes == 0
    if nowhere.any():
        records, places, sizes = records[~nowhere], places[~nowhere], sizes[~nowhere]
    places /= sizes[:, np.newaxis]
    return [str(record) for record in records], places


def _counted(vectors: RecordVectors, held: set[str], lengths: np.ndarray) -> np.ndarray:
    """Which vectors count for their record.

    - None whose record the dataset no longer holds: a record deleted keeps its vectors.
    - None of zeros, nor holding a value that is no number: neither points anywhere.
    - Of the others, one per medium, the first read: two for one medium — the application's
      computation beside a job's — would weigh it twice.
    - One of a whole record, written before embeddings were per medium, only for a record with no
      medium's vector that counts: beside its media's, it would weigh one of them twice.

    Returns:
        A mask of the vectors.
    """
    pointing = np.isfinite(lengths) & (lengths > 0)
    usable = [bool(pointing[row]) and record in held for row, record in enumerate(vectors.record_ids)]
    rows = list(zip(vectors.record_ids, vectors.view_ids, usable, strict=True))
    per_medium = {record for record, view, use in rows if view and use}
    seen: set[tuple[str, str]] = set()
    counted = np.zeros(len(lengths), dtype=bool)
    for row, (record, view, use) in enumerate(rows):
        if not use or (not view and record in per_medium) or (record, view) in seen:
            continue
        seen.add((record, view))
        counted[row] = True
    left_out = len(lengths) - int(counted.sum())
    if left_out:
        log.info(
            "clustering: %d vector(s) of %d left out — a medium's second, a record's beside its media's, "
            "a deleted record's, or pointing nowhere",
            left_out,
            len(lengths),
        )
    return counted


def _grouped(places: np.ndarray, params: ClusteringParams, between_steps: Callable[[], None]) -> np.ndarray:
    """Each record's group, numbered from 0 by decreasing size; `NOISE_CLUSTER` for HDBSCAN's noise.

    The places are worked on where they are, not copied: they are the grouping's alone.

    Args:
        places: Each record's place, as the rows of a matrix; one record at least.
        params: How to group them.
        between_steps: Called between HDBSCAN's projection and its grouping: it stops the chunk of a
            job cancelled meanwhile.

    Returns:
        Each record's group, in the order of the places.
    """
    from sklearn.cluster import HDBSCAN, KMeans
    from sklearn.decomposition import PCA

    count = len(places)
    if params.algorithm is ClusteringAlgorithm.KMEANS:
        # As many groups as asked, but no more than records.
        groups = KMeans(
            n_clusters=min(params.clusters, count), n_init="auto", random_state=SEED, copy_x=False
        ).fit_predict(places)
    elif count < params.min_cluster_size:
        # Too few records for one group of the size asked: all are noise.
        groups = np.full(count, NOISE_CLUSTER)
    else:
        dimensions = min(HDBSCAN_DIMENSIONS, places.shape[1], count)
        reduced = PCA(n_components=dimensions, random_state=SEED, copy=False).fit_transform(places)
        between_steps()
        groups = HDBSCAN(
            min_cluster_size=params.min_cluster_size,
            min_samples=min(params.min_cluster_size, HDBSCAN_MAX_NEIGHBOURS),
            copy=False,
        ).fit_predict(reduced)
    return _numbered_by_size(np.asarray(groups))


def _numbered_by_size(groups: np.ndarray) -> np.ndarray:
    """The groups numbered from 0 by decreasing size, the largest first; noise stays noise.

    An algorithm numbers its groups as it finds them: numbered by size, group 0 means the same thing
    in every run, and two runs read alike. Every negative label is noise: scikit-learn's HDBSCAN
    gives -1 for its noise, and other negative labels for vectors it cannot place.
    """
    sizes = Counter(int(group) for group in groups if group >= 0)
    order = sorted(sizes, key=lambda group: (-sizes[group], group))
    renamed = {group: rank for rank, group in enumerate(order)}
    return np.array([renamed.get(int(group), NOISE_CLUSTER) for group in groups], dtype=np.int64)
