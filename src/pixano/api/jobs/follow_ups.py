# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The processing jobs an import queues once it is done: the embeddings of the dataset it imported into.

An import runs in the application, or in the CLI that started it; processing jobs run in
pixano-worker. Whoever starts an import decides here what it asks for, and the import engine keeps
that with its job (`FollowUp`). Once the data is in, the engine calls `submit_follow_ups`, bound to
the deployment's queue and library, which fits each to the dataset as written: the embeddings asked
for become one job per model name to compute — every model the dataset already holds, whose
embeddings lack the media the import added, and the model the import named, or the deployment's
default where the dataset holds none. What cannot be queued says why on the import's job, and the
import stays done: one can still start the jobs by hand.

The embeddings are asked for by default only where they can run — a queue reachable, where a worker
declared the job, and a model to name — and on an import not known to hold no still image, so that
an installation without jobs, or an import of text or video, never reads a refusal. Asked for
explicitly, they are kept whatever the queue says, and the import says why they were not queued.
"""

import logging
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any

import psycopg

from pixano.datasets import Dataset
from pixano.datasets.io.jobs import FollowUp
from pixano.schemas import media_type_of

from .enqueue import InvalidParamsError, QueueUnavailableError, UnknownKindError, available_kinds, connect, submit


logger = logging.getLogger(__name__)

EMBEDDINGS_KIND = "embeddings"

# The media type the embeddings job computes by default, and its name in an import plan's views: a
# frame belongs to its video, not to the still images.
EMBEDDED_MEDIA = "image"
EMBEDDED_VIEW_BASE = "Image"

# How long a statement, or a lock it waits for, may hold an import on the job queue. Queueing a job
# is a handful of rows; past this, the queue is being reinstalled or is stuck, and the import says
# so rather than wait — it holds the import runner meanwhile.
QUEUE_STATEMENT_TIMEOUT_MS = 5_000

NO_WORKER = "no worker runs the embeddings job — start pixano-worker"
NO_MODEL = "no embeddings model — name one, set PIXANO_EMBEDDINGS_MODEL, or serve one from the inference"
# The import form names none: it offers what the deployment and the inference give.
NO_MODEL_SERVED = "no embeddings model — set PIXANO_EMBEDDINGS_MODEL, or serve one from the inference"
NO_IMAGE = "the dataset has no image to embed"
# As the worker words its own refusal of such a dataset, at a job's planning.
EMBEDDINGS_UNREADABLE = (
    "this dataset's description of its embeddings (embeddings.json) cannot be read entirely, so no job may "
    "change it: submit the job again if it was a passing error; if it stays so, repair the file, or compute "
    "every model's embeddings again from nothing from the explorer"
)
QUEUE_UNREADABLE = "the job queue cannot be read — the log of the process that asked says why"


def asks_for_embeddings(compute: bool | None, model: str | None) -> bool | None:
    """What an import request says of the embeddings: a named model asks for them.

    Returns:
        True or False as the request says, True when it names a model without saying, None when it
        says nothing and leaves them to the deployment's default.
    """
    if compute is None and model:
        return True
    return compute


def considers_embeddings(wanted: bool | None, *, default_on: bool, has_images: bool | None) -> bool:
    """Whether the embeddings are worth deciding on, before the queue or the inference is asked.

    Args:
        wanted: What the request says (`asks_for_embeddings`).
        default_on: The deployment's default (`PIXANO_EMBEDDINGS_AFTER_IMPORT`).
        has_images: Whether the import holds still images, from its plan; None when unknown.
    """
    if wanted is not None:
        return wanted
    return default_on and has_images is not False


def plan_has_still_images(inferred_schema: dict[str, Any] | None) -> bool | None:
    """Whether an import plan's views hold still images; None when the plan does not say."""
    views = (inferred_schema or {}).get("views")
    if not isinstance(views, dict):
        return None
    return any(isinstance(view, dict) and view.get("base") == EMBEDDED_VIEW_BASE for view in views.values())


def embeddings_unavailable(database_url: str | None) -> str | None:
    """Why no embeddings job can be queued now, or None when one can.

    One can when a job queue is configured and readable, and a worker declared the job on it. Never
    raises: a queue that fails says so, and the import goes on.
    """
    try:
        with _queue_connection(database_url) as conn:
            kinds = available_kinds(conn)
    except (QueueUnavailableError, psycopg.Error) as error:
        return _public_reason(error)
    return None if EMBEDDINGS_KIND in kinds else NO_WORKER


def decide_embeddings(
    wanted: bool | None,
    model: str | None,
    *,
    named: bool,
    default_on: bool,
    unavailable: str | None,
    no_model: str = NO_MODEL,
) -> list[FollowUp]:
    """The embeddings follow-up an import asks for, if any: one at most.

    Args:
        wanted: What the request says (`asks_for_embeddings`). None follows the deployment's default,
            which only applies where the job can run.
        model: The model the job would run, as the caller resolved it — the request's, the
            deployment's, or the first the inference serves. None when none is known.
        named: Whether the request named that model. One it did not name stands in only for a
            dataset that holds no embeddings yet (`submit_follow_ups`).
        default_on: The deployment's default (`PIXANO_EMBEDDINGS_AFTER_IMPORT`).
        unavailable: Why the job cannot run now, or None; only read for the default.
        no_model: What to say when the request asks for the job and no model is known: the CLI, which
            asks no inference, names its own options.

    Returns:
        No follow-up, or one: pending, or already saying why it will not be queued when the import
        explicitly asked for it without a model to run.
    """
    if wanted is False:
        return []
    if wanted is None and (not default_on or unavailable is not None or not model):
        return []
    if not model:
        return [FollowUp(kind=EMBEDDINGS_KIND, error=f"not queued: {no_model}")]
    return [FollowUp(kind=EMBEDDINGS_KIND, params={"model": model}, defaulted=() if named else ("model",))]


def submit_follow_ups(
    database_url: str | None, library_dir: Path, dataset_id: str, follow_ups: list[FollowUp]
) -> list[list[FollowUp]]:
    """Queue an import's pending follow-ups on the job queue; bound to a deployment, its `FollowUpStarter`.

    Each is fitted to the dataset first — the embeddings into one job per model to compute —, so
    that one with nothing to do says so whatever the queue's state. All are queued in one
    transaction: a database error rolls them all back, and each says the queue could not be read.

    Args:
        database_url: The job queue's database.
        library_dir: The library the import wrote the dataset into.
        dataset_id: The imported dataset.
        follow_ups: The pending follow-ups.

    Returns:
        What each follow-up became, in order — itself, or one per model for the embeddings —, each
        with the queued job's identifier or the reason it was not queued.

    Raises:
        FileNotFoundError: The dataset is not in the library; `queue_follow_ups` turns it into a
            reason for each.
    """
    dataset = Dataset.find(dataset_id, library_dir) if any(f.kind == EMBEDDINGS_KIND for f in follow_ups) else None
    fitted = [
        _fit_embeddings(dataset, follow_up)
        if dataset is not None and follow_up.kind == EMBEDDINGS_KIND
        else [follow_up]
        for follow_up in follow_ups
    ]
    if all(follow_up.error for became in fitted for follow_up in became):
        return fitted
    try:
        with _queue_connection(database_url) as conn:
            return [
                [follow_up if follow_up.error else _submit(conn, dataset_id, follow_up) for follow_up in became]
                for became in fitted
            ]
    except (QueueUnavailableError, psycopg.Error) as error:
        reason = _public_reason(error)
        return [
            [
                follow_up if follow_up.error else replace(follow_up, error=f"not queued: {reason}")
                for follow_up in became
            ]
            for became in fitted
        ]


def _submit(conn: psycopg.Connection, dataset_id: str, follow_up: FollowUp) -> FollowUp:
    """Queue one follow-up; a refusal of the queue's says why, a database error ends them all."""
    try:
        job = submit(conn, kind=follow_up.kind, dataset_id=dataset_id, params=follow_up.params)
    except (QueueUnavailableError, UnknownKindError, InvalidParamsError) as error:
        return replace(follow_up, error=f"not queued: {error}")
    return replace(follow_up, job_id=job.id)


def _fit_embeddings(dataset: Dataset, follow_up: FollowUp) -> list[FollowUp]:
    """The embeddings follow-up fitted to the dataset the import wrote: one per model name to compute.

    - A dataset with no still image has nothing for the job to embed.
    - A dataset whose description of its embeddings cannot be read entirely takes no job: the
      worker would refuse each.
    - Otherwise every model the dataset already holds is computed again — the media an import
      added are in none of their embeddings yet —, and so is the model the import named, first.
      A model the deployment chose instead stands in only for a dataset without embeddings: it
      adds no model to a dataset that has some.

    One job per model name: a job computes the checkpoint the inference serves under that name,
    into that checkpoint's embeddings, so a checkpoint held that is not served any more is not
    computed again, and two held are one job. A model held without a name cannot be asked for. A
    model the inference does not serve any more is refused at its job's planning, which says so.
    Each job computes every medium of the dataset again, the new ones among them: the embeddings
    job has no way to compute only what is missing.
    """
    if not any(media_type_of(schema) == EMBEDDED_MEDIA for schema in dataset.info.tables.values()):
        return [replace(follow_up, error=f"not queued: {NO_IMAGE}")]
    if not dataset.record_embeddings_fully_read():
        return [replace(follow_up, error=f"not queued: {EMBEDDINGS_UNREADABLE}")]
    held = [space["model_id"] for space in dataset.record_embedding_spaces() if space["model_id"]]
    asked = follow_up.params.get("model")
    # A model no one named is not needed where the dataset holds some.
    unneeded = "model" in follow_up.defaulted and bool(held)
    models = dict.fromkeys([*([asked] if asked and not unneeded else []), *held])
    if not models:
        return [replace(follow_up, error=f"not queued: {NO_MODEL}")]
    return [replace(follow_up, params={**follow_up.params, "model": model}) for model in models]


@contextmanager
def _queue_connection(database_url: str | None) -> Iterator[psycopg.Connection]:
    """A connection to the queue whose statements, and the locks they wait for, are bounded.

    Committed when the block ends without error, rolled back otherwise, and closed either way.
    """
    with connect(database_url) as conn:
        conn.execute(f"SET statement_timeout = {QUEUE_STATEMENT_TIMEOUT_MS}")
        conn.execute(f"SET lock_timeout = {QUEUE_STATEMENT_TIMEOUT_MS}")
        yield conn


def _public_reason(error: Exception) -> str:
    """Why the queue said no, without what a client must not read.

    The queue's own refusals — none configured, none installed yet — say what to set or start. The
    database's errors can name its host, its user, even a password in a mistyped URL: they go to the
    log, and the reason given to clients and kept on the import's job is a generic one.
    """
    if isinstance(error, QueueUnavailableError) and error.__cause__ is None:
        return str(error)
    logger.warning("the job queue could not be read for the embeddings after an import: %s", error)
    logger.debug("the job queue's failure", exc_info=error)
    return QUEUE_UNREADABLE
