# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Deprecated GUI import endpoints, now running on the shared io core (spec §12).

The endpoint shapes and the SequenceFrame output contract for videos are
preserved so the shipped import modal keeps working unchanged; the durable
job store and the import wizard replace this router in a later slice, and
the alias is removed in 0.9.
"""

import json
import logging
import os
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Literal

import shortuuid
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from pixano.api.settings import Settings, get_settings
from pixano.datasets.io import ImportSpec, PixanoDataError, import_dataset
from pixano.datasets.io.media import VIDEO_EXTENSIONS
from pixano.datasets.workspaces import WorkspaceType
from pixano.utils import to_snake_case


logger = logging.getLogger(__name__)


@dataclass
class _ImportJob:
    id: str
    status: Literal["pending", "running", "done", "error"] = "pending"
    message: str = ""
    dataset_id: str = ""


_jobs: dict[str, _ImportJob] = {}
_jobs_lock = threading.Lock()

router = APIRouter(prefix="/datasets", tags=["Datasets"])

IMPORT_TYPES = ("unlabeled_images", "unlabeled_videos")


class ImportRequest(BaseModel):
    """Request body for starting a dataset import job."""

    source_dir: str
    import_type: str = "unlabeled_images"
    dataset_name: str = ""


class ImportJobResponse(BaseModel):
    """Response body for import job status queries."""

    job_id: str
    status: str
    message: str
    dataset_id: str


def _set_job(job_id: str, status: str, message: str = "", dataset_id: str = "") -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job:
            logger.info("import job %s: %s %s %s", job_id, status, message, dataset_id)
            job.status = status  # type: ignore[assignment]
            job.message = message
            job.dataset_id = dataset_id


def _spec(name: str, workspace: WorkspaceType) -> ImportSpec:
    return ImportSpec.model_validate(
        {"dataset": {"name": name, "workspace": workspace.value}, "format": "pixano_jsonl"}
    )


def _run_import(job_id: str, source_dir_str: str, import_type: str, dataset_name: str, data_dir: Path) -> None:
    _set_job(job_id, "running", "Preparing import…")

    source_path = Path(source_dir_str)
    if not source_path.is_dir():
        _set_job(job_id, "error", f"Directory not found: {source_dir_str}")
        return

    name = dataset_name.strip() or source_path.name
    if not to_snake_case(name):
        _set_job(job_id, "error", "Could not derive a valid dataset name.")
        return

    try:
        if import_type == "unlabeled_videos":
            _run_video_import(job_id, source_path, name, data_dir)
        else:
            _run_image_import(job_id, source_path, name, data_dir)
    except PixanoDataError as error:
        _set_job(job_id, "error", str(error))
    except Exception as error:  # pragma: no cover - defensive
        _set_job(job_id, "error", str(error))


def _run_image_import(job_id: str, source_path: Path, name: str, data_dir: Path) -> None:
    with tempfile.TemporaryDirectory() as tmp:
        # The GUI passes a flat folder; the importer's media-only mode expects split dirs.
        os.symlink(source_path.resolve(), Path(tmp) / "val")
        _set_job(job_id, "running", "Importing images…")
        result = import_dataset(tmp, data_dir, _spec(name, WorkspaceType.IMAGE))
    records = result.table_counts.get("records", 0)
    _set_job(job_id, "done", f"Successfully imported {records} image(s).", result.dataset_id)


def _run_video_import(job_id: str, source_path: Path, name: str, data_dir: Path) -> None:
    # The shipped UI browses videos as frame sequences; keep that contract by
    # extracting frames in-shim until the video-browse UI lands (spec §12).
    try:
        import cv2
    except ImportError:
        _set_job(
            job_id,
            "error",
            "opencv-python (cv2) is required for video import. Install it with: pip install opencv-python",
        )
        return

    video_files = sorted(f for f in source_path.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS)
    if not video_files:
        _set_job(job_id, "error", f"No video files found in {source_path} (supported: {', '.join(VIDEO_EXTENSIONS)}).")
        return

    with tempfile.TemporaryDirectory() as tmp:
        split_dir = Path(tmp) / "val"
        frames_root = split_dir / "frames"
        frames_root.mkdir(parents=True)

        metadata_lines: list[str] = []
        for index, video_path in enumerate(video_files):
            _set_job(job_id, "running", f"Extracting frames from {video_path.name} ({index + 1}/{len(video_files)})…")
            frame_dir = frames_root / video_path.stem
            frame_dir.mkdir()

            capture = cv2.VideoCapture(str(video_path))
            fps = capture.get(cv2.CAP_PROP_FPS) or 24.0
            frame_index = 0
            while True:
                returned, frame = capture.read()
                if not returned:
                    break
                cv2.imwrite(str(frame_dir / f"{frame_index:05d}.jpg"), frame)
                frame_index += 1
            capture.release()

            if frame_index == 0:
                _set_job(job_id, "error", f"Could not extract any frames from {video_path.name}.")
                return

            metadata_lines.append(
                json.dumps(
                    {"views": {"image": {"frame_pattern": f"frames/{video_path.stem}/*.jpg", "fps": round(fps)}}}
                )
            )

        (split_dir / "metadata.jsonl").write_text("\n".join(metadata_lines) + "\n")
        _set_job(job_id, "running", "Importing video frames…")
        result = import_dataset(tmp, data_dir, _spec(name, WorkspaceType.VIDEO))

    _set_job(job_id, "done", f"Successfully imported {len(video_files)} video(s).", result.dataset_id)


@router.post("/import", response_model=ImportJobResponse, operation_id="start_dataset_import", deprecated=True)
def start_import(
    request: ImportRequest,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportJobResponse:
    """Start an asynchronous dataset import job from a local folder (deprecated alias)."""
    if not isinstance(settings.library_dir, Path):
        raise HTTPException(status_code=400, detail="UI import is only supported for local storage.")
    if request.import_type not in IMPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown import type: {request.import_type!r}.")

    if settings.library_dir.name != "library":
        raise HTTPException(status_code=400, detail="UI import requires the standard <data_dir>/library layout.")
    data_dir = settings.library_dir.parent

    job_id = shortuuid.uuid()
    with _jobs_lock:
        _jobs[job_id] = _ImportJob(id=job_id)

    thread = threading.Thread(
        target=_run_import,
        args=(job_id, request.source_dir, request.import_type, request.dataset_name, data_dir),
        daemon=True,
    )
    thread.start()

    return ImportJobResponse(job_id=job_id, status="pending", message="", dataset_id="")


@router.get("/import/{job_id}", response_model=ImportJobResponse, operation_id="get_import_job", deprecated=True)
def get_import_job(
    job_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> ImportJobResponse:
    """Poll the status of an import job (deprecated alias)."""
    with _jobs_lock:
        job = _jobs.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Import job '{job_id}' not found.")
    return ImportJobResponse(job_id=job.id, status=job.status, message=job.message, dataset_id=job.dataset_id)
