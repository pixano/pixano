# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A job kind that does nothing, slowly.

It exists to exercise the engine without depending on a model: claiming, lease, resumption,
cancellation and progress can all be demonstrated with it. It is also the first implementation
of the three contracts, hence the one that puts them to the test before the frozen-contracts
lot pins them down.
"""

import time
from typing import Any, Iterable

from pydantic import Field

from pixano.schemas.annotations.classification import Classification

from ..reader import JobReader
from ..writer import JobWriter
from .base import Chunk, JobKind, JobParams, Outcome, QuarantinedItem, TransientError


class FakeParams(JobParams):
    """Parameters of the fake job.

    Attributes:
        task_count: Number of tasks to simulate.
        chunk_size: Tasks per chunk.
        seconds_per_task: Time spent per task, to observe a realistic progression.
        fail_at_chunk: Rank of a chunk that must fail, to exercise error reporting.
        transient_at_chunk: Rank of a chunk that hits a transient outage on every attempt, to
            exercise the retry delay and the give-up after exhaustion.
        skip_per_chunk: Tasks declared as having nothing to do in each chunk.
        quarantine_per_chunk: Tasks declared as failed in each chunk, to exercise the
            quarantine.
        write_to: Toy table to write meaningless rows into, to exercise the idempotence of
            writes. Empty, the kind writes nothing.
    """

    task_count: int = Field(default=200, ge=1, le=1_000_000)
    chunk_size: int = Field(default=20, ge=1, le=10_000)
    seconds_per_task: float = Field(default=0.01, ge=0.0, le=60.0)
    fail_at_chunk: int | None = Field(default=None, ge=0)
    transient_at_chunk: int | None = Field(default=None, ge=0)
    skip_per_chunk: int = Field(default=0, ge=0)
    quarantine_per_chunk: int = Field(default=0, ge=0)
    write_to: str | None = Field(
        default=None,
        description="Toy table to write meaningless rows into. Leave empty to write nothing.",
    )


class FakeKind(JobKind[FakeParams]):
    """The fake job kind."""

    name = "fake"
    params_model = FakeParams
    # No model runs here: what this kind writes is not a prediction.
    source_type = "other"

    def plan(self, reader: JobReader, params: FakeParams) -> Iterable[Chunk]:
        """Split into fixed-size chunks. Nothing to read: the count is in the parameters."""
        remaining = params.task_count
        first = 0
        while remaining > 0:
            size = min(params.chunk_size, remaining)
            yield Chunk(payload={"first_task": first, "task_count": size}, task_count=size)
            first += size
            remaining -= size

    def process(self, reader: JobReader, payload: dict[str, Any], params: FakeParams) -> dict[str, Any]:
        """Sleep for the announced time, then return a token result.

        Raises:
            RuntimeError: This chunk's rank is the one that was asked to fail.
            TransientError: This chunk's rank is the one that was asked to hit a transient
                outage.
        """
        rank = payload.get("first_task", 0) // params.chunk_size
        if params.fail_at_chunk == rank:
            raise RuntimeError(f"failure requested at chunk {params.fail_at_chunk}")
        if params.transient_at_chunk == rank:
            raise TransientError(f"transient outage requested at chunk {rank}")
        time.sleep(params.seconds_per_task * payload["task_count"])
        skipped = min(params.skip_per_chunk, payload["task_count"])
        quarantined = min(params.quarantine_per_chunk, payload["task_count"] - skipped)
        return {"processed": payload["task_count"], "skipped": skipped, "quarantined": quarantined}

    def outcome(self, result: dict[str, Any], payload: dict[str, Any], task_count: int) -> Outcome:
        """Skip then quarantine the first tasks of the chunk, as `process` decided."""
        skipped, quarantined = result["skipped"], result["quarantined"]
        first = payload["first_task"]
        return Outcome(
            produced=task_count - skipped - quarantined,
            skipped=skipped,
            quarantined=[
                QuarantinedItem(item_id=f"task-{first + skipped + offset}", reason="failure requested")
                for offset in range(quarantined)
            ],
        )

    def write(self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: FakeParams) -> None:
        """Write a meaningless classification into a toy table.

        The table's name says what it is. This kind exists to exercise the engine, and what it
        produces means nothing: nothing must be able to pass for a real annotation, nor linger
        in a dataset without anyone knowing where it came from.
        """
        if not params.write_to:
            return
        first = payload["first_task"]
        rows = [
            Classification(
                id="",
                record_id=f"task-{first + offset}",
                labels=["fake"],
                confidences=[1.0],
                **writer.provenance(),
            )
            for offset in range(payload["task_count"])
        ]
        writer.replace(params.write_to, key=f"chunk-{first}", rows=rows)
