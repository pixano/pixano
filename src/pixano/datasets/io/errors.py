# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Typed error hierarchy for the data import/export core.

Every error carries an optional :class:`~pixano.datasets.io.plan.Provenance`
naming the file/line/JSON-pointer that produced it, so failures always point
at the offending source data.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from .plan import Provenance


class PixanoDataError(Exception):
    """Base class for all data import/export errors."""

    def __init__(self, message: str, provenance: "Provenance | None" = None):
        """Initialize the error with a message and optional source provenance."""
        self.provenance = provenance
        if provenance is not None:
            message = f"{message} [{provenance.location()}]"
        super().__init__(message)


class FormatDetectionError(PixanoDataError):
    """The source's data format could not be detected unambiguously."""


class SpecValidationError(PixanoDataError):
    """The declarative import/export spec is invalid."""


class MetadataError(PixanoDataError):
    """A metadata file or line does not conform to the declared format."""


class MediaResolutionError(PixanoDataError):
    """A media reference cannot be resolved under the active media policy."""


class PlanMismatchError(PixanoDataError):
    """The source changed between analysis and ingestion."""


class UnsupportedStorageError(PixanoDataError):
    """The operation is not supported on this storage backend (e.g. S3 data dirs)."""


class JobStateError(PixanoDataError):
    """The job is not in a state that allows the requested transition."""


class ResumeError(PixanoDataError):
    """The job cannot be resumed (e.g. its importer has no deterministic ids)."""
