# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The three contracts that make up a job kind.

A job kind is a plugin: it brings its parameters, knows how to split its work, knows how to
process a batch and knows how to write what it produced. The engine — claiming, lease,
resumption, progress, cancellation — knows nothing about its content.

The three contracts:

- **`Params`**, a pydantic model. Its JSON schema is published in the database so that the
  application refuses invalid parameters at submission, rather than queueing a job that would
  fail at execution.
- **`plan`**, which splits the work into chunks. It runs in the worker, not in the
  application: splitting by video or by image is the kind's own logic, and the kind's code
  runs on one side only.
- **`process`** then **`write`**, which process a chunk and write its result. Separated
  because they fail differently — an inference call is transient and gets replayed, a write
  must never be partial.

Failures fall into three families, and the engine handles each differently:

- **transient** — the service is saturated, restarting, not answering. The kind raises
  `TransientError`; the engine hands the chunk back to the queue after a growing delay, and
  only gives up on it after several attempts.
- **per item** — one specific item is unreadable, the others are fine. The kind raises
  nothing: it finishes the chunk and declares the item in its outcome (`outcome`), which puts
  it in quarantine.
- **fatal** — any other exception. The chunk has failed, and the job with it.

`write` must be **idempotent**. Results go to LanceDB while progress goes to PostgreSQL: the
two writes cannot share a transaction, so a worker that dies between the two will redo the
chunk. An identifier derived from the job and the chunk's rank is enough to make the replay
harmless.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, Iterable, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from ..reader import JobReader
from ..writer import JobWriter, ModelIdentity


class JobParams(BaseModel):
    """Base of a job kind's parameters.

    `extra="forbid"` is not a detail of rigour: it is what makes pydantic emit
    `additionalProperties: false` in the published JSON schema, hence what lets the
    application refuse a misspelled parameter name. Without it, a typo passes validation and
    the parameter is silently ignored at execution.
    """

    model_config = ConfigDict(extra="forbid")


ParamsT = TypeVar("ParamsT", bound=JobParams)


class Chunk(BaseModel):
    """A batch of tasks as a planner produces it.

    Attributes:
        payload: What the kind will have to process. Opaque to the engine.
        task_count: Number of tasks, for progress.
    """

    payload: dict[str, Any]
    task_count: int


class TransientError(Exception):
    """A failure of circumstance: the same chunk, replayed later, has every chance of passing.

    To raise when the kind has exhausted its own short retries — a call that fails one second
    and passes the next has no business going around the queue.
    """


class QuarantinedItem(BaseModel):
    """An item a job kind could not process.

    Attributes:
        item_id: The item's identifier in the dataset.
        reason: What happened, readable by the person who will open the quarantine. **In
            English**: the interface displays it as is, and it is in English.
        detail: Enough to diagnose, in any shape.
    """

    item_id: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    detail: dict[str, Any] | None = None


class Outcome(BaseModel):
    """The outcome of a chunk: what became of its tasks.

    Every task is in exactly one of the three categories, and the engine checks it: an outcome
    that does not add up is a defect of the kind, not a display detail.

    Attributes:
        produced: Tasks that yielded a result.
        skipped: Tasks with nothing to do — a record without an image, for a computation on
            images. This is not a failure, and nothing goes to quarantine.
        quarantined: Failed tasks, one per item.
    """

    produced: int = Field(ge=0)
    skipped: int = Field(default=0, ge=0)
    quarantined: list[QuarantinedItem] = Field(default_factory=list)

    @property
    def total(self) -> int:
        """The number of tasks this outcome covers."""
        return self.produced + self.skipped + len(self.quarantined)


class JobKind(ABC, Generic[ParamsT]):
    """A kind of processing that can run on a dataset."""

    name: str
    params_model: type[ParamsT]

    #: Parameters left out of the provenance written with each row: those that say how the
    #: engine runs the job rather than what it computes — the chunk size every kind has, a
    #: request timeout — and a selection of items, which would copy thousands of identifiers
    #: into every row it produced. A kind extends the set with its own.
    params_not_in_provenance: frozenset[str] = frozenset({"chunk_size"})

    #: What this kind produces, in the provenance vocabulary of the Pixano schemas. Most kinds
    #: run a model; a kind that does not run one must say so, so that its output is not taken
    #: for a prediction.
    source_type: str = "model"

    def model_identity(self, params: ParamsT) -> ModelIdentity | None:
        """The model this job runs, for the provenance of every row it writes.

        None by default — a kind that runs no model. A kind that does returns at least the
        model's name; the version is whatever the inference exposes beyond the name. Called
        once per chunk, in the job's thread, so asking the server is allowed; but a provenance
        that cannot be completed must not fail the chunk — return the name alone.
        """
        return None

    def provenance_params(self, params: ParamsT) -> dict[str, Any]:
        """The parameters the provenance records: all of them but the engine's.

        Dumped in JSON mode: a parameter typed as a path, an enum or a date must not make the
        provenance fail to serialise at write time, which would fail the chunk.
        """
        dumped = params.model_dump(mode="json")
        return {key: value for key, value in dumped.items() if key not in self.params_not_in_provenance}

    def prepare(self, writer: "JobWriter", params: ParamsT) -> None:
        """Put the dataset in shape before the job is split.

        Called once per job, under the planning lease, before `plan` — never by the replay of
        a chunk nor by the relaunch of a job that already has its chunks. Doing nothing is the
        default, and it is what most kinds do: a kind only overrides this for a reset that its
        chunks cannot each do on their own — emptying a table before filling it, for example.

        Three rules, the first two checked by the contract suite:

        - **Idempotent.** Called twice, the dataset is in the same state as after once: a
          planner that died after `prepare` lets its lease expire, and the next one starts over.
        - **Destroys nothing unless an explicit parameter asks for it.** A job launched with
          the default parameters must never lose what the dataset holds.
        - **No `finalize` counterpart**, as long as no kind needs one: what must happen at the
          end of a job gets designed then, not by symmetry.

        Args:
            writer: Where to write through, already bound to the dataset and the job.
            params: The validated parameters.
        """

    @abstractmethod
    def plan(self, reader: "JobReader", params: ParamsT) -> Iterable[Chunk]:
        """Split the job's work into chunks.

        The reader is the counterpart of the writer that `write` receives: a kind enumerates
        what it is going to process without opening a dataset itself. A kind that has nothing
        to read — its work is contained in its parameters — can simply ignore it.

        Args:
            reader: Where to read the target dataset from.
            params: The validated parameters.

        Returns:
            The chunks, in the intended execution order.
        """

    @abstractmethod
    def process(self, reader: "JobReader", payload: dict[str, Any], params: ParamsT) -> Any:
        """Process a chunk and return its result, without writing anything.

        This is where the inference calls live. A brief transient failure is replayed right
        here; a lasting failure is signalled with `TransientError`, and the engine will replay
        the chunk later. An unreadable item must not fail the chunk: it is declared in the
        outcome that `outcome` returns.

        The reader is the one from `plan`. One is needed here too: a chunk carries what
        designates the work, never the data itself — putting encoded images in a payload would
        swell the chunk table by the whole weight of the dataset.
        """

    @abstractmethod
    def write(self, writer: "JobWriter", result: Any, payload: dict[str, Any], params: ParamsT) -> None:
        """Write the result, idempotently.

        The kind does not know how to open a dataset: it receives a writer, which is the
        system's single point of writing. This is what will make it possible, later, to
        serialise a dataset's writes across several workers without touching a single job kind.

        Args:
            writer: Where to write through, already bound to the dataset and the job.
            result: What `process` returned.
            payload: The processed chunk.
            params: The validated parameters.
        """

    def outcome(self, result: Any, payload: dict[str, Any], task_count: int) -> Outcome:
        """Say what became of the chunk's tasks.

        By default, all of them yielded a result. A kind that skips or quarantines items
        overrides this: it is what lets a job say what it produced, and not only what it
        attempted.

        Args:
            result: What `process` returned.
            payload: The processed chunk.
            task_count: The number of tasks in the chunk, which the outcome must cover exactly.
        """
        return Outcome(produced=task_count)

    def params_schema(self) -> dict[str, Any]:
        """The JSON schema of the parameters, published for the application."""
        return self.params_model.model_json_schema()

    def validate_params(self, raw: dict[str, Any]) -> ParamsT:
        """Re-read the parameters stored in the database."""
        return self.params_model.model_validate(raw)
