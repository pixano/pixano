# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A job kind that puts the same label on a selection of records.

It exists for a precise reason: to prove that adding a job kind requires no change to the
engine. Its shape deliberately differs from the fake kind's — its parameters carry a list and
a mandatory value, its splitting follows a given selection rather than a count, and it writes
one row per task rather than one batch per chunk.

If the engine had the slightest knowledge of what a kind does, one of the two would break.
"""

from typing import Any, Iterable

from pydantic import Field

from pixano.schemas.annotations.classification import Classification

from ..reader import JobReader
from ..writer import JobWriter
from .base import Chunk, JobKind, JobParams


class LabelParams(JobParams):
    """Parameters of the labelling.

    Attributes:
        record_ids: The records to label. A selection, not a count: this is the shape the most
            common case takes, "process what I ticked".
        label: The label to put. Mandatory, to exercise the refusal of a missing parameter at
            submission.
        chunk_size: Records per chunk.
        write_to: Table to write into. Empty, the kind writes nothing.
    """

    record_ids: list[str] = Field(default_factory=list)
    label: str = Field(min_length=1)
    chunk_size: int = Field(default=32, ge=1, le=10_000)
    write_to: str | None = None


class LabelKind(JobKind[LabelParams]):
    """Puts a label on every record of a selection."""

    name = "label"
    params_model = LabelParams
    #: The selection would copy every labelled identifier into every row it produced.
    params_not_in_provenance = JobKind.params_not_in_provenance | {"record_ids"}
    # A label put by a rule is not a model prediction.
    source_type = "other"

    def plan(self, reader: JobReader, params: LabelParams) -> Iterable[Chunk]:
        """Split the selection into chunks. Nothing to read: the selection is given."""
        ids = params.record_ids
        for start in range(0, len(ids), params.chunk_size):
            batch = ids[start : start + params.chunk_size]
            yield Chunk(payload={"record_ids": batch}, task_count=len(batch))

    def process(self, reader: JobReader, payload: dict[str, Any], params: LabelParams) -> dict[str, Any]:
        """There is nothing to compute: the label is in the parameters."""
        return {"label": params.label, "record_ids": payload["record_ids"]}

    def write(self, writer: JobWriter, result: dict[str, Any], payload: dict[str, Any], params: LabelParams) -> None:
        """Write one classification per record.

        One key per record, unlike the fake kind which uses one per chunk: relabelling a single
        record must not depend on the splitting that processed it the first time.
        """
        if not params.write_to:
            return
        for record_id in result["record_ids"]:
            row = Classification(
                id="",
                record_id=record_id,
                labels=[result["label"]],
                confidences=[1.0],
                **writer.provenance(),
            )
            writer.replace(params.write_to, key=record_id, rows=[row])
