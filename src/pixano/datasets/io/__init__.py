# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Shared data import/export core (see docs/specs/data-import-export.md).

This package hosts the one import/export mechanism used by the CLI, the REST
API, and the Python API: declarative specs, format registry, importer
contract, and the import engine.
"""

from .api import analyze, import_dataset
from .engine import ImportEngine, ImportResult, replay_journals
from .errors import (
    FormatDetectionError,
    JobStateError,
    MediaResolutionError,
    MetadataError,
    PixanoDataError,
    PlanMismatchError,
    ResumeError,
    SpecValidationError,
    UnsupportedStorageError,
)
from .ids import IdLedger, namespace_prefix, stable_id
from .importer import BatchBundle, Cursor, DatasetImporter, DetectResult, SourceRef
from .manifest import ImportManifest
from .media import MediaResolver, ResolvedMedia, VideoProbe, ffprobe_available, probe_image, probe_video
from .plan import AnalyzeLimits, Finding, ImportPlan, PreflightReport, Provenance, SamplePreview
from .progress import ProgressEvent, ProgressSink, ThrottledSink, TqdmSink
from .registry import FORMATS, Capabilities, DataFormat, FormatRegistry
from .spec import ExportSpec, IdPolicy, ImportSpec, MediaPolicy, SchemaSpec, resolve_dataset_info, workspace_preset


__all__ = [
    "AnalyzeLimits",
    "ImportEngine",
    "ImportResult",
    "BatchBundle",
    "Capabilities",
    "Cursor",
    "DataFormat",
    "DatasetImporter",
    "DetectResult",
    "ExportSpec",
    "FORMATS",
    "Finding",
    "FormatDetectionError",
    "FormatRegistry",
    "IdLedger",
    "IdPolicy",
    "ImportManifest",
    "ImportPlan",
    "ImportSpec",
    "JobStateError",
    "MediaPolicy",
    "MediaResolutionError",
    "MediaResolver",
    "MetadataError",
    "PixanoDataError",
    "PlanMismatchError",
    "PreflightReport",
    "ProgressEvent",
    "ProgressSink",
    "Provenance",
    "ResolvedMedia",
    "ResumeError",
    "SamplePreview",
    "SchemaSpec",
    "SourceRef",
    "SpecValidationError",
    "ThrottledSink",
    "TqdmSink",
    "UnsupportedStorageError",
    "VideoProbe",
    "ffprobe_available",
    "analyze",
    "import_dataset",
    "namespace_prefix",
    "probe_image",
    "probe_video",
    "replay_journals",
    "resolve_dataset_info",
    "stable_id",
    "workspace_preset",
]


# Built-in formats register on package import (entry-point plugins load lazily).
from .formats.pixano_jsonl.importer import PIXANO_JSONL  # noqa: E402


FORMATS.register(PIXANO_JSONL)
