# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""REST endpoints for the processing job queue."""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from pixano.api import jobs
from pixano.api.routers._deps import get_dataset_dep
from pixano.api.settings import Settings, get_settings


router = APIRouter(prefix="/jobs", tags=["Jobs"])

MAX_LISTED_JOBS = 200


class SubmitJobRequest(BaseModel):
    """What the interface sends to start a job.

    Attributes:
        kind: Which processing to run. Checked against what a worker has declared it can do.
        dataset_id: The dataset to run it on.
        params: Parameters of the kind, checked against the schema the kind published. How
            the work gets split lives in here, since splitting is the kind's business.
    """

    kind: str = Field(min_length=1)
    dataset_id: str = Field(min_length=1)
    params: dict[str, Any] = Field(default_factory=dict)


class JobKindResponse(BaseModel):
    """A kind a worker has declared, and the shape of its parameters."""

    name: str
    params_schema: dict[str, Any]


class JobResponse(BaseModel):
    """A job as the interface sees it."""

    id: str
    kind: str
    dataset: str
    state: str
    total_tasks: int
    done_tasks: int
    created_at: str

    @classmethod
    def of(cls, record: jobs.JobRecord) -> "JobResponse":
        """Render a job record for the wire."""
        return cls(
            id=record.id,
            kind=record.kind,
            dataset=record.dataset,
            state=record.state,
            total_tasks=record.total_tasks,
            done_tasks=record.done_tasks,
            created_at=record.created_at.isoformat(),
        )


def _connect(settings: Settings):
    """Open a connection to the queue, or answer 503.

    The queue is absent whenever pixano-worker has never started — it owns the schema. That
    is a deployment state, not a client error and not a bug, so it deserves a 503 naming the
    missing component rather than a 500.
    """
    try:
        return jobs.connect(settings.database_url)
    except jobs.QueueUnavailableError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error


@router.get("/kinds", operation_id="list_job_kinds")
def list_job_kinds(settings: Annotated[Settings, Depends(get_settings)]) -> list[JobKindResponse]:
    """List what the running workers declare they can execute.

    Empty means no worker has started, or none carries any kind — in both cases nothing can
    be submitted, and the interface should say so rather than offer a choice that will fail.
    """
    with _connect(settings) as conn:
        try:
            kinds = jobs.available_kinds(conn)
        except jobs.QueueUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    return [JobKindResponse(name=name, params_schema=schema) for name, schema in kinds.items()]


@router.post("", status_code=202, operation_id="submit_job")
def submit_job(
    request: SubmitJobRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> JobResponse:
    """Record a job request. The worker splits it and runs it.

    The dataset is resolved here so that a wrong identifier is a 404 now rather than a job
    that fails once queued.
    """
    get_dataset_dep(request.dataset_id, settings)

    with _connect(settings) as conn:
        try:
            record = jobs.submit(conn, kind=request.kind, dataset_id=request.dataset_id, params=request.params)
        except jobs.UnknownKindError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except jobs.InvalidParamsError as error:
            raise HTTPException(status_code=422, detail=str(error)) from error
        except jobs.QueueUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    return JobResponse.of(record)


@router.get("", operation_id="list_jobs")
def list_jobs(
    settings: Annotated[Settings, Depends(get_settings)],
    limit: Annotated[int, Query(ge=1, le=MAX_LISTED_JOBS)] = 50,
) -> list[JobResponse]:
    """List jobs, most recent first."""
    with _connect(settings) as conn:
        try:
            records = jobs.list_jobs(conn, limit)
        except jobs.QueueUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    return [JobResponse.of(record) for record in records]


@router.get("/{job_id}", operation_id="get_job")
def get_job(job_id: str, settings: Annotated[Settings, Depends(get_settings)]) -> JobResponse:
    """Read one job."""
    with _connect(settings) as conn:
        try:
            record = jobs.get(conn, job_id)
        except jobs.JobNotFoundError as error:
            raise HTTPException(status_code=404, detail=f"job inconnu : {job_id}") from error
        except jobs.QueueUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    return JobResponse.of(record)


@router.post("/{job_id}/cancel", operation_id="cancel_job")
def cancel_job(job_id: str, settings: Annotated[Settings, Depends(get_settings)]) -> JobResponse:
    """Ask for a job to stop.

    Pending chunks leave the queue at once; running ones are left to their worker, which
    gives them back between two batches.
    """
    with _connect(settings) as conn:
        try:
            record = jobs.cancel(conn, job_id)
        except jobs.JobNotFoundError as error:
            raise HTTPException(status_code=404, detail=f"job inconnu : {job_id}") from error
        except jobs.QueueUnavailableError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
    return JobResponse.of(record)
