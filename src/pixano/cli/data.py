# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import re
from enum import Enum
from pathlib import Path

import typer

from pixano.cli._schema_loader import load_info
from pixano.datasets.workspaces import WorkspaceType


class ImportMode(str, Enum):
    """Import modes controlling dataset creation behavior."""

    create = "create"
    overwrite = "overwrite"
    add = "add"


class MetadataValidationMode(str, Enum):
    default = "default"
    strict = "strict"


def _snake_case_name(value: str) -> str:
    snake = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower())
    snake = re.sub(r"_+", "_", snake).strip("_")
    return snake


def _builder_path_for_workspace(workspace: WorkspaceType) -> str:
    builder_map = {
        WorkspaceType.IMAGE: "pixano.datasets.builders.folders.image.ImageFolderBuilder",
        WorkspaceType.VIDEO: "pixano.datasets.builders.folders.video.VideoFolderBuilder",
        WorkspaceType.IMAGE_VQA: "pixano.datasets.builders.folders.vqa.VQAFolderBuilder",
        WorkspaceType.IMAGE_TEXT_ENTITY_LINKING: "pixano.datasets.builders.folders.mel.MelFolderBuilder",
    }
    try:
        return builder_map[workspace]
    except KeyError as exc:
        raise typer.BadParameter(
            f"DatasetInfo.workspace={workspace.value!r} is not supported by pixano data import."
        ) from exc


data_app = typer.Typer(help="Pixano dataset commands.")


@data_app.command(name="import")
def import_data(
    data_dir: Path = typer.Argument(..., exists=True, dir_okay=True, help="Path to data directory."),
    source_dir: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=False,
        dir_okay=True,
        help="Path to source dataset directory containing split folders.",
    ),
    info_spec: str = typer.Option(
        ...,
        "--info",
        help=(
            "DatasetInfo in 'path/to/file.py:attribute' format. "
            "Folder import requires it as the dataset specification source of truth."
        ),
    ),
    mode: ImportMode = typer.Option(ImportMode.create, help="Import mode: create, overwrite, or add."),
    metadata_validation: MetadataValidationMode = typer.Option(
        MetadataValidationMode.default,
        "--metadata-validation",
        help="Metadata validation mode: default or strict.",
    ),
    dry_run: bool = typer.Option(False, "--dry-run", help="Validate metadata and exit without importing."),
    use_image_name_as_id: bool = typer.Option(False, help="Use image file name as record ID."),
) -> None:
    """Import a dataset from an external source directory.

    Reads media from SOURCE_DIR and embeds it directly in the LanceDB database.
    """
    info = load_info(info_spec)
    if not info.name.strip():
        raise typer.BadParameter("DatasetInfo.name must be set. It is used to derive the target dataset folder name.")
    if info.workspace == WorkspaceType.UNDEFINED:
        raise typer.BadParameter("DatasetInfo.workspace must be set for folder import.")

    dataset_name = _snake_case_name(info.name)
    if not dataset_name:
        raise typer.BadParameter("DatasetInfo.name must contain at least one alphanumeric character.")

    resolved_library_dir = data_dir / "library"

    # Resolve builder class
    import importlib

    module_path, class_name = _builder_path_for_workspace(info.workspace).rsplit(".", 1)
    module = importlib.import_module(module_path)
    builder_cls = getattr(module, class_name)

    resolved_library_dir.mkdir(parents=True, exist_ok=True)
    target_dir = resolved_library_dir / dataset_name
    if mode == ImportMode.create and target_dir.exists():
        typer.echo(
            f"Error: Dataset '{dataset_name}' already exists at '{target_dir}'. Use --mode overwrite or --mode add.",
            err=True,
        )
        raise typer.Exit(code=1)

    builder = builder_cls(
        source_dir=source_dir,
        library_dir=resolved_library_dir,
        info=info,
        metadata_validation_mode=metadata_validation.value,
        use_image_name_as_id=use_image_name_as_id,
        target_name=dataset_name,
    )

    report = builder.preflight_metadata(metadata_validation.value)
    typer.echo(f"Metadata validation passed with {report.warning_count} warnings")
    if report.normalized_examples:
        for example in report.normalized_examples:
            typer.echo(f"- Mapping: {example}")
    if report.aliases:
        for alias, aggregate in sorted(report.aliases.items()):
            samples = ", ".join(aggregate.samples)
            typer.echo(f"- Alias applied: {alias} ({aggregate.count} rows; e.g. {samples})")
    if report.inferred:
        for inferred, aggregate in sorted(report.inferred.items()):
            samples = ", ".join(aggregate.samples)
            typer.echo(f"- Inferred mapping: {inferred} ({aggregate.count} rows; e.g. {samples})")
    if report.errors:
        for code, aggregate in sorted(report.errors.items()):
            samples = ", ".join(aggregate.samples)
            typer.echo(f"- Error: {code} ({aggregate.count} rows; e.g. {samples})", err=True)
        raise typer.Exit(code=1)
    if dry_run:
        typer.echo("Dry-run completed successfully. No dataset was created.")
        raise typer.Exit(code=0)

    dataset = builder.build(mode=mode.value)
    typer.echo(f"Dataset '{dataset_name}' built successfully ({dataset.num_rows} records).")
