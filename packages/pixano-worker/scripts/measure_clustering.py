# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Measure how long the clustering job takes to group a dataset's records, and the memory it holds.

The job is one chunk over every record (backend-processing §24): its weight, which multiplies its
time limit, follows the time measured here. For each number of records, this script places them by
their vectors and groups them as the job does (`kinds/clustering.py`), and reports:

- how long placing the records took, and each algorithm's grouping;
- the most memory held at once meanwhile, the vectors' matrix included, let go before the grouping
  as the job lets it go — not the Arrow table the job reads them from, which LanceDB's memory pool
  holds and Python does not see.

The vectors are synthetic but shaped like a vision model's: unit vectors gathered around a hundred
directions, as the images of a dataset gather around what they show. Uniform random vectors would
leave HDBSCAN no group to find, and time it on noise.

Usage:
    uv run --directory packages/pixano-worker python scripts/measure_clustering.py \
        --records 10000,50000 --algorithms kmeans,hdbscan
"""

import argparse
import time
import tracemalloc

import numpy as np
from pixano_worker.kinds.clustering import ClusteringKind, _grouped, _placed
from pixano_worker.reader import RecordVectors

from pixano.schemas import NOISE_CLUSTER


#: The dimension of the vectors: CLIP's, and MobileCLIP's.
DIMENSIONS = 512
#: The directions the vectors gather around, and how far they spread from them.
DIRECTIONS = 100
SPREAD = 0.05
#: Bytes in a megabyte, for the report.
MEGABYTE = 1024 * 1024


def _vectors(records: int, seed: int = 0) -> RecordVectors:
    """One vector per record, each near one of `DIRECTIONS` directions."""
    rng = np.random.default_rng(seed)
    centres = rng.normal(size=(DIRECTIONS, DIMENSIONS)).astype(np.float32)
    centres /= np.linalg.norm(centres, axis=1, keepdims=True)
    vectors = centres[rng.integers(0, DIRECTIONS, records)]
    vectors += rng.normal(scale=SPREAD, size=vectors.shape).astype(np.float32)
    record_ids = [f"record-{n:08d}" for n in range(records)]
    return RecordVectors(record_ids=record_ids, view_ids=[f"{record}-image" for record in record_ids], vectors=vectors)


def _measure(records: int, algorithm: str) -> None:
    # Traced from before the vectors are made, so that the most memory held counts them; the most
    # held while they were made — temporaries of this script's own — set aside.
    tracemalloc.start()
    vectors = _vectors(records)
    held = set(vectors.record_ids)
    params = ClusteringKind().validate_params({"algorithm": algorithm})
    tracemalloc.reset_peak()
    started = time.perf_counter()
    _found, places = _placed(vectors, held)
    placed_s = time.perf_counter() - started
    vectors_mb = vectors.vectors.nbytes / MEGABYTE
    del vectors
    started = time.perf_counter()
    groups = _grouped(places, params, between_steps=lambda: None)
    grouped_s = time.perf_counter() - started
    _current, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    found = len(set(groups.tolist()) - {NOISE_CLUSTER})
    noise = int((groups == NOISE_CLUSTER).sum())
    print(
        f"{records:>9,} records  {algorithm:<8} placed {placed_s:7.2f} s  grouped {grouped_s:8.2f} s  "
        f"{found:>4} groups  {noise:>7,} noise  peak {peak / MEGABYTE:8.0f} MB "
        f"(vectors {vectors_mb:.0f} MB)"
    )


def main() -> None:
    """Measure each number of records with each algorithm asked."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--records", default="10000,50000", help="numbers of records, comma-separated")
    parser.add_argument("--algorithms", default="kmeans,hdbscan", help="kmeans, hdbscan, or both")
    arguments = parser.parse_args()
    for records in (int(value) for value in arguments.records.split(",")):
        for algorithm in arguments.algorithms.split(","):
            _measure(records, algorithm)


if __name__ == "__main__":
    main()
