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

An import can queue the embeddings job of what it imported once it is done, on
the job queue shared with pixano-worker (`pixano.api.jobs.follow_ups`).
"""

import asyncio
import json
import logging
import os
import tempfile
import threading
from functools import partial
from pathlib import Path
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field, ValidationError
from s3path import S3Path

from pixano.api.jobs.follow_ups import (
    NO_MODEL_SERVED,
    asks_for_embeddings,
    considers_embeddings,
    decide_embeddings,
    embeddings_unavailable,
    plan_has_still_images,
    submit_follow_ups,
)
from pixano.api.settings import Settings, get_settings
from pixano.datasets.io import FORMATS, ExportSpec, ImportSpec, PixanoDataError, analyze
from pixano.datasets.io.errors import JobStateError, SpecValidationError
from pixano.datasets.io.jobs import FollowUp, JobRecord, JobRunner, JobStore
from pixano.datasets.io.media import VIDEO_EXTENSIONS
from pixano.inference.types import InferenceTask
from pixano.schemas import ReviewStatus
from pixano.utils import to_snake_case


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/io", tags=["Data IO"])
legacy_router = APIRouter(prefix="/datasets", tags=["Datasets"])

_runners: dict[str, tuple[JobStore, JobRunner]] = {}
_runners_lock = threading.Lock()


def _data_dir(settings: Settings) -> Path:
    if isinstance(settings.library_dir, S3Path) or not isinstance(settings.library_dir, Path):
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
            starter = partial(submit_follow_ups, settings.database_url, settings.library_dir)
            _runners[key] = (store, JobRunner(store, data_dir, follow_up_starter=starter))
        return _runners[key]


# How long an inference may take to say which embeddings models it serves. The answer is a short
# list: past this, an import goes on without it, rather than wait for the client's own timeout and
# its retries — three minutes on an inference that hangs.
EMBEDDINGS_MODELS_LOOKUP_TIMEOUT_S = 5.0


async def _served_embedding_models(settings: Settings) -> list[str]:
    """The embeddings models the inferences this server is connected to serve, by name, each once.

    The worker asks its own inference, often the same: a model left out here can still be named.
    An inference that does not answer in time serves none, as `GET /inference/models/list` says.
    """
    names: list[str] = []
    # A copy: connecting an inference adds a provider while this awaits.
    for provider_name, provider in list(settings.inference_providers.items()):
        try:
            served = await asyncio.wait_for(
                provider.list_models(task=InferenceTask.EMBEDDING), EMBEDDINGS_MODELS_LOOKUP_TIMEOUT_S
            )
        except Exception:
            logger.warning("Failed to list the embeddings models of provider %s", provider_name, exc_info=True)
            continue
        names += [model.name for model in served]
    return list(dict.fromkeys(names))


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
    compute_embeddings: bool | None = Field(
        default=None,
        description="Queue the embeddings job of what is imported once the import is done — one per "
        "model the dataset already holds too. Unset follows the server's default "
        "(PIXANO_EMBEDDINGS_AFTER_IMPORT), which only applies where the job can run.",
    )
    embeddings_model: str | None = Field(
        default=None,
        description="The model the embeddings job runs, beside the models the dataset already holds. Unset "
        "is the server's (PIXANO_EMBEDDINGS_MODEL), else the first embeddings model the inference serves, "
        "used only for a dataset without embeddings.",
    )


class ExportRequestIO(BaseModel):
    """Start an export job."""

    dataset: str
    destination: str
    format: str = "pixano_jsonl"
    media: Literal["files", "uris"] = "files"
    options: dict[str, Any] = Field(default_factory=dict)
    review_statuses: list[ReviewStatus] = Field(
        default_factory=list,
        description="Review statuses of the model annotations to export; annotations no model "
        "produced are always exported. Empty exports every annotation.",
    )


class FollowUpResponse(BaseModel):
    """A processing job an import queues once it is done, and what became of it.

    Attributes:
        kind: The processing job kind: `embeddings`.
        params: Its parameters, the model among them.
        job_id: The queued job, followed in the jobs panel; empty until queued.
        error: Why it was not queued; empty otherwise.
    """

    kind: str
    params: dict[str, Any] = Field(default_factory=dict)
    job_id: str = ""
    error: str = ""


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
    follow_ups: list[FollowUpResponse] = Field(default_factory=list)


class ImportEmbeddingsOffer(BaseModel):
    """Whether an import can queue the embeddings job of what it imports, as the import form asks.

    Attributes:
        queue_configured: A job queue is configured (PIXANO_DATABASE_URL). Without one, the import
            form does not offer the embeddings at all.
        available: The job can run now: a job queue reachable, a worker that declared the job, and
            a model to name.
        reason: Why it cannot, when it cannot.
        enabled_by_default: The server's default for an import (PIXANO_EMBEDDINGS_AFTER_IMPORT).
        models: The models to choose from: the server's, then those the inference serves.
        default_model: The model proposed: the server's, else the first the inference serves.
    """

    queue_configured: bool
    available: bool
    reason: str | None = None
    enabled_by_default: bool
    models: list[str] = Field(default_factory=list)
    default_model: str | None = None


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
        follow_ups=[FollowUpResponse(**follow_up.to_json()) for follow_up in job.follow_ups],
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


class UploadSessionResponse(BaseModel):
    """One staged client upload: the wizard imports from `source` when done."""

    upload_id: str
    source: str


def _uploads_root(settings: Settings) -> Path:
    from pixano.datasets.io.engine import state_dir

    return state_dir(_data_dir(settings)) / "uploads"


def _upload_dir(settings: Settings, upload_id: str) -> Path:
    if not upload_id or "/" in upload_id or upload_id.startswith("."):
        raise HTTPException(status_code=404, detail=f"Unknown upload session '{upload_id}'.")
    session_dir = _uploads_root(settings) / upload_id
    if not session_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Unknown upload session '{upload_id}'.")
    return session_dir


def _staged_path(session_dir: Path, rel_path: str) -> Path:
    """Validate a client-supplied relative path (no traversal, no absolutes)."""
    if not rel_path or rel_path.startswith("/") or "\\" in rel_path:
        raise HTTPException(status_code=400, detail=f"Invalid upload path '{rel_path}'.")
    parts = rel_path.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise HTTPException(status_code=400, detail=f"Invalid upload path '{rel_path}'.")
    return session_dir.joinpath(*parts)


@router.post("/uploads", status_code=201, operation_id="create_upload_session")
def create_upload_session(settings: Annotated[Settings, Depends(get_settings)]) -> UploadSessionResponse:
    """Create a staging folder for a client-side folder upload (the wizard's source picker).

    Users browse and pick a folder on THEIR machine; the files stream into this
    session and the import runs against the staged copy. The session is removed
    when its import finishes (or by boot GC after 24h if abandoned).
    """
    import shortuuid

    upload_id = shortuuid.uuid()
    session_dir = _uploads_root(settings) / upload_id
    session_dir.mkdir(parents=True)
    return UploadSessionResponse(upload_id=upload_id, source=str(session_dir))


@router.put("/uploads/{upload_id}/files/{rel_path:path}", operation_id="upload_session_file")
async def upload_session_file(
    upload_id: str,
    rel_path: str,
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    """Stream one file's raw body into the session, preserving its relative path."""
    target = _staged_path(_upload_dir(settings, upload_id), rel_path)
    target.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with target.open("wb") as sink:
        async for chunk in request.stream():
            sink.write(chunk)
            written += len(chunk)
    return {"path": rel_path, "bytes": written}


@router.delete("/uploads/{upload_id}", status_code=204, operation_id="delete_upload_session")
def delete_upload_session(upload_id: str, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Discard a staged upload (wizard cancelled before importing)."""
    import shutil

    shutil.rmtree(_upload_dir(settings, upload_id))


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


@router.get("/imports/embeddings", operation_id="get_import_embeddings_offer")
async def import_embeddings_offer(settings: Annotated[Settings, Depends(get_settings)]) -> ImportEmbeddingsOffer:
    """Whether an import can queue the embeddings job of what it imports, and with which models.

    The queue and the inference are asked at once: the import form waits for the slower of the two.
    """
    served, reason = await asyncio.gather(
        _served_embedding_models(settings), run_in_threadpool(embeddings_unavailable, settings.database_url)
    )
    # The deployment's model first: it may be served by the worker's inference only.
    default_model = settings.embeddings_model or next(iter(served), None)
    models = served if default_model is None or default_model in served else [default_model, *served]
    if reason is None and default_model is None:
        reason = NO_MODEL_SERVED
    return ImportEmbeddingsOffer(
        queue_configured=bool(settings.database_url),
        available=reason is None,
        reason=reason,
        enabled_by_default=settings.embeddings_after_import,
        models=models,
        default_model=default_model,
    )


@router.post("/imports", status_code=202, operation_id="start_import_job")
async def start_import(request: ImportRequestIO, settings: Annotated[Settings, Depends(get_settings)]) -> JobResponse:
    """Queue an import job (202): from a saved plan_id, or a spec+source pair.

    The request is checked first; then what the import queues once done is settled, which may ask
    the inference for a model and the job queue whether it can run the job.
    """
    runner, source, spec_payload, has_images = await run_in_threadpool(_checked_import, request, settings)
    follow_ups = await _import_follow_ups(request, settings, has_images)
    job = await run_in_threadpool(
        partial(runner.submit_import, source, spec_payload, plan_id=request.plan_id, follow_ups=follow_ups)
    )
    return _job_response(job)


def _checked_import(
    request: ImportRequestIO, settings: Settings
) -> tuple[JobRunner, str, dict[str, Any], bool | None]:
    """The runner, the import's source and spec, and whether its plan holds still images; or why it cannot start.

    Whether it holds still images is None when no plan was saved: the import analyses its source then.
    """
    store, runner = _runner(settings)
    if not request.plan_id and not request.source:
        raise HTTPException(status_code=422, detail="Provide plan_id or source.")
    stored = store.get_plan(request.plan_id) if request.plan_id else None
    if request.plan_id and stored is None:
        raise HTTPException(status_code=409, detail=f"Plan '{request.plan_id}' not found or expired (re-analyze).")
    source = request.source or (stored or (None, ""))[1]
    spec_payload = _spec_payload_for_source(source, request.spec)
    if not (spec_payload.get("dataset") or {}).get("name"):
        try:
            staged = Path(source).resolve().is_relative_to(_uploads_root(settings).resolve())
        except (OSError, ValueError):
            staged = False
        if staged:
            raise HTTPException(
                status_code=422,
                detail="Imports from a staged upload need dataset.name (the upload folder name is opaque).",
            )
    return runner, source, spec_payload, plan_has_still_images(stored[0].inferred_schema) if stored else None


async def _import_follow_ups(request: ImportRequestIO, settings: Settings, has_images: bool | None) -> list[FollowUp]:
    """What the import queues once done: the embeddings job, as asked or by the server's default.

    The default only applies where the job can run, which the queue is asked first: an installation
    without one never waits for the inference. Nor does it apply to an import whose plan holds no
    still image. Asked for — a model named is asking —, the job is kept whatever the queue says, and
    the import says why if it is not queued.
    """
    wanted = asks_for_embeddings(request.compute_embeddings, request.embeddings_model)
    if not considers_embeddings(wanted, default_on=settings.embeddings_after_import, has_images=has_images):
        return []
    unavailable = await run_in_threadpool(embeddings_unavailable, settings.database_url) if wanted is None else None
    if unavailable is not None:
        return []
    # The request's model, the deployment's, then the first the inference serves: asked last, only if needed.
    model = (
        request.embeddings_model
        or settings.embeddings_model
        or next(iter(await _served_embedding_models(settings)), None)
    )
    return decide_embeddings(
        wanted,
        model,
        named=bool(request.embeddings_model),
        default_on=settings.embeddings_after_import,
        unavailable=unavailable,
    )


@router.post("/exports", status_code=202, operation_id="start_export_job")
def start_export(request: ExportRequestIO, settings: Annotated[Settings, Depends(get_settings)]) -> JobResponse:
    """Queue an export job (202)."""
    store, runner = _runner(settings)
    try:
        # The same ExportSpec the CLI and the Python API build (spec §3).
        spec = ExportSpec.model_validate(request.model_dump(exclude={"dataset"}))
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error)) from None
    dataset_dir = settings.library_dir / to_snake_case(request.dataset)  # type: ignore[operator]
    if not dataset_dir.is_dir():
        raise HTTPException(status_code=404, detail=f"Dataset '{request.dataset}' not found in the library.")
    job = runner.submit_export(
        str(dataset_dir),
        spec.destination,
        spec.format,
        spec.media,
        spec.options,
        review_statuses=[status.value for status in spec.review_statuses],
    )
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
    """Roll back a completed add import only when the dataset has no later mutations."""
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
