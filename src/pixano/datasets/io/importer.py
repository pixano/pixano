# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The importer contract: the only surface a format author implements (spec §3.1).

An importer has two responsibilities, strictly separated:

- ``analyze(source, spec, limits)`` — side-effect-free, bounded inspection of
  the source producing an :class:`~pixano.datasets.io.plan.ImportPlan` (counts,
  findings, previews, inferred schema). It must use the same parser as
  ingestion so that what was validated is what gets imported.
- ``iter_batches(plan, spec, cursor)`` — stream the source as
  :class:`BatchBundle`s of table rows. Iteration order must be deterministic
  (sorted globs, stable file order): determinism is what makes resume and
  idempotent re-runs possible.

Importers never write to the dataset — the import engine owns all writes.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, ClassVar, Iterator, Literal

from pixano.datasets.dataset_info import DatasetInfo  # noqa: TC001

from .plan import AnalyzeLimits, ImportPlan, Provenance


if TYPE_CHECKING:
    import pyarrow as pa
    from lancedb.pydantic import LanceModel

    from .spec import ImportSpec


Cursor = dict[str, Any]
"""Importer-opaque, JSON-serializable resume position (e.g. ``{"split": "train", "line": 40960}``)."""


@dataclass(frozen=True)
class SourceRef:
    """A reference to an import source."""

    kind: Literal["local_dir", "local_file", "hf_hub"]
    path: Path | None = None
    url: str | None = None

    @classmethod
    def from_string(cls, source: str) -> "SourceRef":
        """Build a SourceRef from a CLI/API source string.

        ``hub://org/repo`` targets the Hugging Face hub; anything else is a
        local path (directory or file).
        """
        if source.startswith("hub://"):
            return cls(kind="hf_hub", url=source.removeprefix("hub://"))
        path = Path(source)
        return cls(kind="local_dir" if path.is_dir() else "local_file", path=path)

    def location(self) -> str:
        """Human-readable source location."""
        return str(self.path) if self.path is not None else (self.url or "<unknown>")


@dataclass(frozen=True)
class DetectResult:
    """Outcome of a cheap format sniff on a source."""

    confidence: float  # 0.0-1.0
    evidence: str = ""


@dataclass
class BatchBundle:
    """One streamed batch of rows, grouped by table.

    ``tables`` maps canonical table names to either a list of LanceModel rows
    (the ergonomic path) or a ``pyarrow`` RecordBatch/Table (the high-volume
    path). ``cursor`` is the resume position *after* this bundle is committed.
    """

    tables: dict[str, "list[LanceModel] | pa.RecordBatch | pa.Table"]
    cursor: Cursor = field(default_factory=dict)
    provenance: Provenance | None = None


class DatasetImporter(ABC):
    """Base class for format importers (spec §3.1/§7).

    Class attributes declare the importer's identity and guarantees:

    Attributes:
        format_name: Registry name of the format this importer reads.
        importer_version: Semver of the importer code, stamped into dataset
            provenance at import time.
        supports_resume: Whether ``iter_batches`` honors a ``cursor``.
        deterministic_ids: Whether re-running the same source yields the same
            row ids. Importers without deterministic ids are restart-only:
            the engine refuses to resume them.
    """

    format_name: ClassVar[str]
    importer_version: ClassVar[str] = "0.0.0"
    supports_resume: ClassVar[bool] = False
    deterministic_ids: ClassVar[bool] = False

    def probe(self, source: SourceRef) -> DetectResult | None:
        """Cheaply sniff whether this importer can read the source.

        Returns None when the source does not look like this format.
        """
        return None

    def effective_namespace(self, spec: "ImportSpec", source: SourceRef) -> str:
        """The id namespace actually used for derived ids (rollback anchor).

        Defaults to the spec's namespace, else a source-derived identity —
        the same rule every built-in importer applies.
        """
        if spec.ids.namespace:
            return spec.ids.namespace
        if source.path is not None:
            return source.path.name
        return (source.url or "source").replace("/", "_")

    def resolve_info(self, spec: "ImportSpec", source: SourceRef | None = None) -> "DatasetInfo":
        """Resolve the target schema for this format.

        The default honors the user's spec (schema block, manifest, or
        workspace preset). Formats with an intrinsic schema (COCO, LeRobot)
        override this to supply it when the spec declares none; ``source``
        is provided so source-dependent schemas (LeRobot cameras) can look.
        """
        from .spec import resolve_dataset_info

        return resolve_dataset_info(spec)

    @abstractmethod
    def analyze(self, source: SourceRef, spec: "ImportSpec", limits: AnalyzeLimits) -> ImportPlan:
        """Inspect the source without side effects and produce an import plan."""
        ...

    @abstractmethod
    def iter_batches(
        self,
        source: SourceRef,
        spec: "ImportSpec",
        plan: ImportPlan,
        cursor: Cursor | None = None,
    ) -> Iterator[BatchBundle]:
        """Stream the source as table-row bundles, optionally resuming at a cursor."""
        ...
