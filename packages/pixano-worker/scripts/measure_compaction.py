# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Measure what compacting an annotation table costs, under the write lock.

Compaction runs every `COMPACT_EVERY_WRITES` writes, in the chunk that triggers it, under the
dataset's write lock: the other chunks of the same dataset wait for it to finish. Short on a
vector table (63 fragments merged in a fraction of a second), it had not been measured on an
annotation table — the one the step 2 kinds will fill, and that users annotate at the same time.

The script fills a classification table by writes of a chunk's size, as a job would, and times
each `optimize`: this is the time during which the dataset accepts no other write.

Usage:
    uv run --directory packages/pixano-worker python scripts/measure_compaction.py --rows 10000,30000
"""

import argparse
import statistics
import tempfile
import time
from pathlib import Path

from pixano_worker.writer import COMPACT_EVERY_WRITES, KEEP_OLD_VERSIONS_FOR

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas.annotations.classification import Classification
from pixano.schemas.records import Record


# The size of an annotation chunk: one row per record, eight records per chunk like the
# embeddings kind's default.
ROWS_PER_WRITE = 8


def measure(rows: int, root: Path) -> tuple[int, list[float]]:
    """Fill a table by chunk writes, compact at the writer's pace, time it.

    Returns:
        The number of compactions, and the duration of each in seconds.
    """
    dataset = Dataset.create(
        root / f"compaction-{rows}",
        DatasetInfo(id=f"compaction-{rows}", name="Compaction", record=Record, classification=Classification),
    )
    dataset.add_data("records", [Record(id=f"rec-{n}") for n in range(rows)])

    durations: list[float] = []
    writes = 0
    for start in range(0, rows, ROWS_PER_WRITE):
        batch = [
            Classification(id=f"cls-{n}", record_id=f"rec-{n}", labels=["a"], confidences=[1.0])
            for n in range(start, min(start + ROWS_PER_WRITE, rows))
        ]
        dataset.update_data("classifications", batch)
        writes += 1
        if writes % COMPACT_EVERY_WRITES == 0:
            began = time.perf_counter()
            dataset.open_table("classifications").optimize(cleanup_older_than=KEEP_OLD_VERSIONS_FOR)
            durations.append(time.perf_counter() - began)
    return writes, durations


def main() -> None:
    """Measure and return a table ready to paste into the documentation."""
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rows", default="10000,30000", help="Table sizes to measure, in rows.")
    args = parser.parse_args()

    print("| rows | writes | compactions | median | max | last |", flush=True)
    print("| ---: | ---: | ---: | ---: | ---: | ---: |", flush=True)
    with tempfile.TemporaryDirectory() as scratch:
        for rows in (int(r) for r in args.rows.split(",")):
            writes, durations = measure(rows, Path(scratch))
            print(
                f"| {rows} | {writes} | {len(durations)} | {statistics.median(durations):.3f} s "
                f"| {max(durations):.3f} s | {durations[-1]:.3f} s |",
                flush=True,
            )


if __name__ == "__main__":
    main()
