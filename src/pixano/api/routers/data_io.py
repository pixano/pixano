# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The /io/* data import/export API plus the deprecated GUI import alias (spec §9).

Every route is a thin shell over the shared io core: analyze returns the same
`ImportPlan` JSON the CLI renders, imports run as durable jobs in the shared
SQLite store (the CLI sees them too), and the legacy `POST /datasets/import` +
`GET /datasets/import/{job_id}` pair keeps the shipped modal working until the
wizard cutover (removed in 0.9). The REST surface never executes user Python —
the `--importer`/`--info-py` escape hatches are CLI-only (spec Goal 2).
"""

import json
import logging
import os
import tempfile
import threading
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from pixano.api.settings import Settings, get_settings
from pixano.datasets.io import FORMATS, ImportSpec, PixanoDataError, analyze
from pixano.datasets.io.errors import JobStateError, SpecValidationError
from pixano.datasets.io.jobs import JobRecord, JobRunner, JobStore
from pixano.datasets.io.media import VIDEO_EXTENSIONS
from pixano.utils import to_snake_case


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/io", tags=["Data IO"])
legacy_router = APIRouter(prefix="/datasets", tags=["Datasets"])

_runners: dict[str, tuple[JobStore, JobRunner]] = {}
_runners_lock = threading.Lock()


def _data_dir(settings: Settings) -> Path:
    if not isinstance(settings.library_dir, Path):
        raise HTTPException(status_code=400, detail="Data IO requires local storage (S3 libraries are read-only).")
    if settings.library_dir.name != "library":
        raise HTTPException(status_code=400, detail="Data IO requires the standard <data_dir>/library layout.")
    return settings.library_dir.parent


def _spec_payload_for_source(source: str, overrides: dict[str, Any]) -> dict[str, Any]:
    """Merge the source's dataset.yaml (if any) under the request's spec overrides."""
    manifest = Path(source) / "dataset.yaml"
    payload: dict[str, Any] = {}
    if manifest.is_file():
        import yaml

        loaded = yaml.safe_load(manifest.read_text(encoding="utf-8")) or {}
        if isinstance(loaded, dict):
            payload = loaded
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(payload.get(key), dict):
            payload[key] = {**payload[key], **value}
        else:
            payload[key] = value
    payload.pop("pixano", None)
    return payload


def _runner(settings: Settings) -> tuple[JobStore, JobRunner]:
    data_dir = _data_dir(settings)
    key = str(data_dir)
    with _runners_lock:
        if key not in _runners:
            store = JobStore.for_data_dir(data_dir)
            _runners[key] = (store, JobRunner(store, data_dir))
        return _runners[key]


# ----------------------------------------------------------------------
# Transport models
# ----------------------------------------------------------------------


class AnalyzeRequest(BaseModel):
    """Analyze a source against a declarative spec (no side effects)."""

    source: str
    spec: dict[str, Any] = Field(default_factory=dict)
    save_plan: bool = True


class ImportRequestIO(BaseModel):
    """Start an import job from a saved plan or a spec+source pair."""

    plan_id: str = ""
    source: str = ""
    spec: dict[str, Any] = Field(default_factory=dict)


class ExportRequestIO(BaseModel):
    """Start an export job."""

    dataset: str
    destination: str
    format: str = "pixano_jsonl"
    media: Literal["files", "uris"] = "files"


class JobResponse(BaseModel):
    """One job, as stored."""

    job_id: str
    kind: str
    dataset: str
    status: str
    progress: dict[str, Any] = Field(default_factory=dict)
    error: dict[str, Any] = Field(default_factory=dict)
    created_at: float = 0.0
    updated_at: float = 0.0


def _job_response(job: JobRecord) -> JobResponse:
    return JobResponse(
        job_id=job.id,
        kind=job.kind,
        dataset=job.dataset,
        status=job.status,
        progress=job.progress,
        error={key: value for key, value in job.error.items() if key != "cancel_requested"},
        created_at=job.created_at,
        updated_at=job.updated_at,
    )


# ----------------------------------------------------------------------
# /io routes
# ----------------------------------------------------------------------


@router.get("/formats", operation_id="list_io_formats")
def list_formats() -> list[dict[str, Any]]:
    """List registered data formats and their capabilities."""
    return [
        {
            "name": data_format.name,
            "title": data_format.title,
            "can_import": data_format.importer_cls is not None,
            "can_export": data_format.name in ("pixano_jsonl", "coco"),
            "capabilities": {
                "media_kinds": sorted(data_format.capabilities.media_kinds),
                "annotation_kinds": sorted(data_format.capabilities.annotation_kinds),
                "supports_resume": data_format.capabilities.supports_resume,
            },
        }
        for data_format in FORMATS
    ]


class FolderEntry(BaseModel):
    """One browsable subfolder of a server directory."""

    name: str
    path: str
    hint: str = ""  # "pixano" | "lerobot" | "" — shallow source markers for the picker


class FolderBrowseResponse(BaseModel):
    """A server directory listing for the wizard's source picker."""

    path: str
    parent: str | None
    entries: list[FolderEntry]


_BROWSE_MAX_ENTRIES = 500


@router.get("/browse", operation_id="browse_server_folders")
def browse_folders(path: str = "") -> FolderBrowseResponse:
    """List a server directory's subfolders (the wizard's source picker).

    Directories only — import sources are folders; defaults to the server
    user's home directory. This exposes no surface the import API does not
    already have: /io/analyze accepts arbitrary server paths.
    """
    base = (Path(path).expanduser() if path.strip() else Path.home()).resolve()
    if not base.is_dir():
        raise HTTPException(status_code=404, detail=f"Not a directory on the server: {base}")
    try:
        children = sorted(p for p in base.iterdir() if p.is_dir() and not p.name.startswith("."))
    except PermissionError:
        raise HTTPException(status_code=403, detail=f"Permission denied: {base}") from None
    entries: list[FolderEntry] = []
    for child in children[:_BROWSE_MAX_ENTRIES]:
        hint = ""
        try:
            if (child / "dataset.yaml").is_file():
                hint = "pixano"
            elif (child / "meta" / "info.json").is_file():
                hint = "lerobot"
        except OSError:
            hint = ""
        entries.append(FolderEntry(name=child.name, path=str(child), hint=hint))
    parent = str(base.parent) if base.parent != base else None
    return FolderBrowseResponse(path=str(base), parent=parent, entries=entries)


@router.post("/analyze", operation_id="analyze_import_source")
def analyze_source(request: AnalyzeRequest, settings: Annotated[Settings, Depends(get_settings)]) -> dict[str, Any]:
    """Analyze a source; returns the plan JSON (and a plan_id for later execution)."""
    store, _ = _runner(settings)
    if "importer" in request.spec or "info_py" in request.spec:
        raise HTTPException(status_code=400, detail="The REST API does not execute user Python (CLI-only options).")
    try:
        spec = ImportSpec.model_validate(_spec_payload_for_source(request.source, request.spec))
        plan = analyze(request.source, spec)
    except PixanoDataError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    payload = plan.model_dump()
    if request.save_plan:
        payload["plan_id"] = store.save_plan(plan, source=request.source)
    return payload


@router.post("/imports", status_code=202, operation_id="start_import_job")
def start_import(request: ImportRequestIO, settings: Annotated[Settings, Depends(get_settings)]) -> JobResponse:
    """Queue an import job (202): from a saved plan_id, or a spec+source pair."""
    store, runner = _runner(settings)
    if not request.plan_id and not request.source:
        raise HTTPException(status_code=422, detail="Provide plan_id or source.")
    if request.plan_id and store.get_plan(request.plan_id) is None:
        raise HTTPException(status_code=409, detail=f"Plan '{request.plan_id}' not found or expired (re-analyze).")
    source = request.source or (store.get_plan(request.plan_id) or (None, ""))[1]
    job = runner.submit_import(source, _spec_payload_for_source(source, request.spec), plan_id=request.plan_id)
    return _job_response(job)


@router.post("/exports", status_code=202, operation_id="start_export_job")
def start_export(request: ExportRequestIO, settings: Annotated[Settings, Depends(get_settings)]) -> JobResponse:
    """Queue an export job (202)."""
    store, runner = _runner(settings)
    dataset_dir = settings.library_dir / to_snake_case(request.dataset)  # type: ignore[operator]
    if not dataset_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Dataset '{request.dataset}' not found in the library.")
    job = runner.submit_export(str(dataset_dir), request.destination, request.format, request.media)
    return _job_response(job)


@router.get("/jobs", operation_id="list_io_jobs")
def list_jobs(settings: Annotated[Settings, Depends(get_settings)], limit: int = 50) -> list[JobResponse]:
    """Most recent jobs first."""
    store, _ = _runner(settings)
    return [_job_response(job) for job in store.list_jobs(limit=limit)]


@router.get("/jobs/{job_id}", operation_id="get_io_job")
def get_job(job_id: str, settings: Annotated[Settings, Depends(get_settings)]) -> JobResponse:
    """One job by id."""
    store, _ = _runner(settings)
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found.")
    return _job_response(job)


@router.post("/jobs/{job_id}/cancel", operation_id="cancel_io_job")
def cancel_job(job_id: str, settings: Annotated[Settings, Depends(get_settings)]) -> JobResponse:
    """Request cooperative cancellation (observed at the next flush boundary)."""
    store, _ = _runner(settings)
    try:
        return _job_response(store.request_cancel(job_id))
    except JobStateError as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.post("/jobs/{job_id}/resume", status_code=202, operation_id="resume_io_job")
def resume_job(job_id: str, settings: Annotated[Settings, Depends(get_settings)]) -> JobResponse:
    """Resume an interrupted/errored import from its last committed checkpoint."""
    _, runner = _runner(settings)
    try:
        return _job_response(runner.submit_resume(job_id))
    except (JobStateError, PixanoDataError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from None


@router.delete("/jobs/{job_id}", operation_id="rollback_io_job")
def rollback_job(job_id: str, settings: Annotated[Settings, Depends(get_settings)]) -> JobResponse:
    """Roll back a completed add-mode import (version restore, else namespace delete)."""
    store, runner = _runner(settings)
    try:
        runner.rollback(job_id)
    except (JobStateError, PixanoDataError) as error:
        raise HTTPException(status_code=409, detail=str(error)) from None
    job = store.get_job(job_id)
    assert job is not None
    return _job_response(job)


# ----------------------------------------------------------------------
# Deprecated GUI alias (removed in 0.9): the shipped modal polls these.
# ----------------------------------------------------------------------

IMPORT_TYPES = ("unlabeled_images", "unlabeled_videos")

_LEGACY_STATUS = {
    "pending": "pending",
    "running": "running",
    "done": "done",
    "error": "error",
    "interrupted": "error",
    "cancelled": "error",
    "rolled_back": "error",
}


class ImportRequest(BaseModel):
    """Legacy request body (shipped import modal)."""

    source_dir: str
    import_type: str = "unlabeled_images"
    dataset_name: str = ""


class ImportJobResponse(BaseModel):
    """Legacy response shape the modal polls."""

    job_id: str
    status: str
    message: str
    dataset_id: str


def _legacy_response(job: JobRecord) -> ImportJobResponse:
    message = job.error.get("message", "") or job.progress.get("message", "")
    if job.status == "done":
        records = job.progress.get("table_counts", {}).get("records", 0)
        message = f"Successfully imported {records} item(s)."
    return ImportJobResponse(
        job_id=job.id,
        status=_LEGACY_STATUS.get(job.status, "error"),
        message=message,
        dataset_id=job.dataset if job.status == "done" else "",
    )


def _prepare_legacy_source(source_dir: Path, import_type: str, staging: Path) -> tuple[Path, dict[str, Any]]:
    """Arrange the flat GUI folder into an importable source (split dir + spec)."""
    if import_type == "unlabeled_images":
        os.symlink(source_dir.resolve(), staging / "val")
        return staging, {"workspace": "image"}

    # unlabeled_videos: the shipped UI browses frame sequences (flip to real
    # Video rows rides the video-browse UI slice).
    import cv2

    split_dir = staging / "val"
    frames_root = split_dir / "frames"
    frames_root.mkdir(parents=True)
    metadata_lines: list[str] = []
    video_files = sorted(f for f in source_dir.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS)
    if not video_files:
        raise SpecValidationError(f"No video files found in {source_dir}.")
    for video_path in video_files:
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
            raise SpecValidationError(f"Could not extract any frames from {video_path.name}.")
        metadata_lines.append(
            json.dumps({"views": {"image": {"frame_pattern": f"frames/{video_path.stem}/*.jpg", "fps": round(fps)}}})
        )
    (split_dir / "metadata.jsonl").write_text("\n".join(metadata_lines) + "\n")
    return staging, {"workspace": "video"}


@legacy_router.post("/import", response_model=ImportJobResponse, operation_id="start_dataset_import", deprecated=True)
def legacy_start_import(
    request: ImportRequest, settings: Annotated[Settings, Depends(get_settings)]
) -> ImportJobResponse:
    """Start a legacy import job from a local folder (deprecated alias)."""
    if request.import_type not in IMPORT_TYPES:
        raise HTTPException(status_code=400, detail=f"Unknown import type: {request.import_type!r}.")
    source_dir = Path(request.source_dir)
    if not source_dir.is_dir():
        raise HTTPException(status_code=400, detail=f"Directory not found: {request.source_dir}")
    store, runner = _runner(settings)

    name = request.dataset_name.strip() or source_dir.name
    staging = Path(tempfile.mkdtemp(prefix="pixano-gui-import-"))

    def prepare() -> tuple[str, dict[str, Any]]:
        # Frame extraction (cv2) is heavy — it runs on the job thread, never here.
        source, dataset_extras = _prepare_legacy_source(source_dir, request.import_type, staging)
        return str(source), dataset_extras

    spec_payload = {"dataset": {"name": name}, "format": "pixano_jsonl"}
    job = runner.submit_import(str(source_dir), spec_payload, prepare=prepare)
    return _legacy_response(job)


@legacy_router.get(
    "/import/{job_id}", response_model=ImportJobResponse, operation_id="get_import_job", deprecated=True
)
def legacy_get_import_job(job_id: str, settings: Annotated[Settings, Depends(get_settings)]) -> ImportJobResponse:
    """Poll a legacy import job (deprecated alias)."""
    store, _ = _runner(settings)
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Import job '{job_id}' not found.")
    return _legacy_response(job)
