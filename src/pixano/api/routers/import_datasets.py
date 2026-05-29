# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os
import re
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import shortuuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from pixano.api.settings import Settings, get_settings
from pixano.datasets.builders.folders.image import ImageFolderBuilder
from pixano.datasets.dataset_info import DatasetInfo


def _snake_case_name(value: str) -> str:
    snake = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    return re.sub(r"_+", "_", snake).strip("_")


@dataclass
class _ImportJob:
    id: str
    status: Literal["pending", "running", "done", "error"] = "pending"
    message: str = ""
    dataset_id: str = ""


_jobs: dict[str, _ImportJob] = {}
_jobs_lock = threading.Lock()

router = APIRouter(prefix="/datasets", tags=["Datasets"])

IMPORT_TYPES = {
    "unlabeled_images": ImageFolderBuilder,
}


class ImportRequest(BaseModel):
    source_dir: str
    import_type: str = "unlabeled_images"
    dataset_name: str = ""


class ImportJobResponse(BaseModel):
    job_id: str
    status: str
    message: str
    dataset_id: str


def _set_job(job_id: str, status: str, message: str = "", dataset_id: str = "") -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job:
            job.status = status  # type: ignore[assignment]
            job.message = message
            job.dataset_id = dataset_id


def _run_import(job_id: str, source_dir_str: str, dataset_name: str, library_dir: Path) -> None:
    _set_job(job_id, "running", "Preparing import…")

    source_path = Path(source_dir_str)
    if not source_path.is_dir():
        _set_job(job_id, "error", f"Directory not found: {source_dir_str}")
        return

    name = dataset_name.strip() or source_path.name
    target_name = _snake_case_name(name)
    if not target_name:
        _set_job(job_id, "error", "Could not derive a valid dataset name.")
        return

    if (library_dir / target_name).exists():
        _set_job(job_id, "error", f"Dataset '{target_name}' already exists. Choose a different name.")
        return

    try:
        with tempfile.TemporaryDirectory() as tmp:
            os.symlink(source_path.resolve(), Path(tmp) / "val")
            builder = ImageFolderBuilder(
                source_dir=tmp,
                library_dir=library_dir,
                info=DatasetInfo(name=name),
                target_name=target_name,
            )
            _set_job(job_id, "running", "Validating source folder…")
            report = builder.preflight_metadata()
            if not report.is_valid:
                _set_job(job_id, "error", f"Validation failed with {report.error_count} error(s).")
                return
            _set_job(job_id, "running", "Importing images…")
            dataset = builder.build()

        _set_job(
            job_id,
            "done",
            f"Successfully imported {dataset.num_rows} image(s).",
            dataset.info.id,
        )
    except Exception as exc:
        _set_job(job_id, "error", str(exc))


@router.post("/import", response_model=ImportJobResponse, operation_id="start_dataset_import")
def start_import(
    request: ImportRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportJobResponse:
    """Start an asynchronous dataset import job from a local folder."""
    if not isinstance(settings.library_dir, Path):
        raise HTTPException(status_code=400, detail="UI import is only supported for local storage.")
    if request.import_type not in IMPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown import type: {request.import_type!r}.")

    job_id = shortuuid.uuid()
    with _jobs_lock:
        _jobs[job_id] = _ImportJob(id=job_id)

    thread = threading.Thread(
        target=_run_import,
        args=(job_id, request.source_dir, request.dataset_name, settings.library_dir),
        daemon=True,
    )
    thread.start()

    return ImportJobResponse(job_id=job_id, status="pending", message="", dataset_id="")


@router.get("/import/{job_id}", response_model=ImportJobResponse, operation_id="get_import_job")
def get_import_job(
    job_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportJobResponse:
    """Poll the status of an import job."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Import job '{job_id}' not found.")
    return ImportJobResponse(
        job_id=job.id, status=job.status, message=job.message, dataset_id=job.dataset_id
    )
