# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Format registry: one record per data format, bundling importer + exporter (spec §7).

A single :class:`DataFormat` record gives import/export symmetry, capability-based
GUI enumeration (``params_model.model_json_schema()`` renders the options form),
and third-party extension through the ``pixano.formats`` entry-point group —
installed code, never uploaded code.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import TYPE_CHECKING, Callable, Iterator, Sequence

from pydantic import BaseModel

from .errors import FormatDetectionError, SpecValidationError
from .importer import DatasetImporter, DetectResult, SourceRef


if TYPE_CHECKING:
    from pixano.datasets.exporters.dataset_exporter import DatasetExporter


logger = logging.getLogger(__name__)

ENTRY_POINT_GROUP = "pixano.formats"


class EmptyParams(BaseModel):
    """Default (empty) format-options model."""

    model_config = {"extra": "forbid"}


@dataclass(frozen=True)
class Capabilities:
    """What a format can read/write — drives GUI picker enumeration and greying."""

    media_kinds: frozenset[str] = frozenset()  # {"image","video","sequence_frames","text","point_cloud"}
    annotation_kinds: frozenset[str] = frozenset()  # {"bbox","mask","keypoints","multi_path","message","text_span"}
    source_kinds: frozenset[str] = frozenset({"local_dir"})  # {"local_dir","local_file","hf_hub"}
    supports_resume: bool = False
    deterministic_ids: bool = False


@dataclass(frozen=True)
class DataFormat:
    """One registered data format."""

    name: str
    title: str
    importer_cls: type[DatasetImporter] | None = None  # None => export-only
    exporter_cls: "type[DatasetExporter] | None" = None  # None => import-only
    params_model: type[BaseModel] = EmptyParams
    capabilities: Capabilities = field(default_factory=Capabilities)
    detect: Callable[[SourceRef], DetectResult | None] | None = None


class FormatRegistry:
    """Registry of data formats: static built-ins plus entry-point plugins."""

    def __init__(self, builtin: Sequence[DataFormat] = ()):
        """Initialize with built-in formats; plugins load lazily on first access."""
        self._formats: dict[str, DataFormat] = {}
        self._entry_points_loaded = False
        for data_format in builtin:
            self.register(data_format)

    def register(self, data_format: DataFormat) -> None:
        """Register a format; duplicate names are an error."""
        if data_format.name in self._formats:
            raise SpecValidationError(f"Data format '{data_format.name}' is already registered.")
        self._formats[data_format.name] = data_format

    def get(self, name: str) -> DataFormat:
        """Look up a format by name."""
        self._load_entry_points()
        try:
            return self._formats[name]
        except KeyError:
            known = ", ".join(sorted(self._formats)) or "<none>"
            raise SpecValidationError(f"Unknown data format '{name}'. Known formats: {known}.") from None

    def names(self) -> list[str]:
        """All registered format names."""
        self._load_entry_points()
        return sorted(self._formats)

    def __iter__(self) -> Iterator[DataFormat]:
        """Iterate over registered formats."""
        self._load_entry_points()
        return iter(self._formats.values())

    def detect(self, source: SourceRef) -> DataFormat:
        """Detect the format of a source — never guesses.

        Every registered format's ``detect`` sniffs the source; the single
        highest-confidence match wins. No match or a tie raises
        :class:`FormatDetectionError` listing the candidates.
        """
        self._load_entry_points()
        candidates: list[tuple[float, DataFormat, str]] = []
        for data_format in self._formats.values():
            if data_format.detect is None:
                continue
            try:
                result = data_format.detect(source)
            except Exception as exc:
                logger.warning("Format '%s' detection failed on %s: %s", data_format.name, source.location(), exc)
                continue
            if result is not None and result.confidence > 0:
                candidates.append((result.confidence, data_format, result.evidence))

        if not candidates:
            known = ", ".join(self.names()) or "<none>"
            raise FormatDetectionError(
                f"Could not detect the data format of '{source.location()}'. Pass an explicit format (known: {known})."
            )
        candidates.sort(key=lambda c: c[0], reverse=True)
        if len(candidates) > 1 and candidates[0][0] == candidates[1][0]:
            tied = ", ".join(f"{fmt.name} ({evidence})" for _, fmt, evidence in candidates if _ == candidates[0][0])
            raise FormatDetectionError(
                f"Ambiguous data format for '{source.location()}': {tied}. Pass an explicit format."
            )
        return candidates[0][1]

    def _load_entry_points(self) -> None:
        if self._entry_points_loaded:
            return
        self._entry_points_loaded = True
        for entry_point in entry_points(group=ENTRY_POINT_GROUP):
            try:
                data_format = entry_point.load()
                if not isinstance(data_format, DataFormat):
                    raise TypeError(f"entry point must resolve to a DataFormat, got {type(data_format)}")
                self.register(data_format)
            except Exception as exc:
                # One broken plugin must not take the registry down.
                logger.warning("Skipping broken pixano.formats entry point '%s': %s", entry_point.name, exc)


FORMATS = FormatRegistry()
"""The process-wide format registry. Built-in formats register on import of their packages."""
