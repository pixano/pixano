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
from .manifest import ImportManifest
from .plan import AnalyzeLimits, Finding, ImportPlan, PreflightReport, Provenance, SamplePreview
from .progress import ProgressEvent, ProgressSink, ThrottledSink, TqdmSink


__all__ = [
    "AnalyzeLimits",
    "Finding",
    "FormatDetectionError",
    "IdLedger",
    "ImportManifest",
    "ImportPlan",
    "JobStateError",
    "MediaResolutionError",
    "MetadataError",
    "PixanoDataError",
    "PlanMismatchError",
    "PreflightReport",
    "ProgressEvent",
    "ProgressSink",
    "Provenance",
    "ResumeError",
    "SamplePreview",
    "SpecValidationError",
    "ThrottledSink",
    "TqdmSink",
    "UnsupportedStorageError",
    "namespace_prefix",
    "stable_id",
]
