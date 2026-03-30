# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""In-memory job manager for pre-annotation background tasks."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime

import shortuuid

from .preannotation import PreannotationConfig, PreannotationProgress


@dataclass
class PreannotationJob:
    """State of a single pre-annotation job.

    Attributes:
        job_id: Unique job identifier.
        dataset_id: Dataset being annotated.
        async_task: The running asyncio Task (None before start).
        cancel_event: Event used to signal cancellation.
        progress: Live progress information.
        created_at: Job creation timestamp.
        config: The pre-annotation configuration.
    """

    job_id: str
    dataset_id: str
    async_task: asyncio.Task | None = None  # type: ignore[type-arg]
    cancel_event: asyncio.Event = field(default_factory=asyncio.Event)
    progress: PreannotationProgress = field(default_factory=PreannotationProgress)
    created_at: datetime = field(default_factory=datetime.utcnow)
    config: PreannotationConfig | None = None


# Module-level state ---------------------------------------------------------

_JOBS: dict[str, PreannotationJob] = {}
_DATASET_LOCKS: dict[str, str] = {}  # dataset_id -> job_id


class DatasetBusyError(Exception):
    """Raised when a dataset already has a running pre-annotation job."""


def create_job(dataset_id: str, config: PreannotationConfig) -> PreannotationJob:
    """Create a new pending job.  Raises ``DatasetBusyError`` if *dataset_id* is already busy."""
    if dataset_id in _DATASET_LOCKS:
        existing = _DATASET_LOCKS[dataset_id]
        raise DatasetBusyError(
            f"Dataset '{dataset_id}' already has a running job: {existing}"
        )

    job_id = shortuuid.uuid()
    job = PreannotationJob(job_id=job_id, dataset_id=dataset_id, config=config)
    _JOBS[job_id] = job
    _DATASET_LOCKS[dataset_id] = job_id
    return job


def get_job(job_id: str) -> PreannotationJob | None:
    """Return job by ID or ``None``."""
    return _JOBS.get(job_id)


def cancel_job(job_id: str) -> bool:
    """Signal cancellation for *job_id*.  Returns ``True`` if job existed."""
    job = _JOBS.get(job_id)
    if job is None:
        return False
    job.cancel_event.set()
    return True


def complete_job(job_id: str) -> None:
    """Release the dataset lock when a job finishes (success, failure, or cancellation)."""
    job = _JOBS.get(job_id)
    if job is not None and _DATASET_LOCKS.get(job.dataset_id) == job_id:
        del _DATASET_LOCKS[job.dataset_id]


def list_jobs(dataset_id: str | None = None) -> list[PreannotationJob]:
    """Return all jobs, optionally filtered by *dataset_id*."""
    jobs = list(_JOBS.values())
    if dataset_id is not None:
        jobs = [j for j in jobs if j.dataset_id == dataset_id]
    return jobs
