# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""REST API endpoints for pre-annotation jobs."""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from pixano.api.settings import Settings, get_settings
from pixano.datasets import Dataset
from pixano.inference.preannotation import PreannotationConfig, PreannotationProgress, run_preannotation
from pixano.inference.preannotation_jobs import (
    DatasetBusyError,
    PreannotationJob,
    cancel_job,
    complete_job,
    create_job,
    get_job,
    list_jobs,
)
from pixano.inference.provider import InferenceProvider
from pixano.inference.types import InferenceTask


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/preannotation", tags=["Pre-annotation"])


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class StartPreannotationRequest(BaseModel):
    """Request body for starting a pre-annotation job."""

    dataset_id: str
    model: str
    provider_name: str | None = None
    task: str = "detection"
    classes: list[str] | None = None
    class_field: str | None = None
    box_threshold: float = 0.5
    text_threshold: float = 0.5
    batch_write_size: int = 50
    view_name: str | None = None


class PreannotationJobResponse(BaseModel):
    """Status response for a pre-annotation job."""

    job_id: str
    dataset_id: str
    status: str
    total: int
    processed: int
    succeeded: int
    failed: int
    errors: list[dict[str, str]]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_provider(settings: Settings, provider_name: str | None = None) -> InferenceProvider:
    if provider_name:
        provider = settings.inference_providers.get(provider_name)
        if provider is None:
            raise HTTPException(status_code=404, detail=f"Unknown inference provider '{provider_name}'")
        return provider
    if not settings.inference_providers or not settings.default_inference_provider:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    provider = settings.inference_providers.get(settings.default_inference_provider)
    if provider is None:
        raise HTTPException(status_code=404, detail="No inference provider connected")
    return provider


def _get_dataset(dataset_id: str, settings: Settings) -> Dataset:
    try:
        return Dataset.find(dataset_id, settings.library_dir)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=f"Dataset '{dataset_id}' not found.") from exc


def _job_to_response(job: PreannotationJob) -> PreannotationJobResponse:
    return PreannotationJobResponse(
        job_id=job.job_id,
        dataset_id=job.dataset_id,
        status=job.progress.status,
        total=job.progress.total,
        processed=job.progress.processed,
        succeeded=job.progress.succeeded,
        failed=job.progress.failed,
        errors=job.progress.errors,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/jobs", response_model=PreannotationJobResponse, status_code=202)
async def start_preannotation(
    request: StartPreannotationRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> PreannotationJobResponse:
    """Start a pre-annotation job on a dataset."""
    dataset = _get_dataset(request.dataset_id, settings)
    provider = _get_provider(settings, request.provider_name)

    config = PreannotationConfig(
        task=InferenceTask(request.task),
        model=request.model,
        classes=request.classes,
        class_field=request.class_field,
        box_threshold=request.box_threshold,
        text_threshold=request.text_threshold,
        batch_write_size=request.batch_write_size,
        view_name=request.view_name,
    )

    try:
        job = create_job(request.dataset_id, config)
    except DatasetBusyError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc

    async def _run_job() -> None:
        try:
            def _update_progress(progress: PreannotationProgress) -> None:
                job.progress = progress

            result = await run_preannotation(
                dataset=dataset,
                provider=provider,
                config=config,
                progress_callback=_update_progress,
                cancel_event=job.cancel_event,
            )
            job.progress = result
        except Exception:
            logger.exception("Pre-annotation job %s failed unexpectedly", job.job_id)
            job.progress.status = "failed"
        finally:
            complete_job(job.job_id)

    job.async_task = asyncio.create_task(_run_job())

    return _job_to_response(job)


@router.get("/jobs", response_model=list[PreannotationJobResponse])
async def list_preannotation_jobs(
    dataset_id: str | None = Query(default=None),
) -> list[PreannotationJobResponse]:
    """List pre-annotation jobs, optionally filtered by dataset."""
    return [_job_to_response(j) for j in list_jobs(dataset_id)]


@router.get("/jobs/{job_id}", response_model=PreannotationJobResponse)
async def get_preannotation_status(job_id: str) -> PreannotationJobResponse:
    """Poll the status of a pre-annotation job."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return _job_to_response(job)


@router.delete("/jobs/{job_id}", response_model=PreannotationJobResponse)
async def cancel_preannotation(job_id: str) -> PreannotationJobResponse:
    """Cancel a running pre-annotation job."""
    if not cancel_job(job_id):
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    job = get_job(job_id)
    assert job is not None  # cancel_job returned True
    return _job_to_response(job)
