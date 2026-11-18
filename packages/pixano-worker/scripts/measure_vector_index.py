# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Measure what a vector index buys a dataset's embeddings, and what it costs.

An index makes a search approximate: it answers faster, but may miss some of the true nearest
neighbours. Below some size, the exact search LanceDB runs without an index is fast enough, and
an index only loses results. This script measures, on a dataset's embeddings table — one vector
per record, as the embeddings computation fills it:

- how long the exact search takes, as the table grows;
- how long each index type takes to build;
- how fast a search through it answers, and how many of the exact nearest records it still finds
  (its recall), with the search settings Pixano could use.

The vectors are synthetic but shaped like a vision model's: unit vectors gathered around a
thousand directions, as the images of a dataset gather around what they show. Uniform random
vectors would make every neighbour almost equally far, which no real dataset does, and would
understate what an index gets right.

Usage:
    uv run --directory packages/pixano-worker python scripts/measure_vector_index.py --rows 100000,300000
"""

import argparse
import statistics
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas.records import Record


# The dimension of the embeddings model the local stack serves (MobileCLIP2-S2), and of CLIP's
# ViT-B models: what a Pixano embeddings table holds today.
DIMENSION = 512

# How many directions the synthetic vectors gather around, and how far they spread from them.
# The spread is the standard deviation of the noise added to each coordinate of a unit
# direction: about the closeness of images of one subject in a vision model's space.
CLUSTERS = 1_000
SPREAD = 0.03

# Rows added per call when filling the table: large, since filling is not what is measured.
FILL_BATCH = 20_000

# The searches timed per setting, and how many records each asks for: the explorer's page of
# semantic search results.
QUERIES = 50
RECORDS_PER_QUERY = 50

# The seed of every random draw, so that two runs measure the same vectors.
SEED = 7


@dataclass(frozen=True)
class Setting:
    """One way of searching: an index type, and the query settings tried on it."""

    label: str
    index_type: str | None
    query: dict[str, Any]


SETTINGS = (
    Setting("exact search, no index", None, {}),
    Setting("IVF_PQ, default search", "IVF_PQ", {}),
    Setting("IVF_PQ, refine_factor 10", "IVF_PQ", {"refine_factor": 10}),
    Setting("IVF_SQ, default search", "IVF_SQ", {}),
    Setting("IVF_SQ, refine_factor 10", "IVF_SQ", {"refine_factor": 10}),
    Setting("IVF_HNSW_SQ, default search", "IVF_HNSW_SQ", {}),
    Setting("IVF_HNSW_SQ, refine_factor 10", "IVF_HNSW_SQ", {"refine_factor": 10}),
)


def synthetic_vectors(rows: int, rng: np.random.Generator) -> np.ndarray:
    """Unit vectors gathered around `CLUSTERS` directions."""
    directions = rng.standard_normal((CLUSTERS, DIMENSION)).astype(np.float32)
    directions /= np.linalg.norm(directions, axis=1, keepdims=True)
    vectors = directions[rng.integers(0, CLUSTERS, rows)]
    vectors = vectors + rng.normal(0.0, SPREAD, (rows, DIMENSION)).astype(np.float32)
    return vectors / np.linalg.norm(vectors, axis=1, keepdims=True)


def filled_table(root: Path, vectors: np.ndarray) -> Any:
    """A dataset whose embeddings table holds `vectors`, one record per row."""
    rows = len(vectors)
    dataset = Dataset.create(
        root / f"index-{rows}", DatasetInfo(id=f"index-{rows}", name="Vector index", record=Record)
    )
    space = dataset.create_record_embedding_table(dim=DIMENSION, model_id="synthetic")
    table = dataset.open_table(space["table"])
    for start in range(0, rows, FILL_BATCH):
        table.add(
            [
                {
                    "id": f"vec-{n}",
                    "record_id": f"rec-{n}",
                    "view_id": f"view-{n}",
                    "frame_id": "",
                    "vector": vectors[n].tolist(),
                    "shape": [DIMENSION],
                }
                for n in range(start, min(start + FILL_BATCH, rows))
            ]
        )
    return table


def nearest_records(table: Any, query: np.ndarray, setting: Setting) -> list[str]:
    """The records a search returns, the way `Dataset.search_records` asks for them."""
    search = table.search(query.tolist()).metric("cosine").select(["record_id"]).limit(RECORDS_PER_QUERY)
    if setting.index_type is None:
        search = search.bypass_vector_index()
    if "refine_factor" in setting.query:
        search = search.refine_factor(setting.query["refine_factor"])
    return search.to_arrow().column("record_id").to_pylist()


def measure(rows: int, root: Path) -> list[tuple[str, float, float, float]]:
    """Build every index type on a table of `rows` vectors, and search through each.

    Returns:
        Per setting: its label, the build time in seconds (0 without an index), the median
        search time in milliseconds, and the recall against the exact search.
    """
    rng = np.random.default_rng(SEED)
    vectors = synthetic_vectors(rows, rng)
    table = filled_table(root, vectors)
    queries = vectors[rng.integers(0, rows, QUERIES)] + rng.normal(0.0, SPREAD, (QUERIES, DIMENSION)).astype(
        np.float32
    )
    exact = Setting("exact", None, {})
    truth = [set(nearest_records(table, query, exact)) for query in queries]

    results = []
    built: str | None = None
    build_s = 0.0
    for setting in SETTINGS:
        if setting.index_type is not None and setting.index_type != built:
            began = time.perf_counter()
            table.create_index(
                metric="cosine", index_type=setting.index_type, vector_column_name="vector", replace=True
            )
            build_s = time.perf_counter() - began
            built = setting.index_type
        durations, found = [], 0
        for query, expected in zip(queries, truth, strict=True):
            began = time.perf_counter()
            returned = nearest_records(table, query, setting)
            durations.append((time.perf_counter() - began) * 1000)
            found += len(expected & set(returned))
        recall = found / sum(len(expected) for expected in truth)
        results.append((setting.label, build_s if setting.index_type else 0.0, statistics.median(durations), recall))
    return results


def main() -> None:
    """Measure and print a table ready to paste into the documentation."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", default="100000,300000", help="Table sizes to measure, in vectors.")
    args = parser.parse_args()

    print("| vectors | setting | index build | median search | recall |", flush=True)
    print("| ---: | --- | ---: | ---: | ---: |", flush=True)
    with tempfile.TemporaryDirectory() as scratch:
        for rows in (int(r) for r in args.rows.split(",")):
            for label, build_s, search_ms, recall in measure(rows, Path(scratch)):
                build = f"{build_s:.1f} s" if build_s else "—"
                print(f"| {rows} | {label} | {build} | {search_ms:.1f} ms | {recall:.3f} |", flush=True)


if __name__ == "__main__":
    main()
