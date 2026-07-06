# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The shared Python entry points behind the CLI and the REST API (spec §3.1).

``analyze`` and ``import_dataset`` are the whole public surface: the CLI
renders the returned :class:`ImportPlan` and calls ``import_dataset`` with a
tqdm sink; the REST layer does the same with a job-store sink.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Sequence

from pixano.datasets.dataset_info import DatasetInfo


if TYPE_CHECKING:
    from pixano.datasets.dataset import Dataset

from .engine import ImportEngine, ImportResult
from .errors import SpecValidationError
from .importer import DatasetImporter, SourceRef
from .plan import AnalyzeLimits, ImportPlan
from .progress import ProgressSink
from .registry import FORMATS
from .spec import ImportSpec


def _resolve_importer(source: SourceRef, spec: ImportSpec, importer: DatasetImporter | None) -> DatasetImporter:
    if importer is not None:
        return importer
    if spec.format == "auto":
        data_format = FORMATS.detect(source)
    else:
        data_format = FORMATS.get(spec.format)
    if data_format.importer_cls is None:
        raise SpecValidationError(f"Data format '{data_format.name}' is export-only.")
    return data_format.importer_cls()


def analyze(
    source: str | Path,
    spec: ImportSpec | None = None,
    limits: AnalyzeLimits | None = None,
    importer: DatasetImporter | None = None,
) -> ImportPlan:
    """Analyze a source without side effects and return its import plan."""
    spec = spec or ImportSpec()
    source_ref = SourceRef.from_string(str(source))
    resolved = _resolve_importer(source_ref, spec, importer)
    return resolved.analyze(source_ref, spec, limits or AnalyzeLimits())


def import_dataset(
    source: str | Path,
    data_dir: str | Path,
    spec: ImportSpec | None = None,
    *,
    plan: ImportPlan | None = None,
    info: DatasetInfo | None = None,
    importer: DatasetImporter | None = None,
    sinks: Sequence[ProgressSink] = (),
    engine: ImportEngine | None = None,
) -> ImportResult:
    """Import a source into the data directory's library (analyze → validate → ingest).

    Args:
        source: Source directory/file, or ``hub://org/repo``.
        data_dir: The Pixano data directory (holds ``library/``).
        spec: Declarative import spec; defaults apply when omitted.
        plan: A previously computed plan; re-analyzed when omitted.
        info: Target dataset schema; derived from the workspace preset when omitted.
        importer: Explicit importer instance (advanced; bypasses the registry).
        sinks: Progress sinks (e.g. a tqdm sink).
        engine: Preconfigured engine (jobs wire checkpoints/cancellation through it).

    Returns:
        The import result (dataset id/path, per-table row counts).
    """
    spec = spec or ImportSpec()
    source_ref = SourceRef.from_string(str(source))
    resolved = _resolve_importer(source_ref, spec, importer)

    if plan is None:
        plan = resolved.analyze(source_ref, spec, AnalyzeLimits())
    if not plan.report.is_valid:
        raise SpecValidationError(
            f"Analysis found {plan.report.error_count} error(s); fix the source or inspect the plan report."
        )

    if info is None:
        info = resolved.resolve_info(spec)
    if spec.dataset.name:
        info.name = spec.dataset.name
    if spec.dataset.description:
        info.description = spec.dataset.description

    engine = engine or ImportEngine(Path(data_dir))
    return engine.run(resolved, source_ref, spec, plan, info, sinks=sinks)


def export_dataset(
    dataset: "Dataset | Path | str",
    destination: str | Path,
    format: str = "pixano_jsonl",
    media: str = "files",
) -> Path:
    """Export a dataset to a data format (spec §10).

    ``pixano_jsonl`` emits exactly the import grammar with explicit ids, so
    import → export → import is id-equal. Other formats arrive with their
    exporters (plan P3).
    """
    from pixano.datasets.dataset import Dataset

    if format != "pixano_jsonl":
        raise SpecValidationError(f"Export format '{format}' is not available yet; only 'pixano_jsonl' is.")
    if media not in ("files", "uris"):
        raise SpecValidationError("media must be 'files' or 'uris'.")

    from .formats.pixano_jsonl.exporter import PixanoJsonlExporter

    resolved = dataset if isinstance(dataset, Dataset) else Dataset(Path(dataset))
    return PixanoJsonlExporter(media=media).export(resolved, Path(destination))  # type: ignore[arg-type]
