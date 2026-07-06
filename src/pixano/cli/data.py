# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Pixano data import/export CLI (spec §9) — a thin shell over the shared io core."""

from pathlib import Path
from typing import Optional

import typer

from pixano.datasets.dataset import Dataset
from pixano.datasets.io import (
    FORMATS,
    ImportPlan,
    ImportSpec,
    PixanoDataError,
    TqdmSink,
    analyze,
    export_dataset,
    import_dataset,
)
from pixano.datasets.io.formats.pixano_jsonl.migrate import migrate_tree
from pixano.datasets.workspaces import WorkspaceType
from pixano.utils import to_snake_case


data_app = typer.Typer(help="Pixano dataset import/export commands.")

_SAMPLE_LIMIT = 5


def _render_plan(plan: ImportPlan) -> None:
    """Render an import plan the way the v1 preflight report was rendered."""
    typer.echo(f"Format: {plan.format} (importer {plan.importer_version})")
    for split, count in sorted(plan.splits.items()):
        typer.echo(f"- Split '{split}': {count} record(s){' (estimated)' if plan.totals.estimated else ''}")
    if plan.totals.records is not None:
        typer.echo(f"Total: {plan.totals.records} record(s)")

    for finding in plan.report.warnings:
        samples = ", ".join(sample.location() for sample in finding.samples[:_SAMPLE_LIMIT])
        typer.echo(f"- Warning: {finding.code} ({finding.count} occurrence(s); e.g. {samples})")
        if finding.suggestion:
            typer.echo(f"  {finding.suggestion}")
    for finding in plan.report.errors:
        samples = ", ".join(sample.location() for sample in finding.samples[:_SAMPLE_LIMIT])
        typer.echo(f"- Error: {finding.code} ({finding.count} occurrence(s); e.g. {samples})", err=True)
        if finding.suggestion:
            typer.echo(f"  {finding.suggestion}", err=True)


def _build_spec(
    source: Path,
    spec_file: Optional[Path],
    format: str,
    name: str,
    workspace: str,
    mode: str,
    media: Optional[str],
    namespace: Optional[str],
) -> ImportSpec:
    discovered = source / "pixano.yaml" if source.is_dir() else None
    if spec_file is not None:
        spec = ImportSpec.from_yaml(spec_file)
    elif discovered is not None and discovered.is_file():
        spec = ImportSpec.from_yaml(discovered)
    else:
        spec = ImportSpec()

    updates: dict = {}
    if format != "auto" or spec.format == "auto":
        updates["format"] = format
    if mode != spec.mode:
        updates["mode"] = mode
    if media is not None:
        updates["media"] = spec.media.model_copy(update={"mode": media})
    if namespace is not None:
        updates["ids"] = spec.ids.model_copy(update={"namespace": namespace})
    dataset_updates: dict = {}
    if name:
        dataset_updates["name"] = name
    if workspace:
        try:
            dataset_updates["workspace"] = WorkspaceType(workspace)
        except ValueError:
            valid = ", ".join(w.value for w in WorkspaceType)
            raise typer.BadParameter(f"Unknown workspace '{workspace}' (valid: {valid}).") from None
    if dataset_updates:
        updates["dataset"] = spec.dataset.model_copy(update=dataset_updates)
    return spec.model_copy(update=updates) if updates else spec


@data_app.command(name="import")
def import_command(
    data_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Pixano data directory."),
    source: Path = typer.Argument(..., exists=True, help="Source directory to import."),
    format: str = typer.Option("auto", "--format", help="Data format (auto = detect)."),
    spec_file: Optional[Path] = typer.Option(
        None, "--spec", exists=True, dir_okay=False, help="pixano.yaml import spec (default: <source>/pixano.yaml)."
    ),
    name: str = typer.Option("", "--name", help="Target dataset name (overrides the spec)."),
    workspace: str = typer.Option("", "--workspace", help="Workspace preset (image, video, image_vqa, ...)."),
    mode: str = typer.Option("create", "--mode", help="create, overwrite, or add."),
    media: Optional[str] = typer.Option(None, "--media", help="Media storage: embed (default) or uri."),
    namespace: Optional[str] = typer.Option(None, "--namespace", help="Id namespace (default: source identity)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Analyze and print the plan without importing."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the plan confirmation prompt."),
    importer_spec: Optional[str] = typer.Option(
        None, "--importer", help="Advanced: custom importer as 'path/to/file.py:ClassName'."
    ),
    info_py: Optional[str] = typer.Option(
        None, "--info-py", help="Advanced: DatasetInfo as 'path/to/file.py:attribute'."
    ),
) -> None:
    """Import a dataset: analyze, confirm the plan, then ingest atomically."""
    spec = _build_spec(source, spec_file, format, name, workspace, mode, media, namespace)

    importer = None
    if importer_spec is not None:
        from pixano.cli._schema_loader import load_importer

        importer = load_importer(importer_spec)

    info = None
    if info_py is not None:
        from pixano.cli._schema_loader import load_info

        info = load_info(info_py)

    try:
        plan = analyze(source, spec, importer=importer)
    except PixanoDataError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from None

    _render_plan(plan)
    if not plan.report.is_valid:
        typer.echo(f"Analysis found {plan.report.error_count} error(s); nothing was imported.", err=True)
        raise typer.Exit(code=1)
    if dry_run:
        typer.echo("Dry-run completed successfully. No dataset was created.")
        raise typer.Exit(code=0)
    if not yes and not typer.confirm("Proceed with the import?", default=True):
        raise typer.Exit(code=0)

    sink = TqdmSink()
    try:
        result = import_dataset(source, data_dir, spec, plan=plan, info=info, importer=importer, sinks=[sink])
    except PixanoDataError as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from None
    finally:
        sink.close()
    records = result.table_counts.get("records", 0)
    typer.echo(
        f"Dataset '{result.dataset_path.name}' imported successfully "
        f"({records} record(s), storage: {result.storage_mode}, job {result.job_id})."
    )


@data_app.command(name="export")
def export_command(
    data_dir: Path = typer.Argument(..., exists=True, file_okay=False, help="Pixano data directory."),
    dataset: str = typer.Argument(..., help="Dataset name or id in the library."),
    destination: Path = typer.Argument(..., help="Destination directory."),
    format: str = typer.Option("pixano_jsonl", "--format", help="Export format."),
    media: str = typer.Option("files", "--media", help="files (dump embedded bytes) or uris (write URIs verbatim)."),
) -> None:
    """Export a dataset from the library (JSONL v2 output re-imports identically)."""
    library_dir = data_dir / "library"
    dataset_dir = library_dir / to_snake_case(dataset)
    try:
        resolved = Dataset(dataset_dir) if dataset_dir.is_dir() else Dataset.find(dataset, library_dir)
        exported = export_dataset(resolved, destination, format=format, media=media)
    except (PixanoDataError, FileNotFoundError) as error:
        typer.echo(f"Error: {error}", err=True)
        raise typer.Exit(code=1) from None
    typer.echo(f"Dataset '{dataset}' exported to '{exported}'.")


@data_app.command(name="formats")
def formats_command() -> None:
    """List the registered data formats."""
    for data_format in FORMATS:
        directions = "+".join(
            direction
            for direction, available in (("import", data_format.importer_cls), ("export", data_format.exporter_cls))
            if available
        )
        typer.echo(f"- {data_format.name} ({data_format.title}): {directions or 'unavailable'}")
    typer.echo("(pixano_jsonl also exports through 'pixano data export'.)")


@data_app.command(name="migrate-jsonl")
def migrate_jsonl_command(
    source: Path = typer.Argument(..., exists=True, file_okay=False, help="v1 source directory (split folders)."),
    destination: Optional[Path] = typer.Argument(None, help="Output directory (default: <source>_migrated)."),
) -> None:
    """Convert 0.7.x metadata.jsonl files to the JSONL v2 format (best effort)."""
    target = destination if destination is not None else source.with_name(source.name + "_migrated")
    report = migrate_tree(source, target)
    typer.echo(f"Migrated {report.lines_migrated} line(s) across {report.files_migrated} file(s) to '{target}'.")
    typer.echo("Media files are not copied: point the import at the original directory structure or copy them over.")
    for note in report.needs_attention[:20]:
        typer.echo(f"- Needs attention: {note}", err=True)
    if report.needs_attention:
        typer.echo(f"{len(report.needs_attention)} line(s) need manual attention.", err=True)
