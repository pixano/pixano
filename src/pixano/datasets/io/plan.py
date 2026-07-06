# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Analysis-phase artifacts: provenance, findings, preflight report, import plan.

An :class:`ImportPlan` is the fully JSON-serializable output of an importer's
side-effect-free ``analyze()`` phase. The CLI renders it for confirmation, the
GUI renders it as the wizard's preview step, and ingestion executes it —
one artifact, three consumers (spec §8).
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, Field


Severity = Literal["error", "warning", "info"]

# How many sample locations to keep per finding (mirrors the previous
# MetadataValidationReport behavior).
_MAX_SAMPLES_PER_FINDING = 5


def fingerprint(payload: Any) -> str:
    """Compute a stable fingerprint of a JSON-serializable payload."""
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


class Provenance(BaseModel):
    """Where a finding or error comes from in the source data."""

    file: str | None = None
    line: int | None = None
    json_pointer: str | None = None
    record_key: str | None = None

    def location(self) -> str:
        """Render the provenance as a compact `file:line:pointer` string."""
        parts = [part for part in (self.file, self.line, self.json_pointer, self.record_key) if part is not None]
        return ":".join(str(part) for part in parts) if parts else "<unknown>"


class Finding(BaseModel):
    """One aggregated validation finding (same code across many rows)."""

    code: str
    severity: Severity = "error"
    count: int = 0
    samples: list[Provenance] = Field(default_factory=list)
    suggestion: str = ""

    def add(self, provenance: Provenance) -> None:
        """Record one more occurrence, keeping at most a few sample locations."""
        self.count += 1
        if len(self.samples) < _MAX_SAMPLES_PER_FINDING and provenance not in self.samples:
            self.samples.append(provenance)


class PreflightReport(BaseModel):
    """Aggregated validation findings for one analyze pass.

    Generalizes the folder-import ``MetadataValidationReport``: findings are
    keyed by code, carry sample provenances, and split into errors/warnings.
    """

    findings: dict[str, Finding] = Field(default_factory=dict)

    def add(
        self,
        code: str,
        provenance: Provenance,
        severity: Severity = "error",
        suggestion: str = "",
    ) -> None:
        """Record one occurrence of a finding."""
        finding = self.findings.get(code)
        if finding is None:
            finding = Finding(code=code, severity=severity, suggestion=suggestion)
            self.findings[code] = finding
        finding.add(provenance)

    @property
    def errors(self) -> list[Finding]:
        """Findings with error severity."""
        return [finding for finding in self.findings.values() if finding.severity == "error"]

    @property
    def warnings(self) -> list[Finding]:
        """Findings with warning or info severity."""
        return [finding for finding in self.findings.values() if finding.severity != "error"]

    @property
    def error_count(self) -> int:
        """Total number of error occurrences."""
        return sum(finding.count for finding in self.errors)

    @property
    def warning_count(self) -> int:
        """Total number of warning/info occurrences."""
        return sum(finding.count for finding in self.warnings)

    @property
    def is_valid(self) -> bool:
        """Whether the analyzed source has no errors."""
        return self.error_count == 0


class SamplePreview(BaseModel):
    """One normalized preview record shown before ingestion."""

    record: dict[str, Any]
    thumbnails: dict[str, str] = Field(default_factory=dict)  # logical view name -> data URL


class AnalyzeLimits(BaseModel):
    """Bounds for the analyze phase (spec §8: analyze is pure AND bounded)."""

    max_lines: int | None = None
    max_bytes: int | None = None
    max_media_probes: int = 32
    max_previews: int = 5


class PlanTotals(BaseModel):
    """Record/media totals discovered (or estimated) at analyze time."""

    records: int | None = None
    media_bytes: int | None = None
    estimated: bool = False


class ImportPlan(BaseModel):
    """The executable output of an importer's analyze phase."""

    plan_id: str = ""
    format: str
    importer_version: str = ""
    spec_fingerprint: str = ""
    source_fingerprint: str = ""
    splits: dict[str, int | None] = Field(default_factory=dict)
    totals: PlanTotals = Field(default_factory=PlanTotals)
    inferred_schema: dict[str, Any] | None = None
    report: PreflightReport = Field(default_factory=PreflightReport)
    previews: list[SamplePreview] = Field(default_factory=list)
    media_size_estimate_bytes: int | None = None

    @property
    def plan_fingerprint(self) -> str:
        """Fingerprint binding this plan to its spec and source states."""
        return fingerprint({"spec": self.spec_fingerprint, "source": self.source_fingerprint})
