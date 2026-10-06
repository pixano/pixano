# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

r"""Measure the throughput of the embeddings job, by chunk size and by storage mode.

The question this script answers is not "how many images per second" — that depends on the
model and the machine — but two comparisons which, for their part, do carry over:

1. **What transporting the bytes costs.** The plan states that media must not go through
   Pixano. On two datasets carrying the same images, one referenced by path and the other
   embedded, the gap puts a number on this invariant instead of asserting it.
2. **The chunk size that is worth it.** A chunk amortises a network round trip and a model
   pass; too big, it lengthens what a resume has to redo.

A task is a **planned** record, not a produced vector: the job kind discards the records with
no usable image. The two numbers only coincide on a dataset where every record carries an
image — measured on nuScenes, 26,766 tasks give only 404 vectors, the rest being lidar
readings without a camera. Hence the choice of the datasets to measure, explicit and
mandatory: a throughput only makes sense on a fully imaged dataset.

Usage:
    uv run --directory packages/pixano-worker python scripts/measure_throughput.py \\
        --api http://localhost:7492 --sizes 8,16,32,64 \\
        --datasets "VOC 2007 Sample,VOC 2007 (uri)"
"""

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


def _call(url: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"} if data else {})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read())


#: What the embeddings kind logs for each written chunk, with the job's identifier.
PHASES = re.compile(
    r"job (?P<job>[0-9a-f-]{36}): phases read (?P<read>[\d.]+) s, inference (?P<inference>[\d.]+) s, "
    r"write (?P<write>[\d.]+) s"
)


def phases_of(worker_log: Path, job_id: str) -> dict[str, float]:
    """Add up, over the worker's log, the time spent per phase for a job.

    The phases are summed over the chunks: with several chunks in flight, their sum exceeds
    the job's duration. These are working times, not waiting times — this is what says where
    the time goes when a bigger chunk turns out to be slower.
    """
    totals = {"read": 0.0, "inference": 0.0, "write": 0.0}
    for line in worker_log.read_text(errors="replace").splitlines():
        found = PHASES.search(line)
        if found and found["job"] == job_id:
            for phase in totals:
                totals[phase] += float(found[phase])
    return totals


def run_job(api: str, dataset_id: str, chunk_size: int, poll_s: float = 0.2) -> tuple[float, int, str]:
    """Launch an embeddings job and wait for it to finish.

    The wait is short compared with a job's duration, so that the polling step does not get
    mixed up with what is being measured.

    Returns:
        The duration in seconds, the number of planned tasks, and the job's identifier.
    """
    job = _call(
        f"{api}/jobs",
        {
            "kind": "embeddings",
            "dataset_id": dataset_id,
            "params": {"model": "clip", "chunk_size": chunk_size},
        },
    )
    started = time.monotonic()
    while True:
        time.sleep(poll_s)
        state = _call(f"{api}/jobs/{job['id']}")
        if state["state"] in ("done", "error", "cancelled"):
            if state["state"] != "done":
                raise RuntimeError(f"job {state['state']}: {state}")
            return time.monotonic() - started, state["total_tasks"], job["id"]


def datasets(api: str) -> dict[str, str]:
    """The available datasets, by name."""
    return {d["name"]: d["id"] for d in _call(f"{api}/datasets")}


def main() -> None:
    """Measure and return a table ready to paste into the documentation."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api", default="http://localhost:7492")
    parser.add_argument("--sizes", default="8,16,32,64")
    parser.add_argument(
        "--datasets",
        required=True,
        help="Names of the datasets to measure, comma-separated. Mandatory: measuring "
        "everything lying around in the library launches a long computation on datasets whose "
        "throughput means nothing.",
    )
    parser.add_argument(
        "--worker-log",
        type=Path,
        help="The worker's log (for example the output of `docker compose logs -f pixano-worker`, or that "
        "of a worker launched by hand), to break the duration down by phase: read, inference, write.",
    )
    args = parser.parse_args()

    available = datasets(args.api)
    wanted = [n.strip() for n in args.datasets.split(",") if n.strip()]
    unknown = [name for name in wanted if name not in available]
    if unknown:
        raise SystemExit(f"unknown dataset: {', '.join(unknown)}. Known: {', '.join(available)}")
    sizes = [int(s) for s in args.sizes.split(",")]

    phases = " read | inference | write |" if args.worker_log else ""
    print(f"| dataset | chunk | planned tasks | duration | tasks/s |{phases}", flush=True)
    print("| --- | ---: | ---: | ---: | ---: |" + (" ---: | ---: | ---: |" if args.worker_log else ""), flush=True)
    for name in wanted:
        for size in sizes:
            elapsed, tasks, job_id = run_job(args.api, available[name], size)
            rate = tasks / elapsed if elapsed else 0.0
            row = f"| {name} | {size} | {tasks} | {elapsed:.1f} s | {rate:.1f} |"
            if args.worker_log:
                # The worker writes its log after the fact; give it time to flush it.
                time.sleep(1.0)
                totals = phases_of(args.worker_log, job_id)
                row += f" {totals['read']:.1f} s | {totals['inference']:.1f} s | {totals['write']:.1f} s |"
            print(row, flush=True)


if __name__ == "__main__":
    main()
