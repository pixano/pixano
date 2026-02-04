# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shutil
from enum import Enum
from pathlib import Path
from typing import Optional

import typer

from pixano.app.cli._schema_loader import load_schema


class DatasetType(str, Enum):
    """Supported dataset types for folder-based import."""

    image = "image"
    video = "video"
    vqa = "vqa"


class ImportMode(str, Enum):
    """Import modes controlling dataset creation behavior."""

    create = "create"
    overwrite = "overwrite"
    add = "add"


data_app = typer.Typer(help="Pixano data commands.")


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
    name: Optional[str] = typer.Option(None, help="Dataset name. Defaults to source directory name."),
    description: str = typer.Option("", help="Dataset description."),
    type: DatasetType = typer.Option(DatasetType.image, help="Dataset type: image, video, or vqa."),
    schema: Optional[str] = typer.Option(
        None,
        help="Custom schema in 'path/to/file.py:ClassName' format. Uses the default schema for the type if omitted.",
    ),
    mode: ImportMode = typer.Option(ImportMode.create, help="Import mode: create, overwrite, or add."),
    use_image_name_as_id: bool = typer.Option(False, help="Use image file name as item ID."),
) -> None:
    """Import a dataset from an external source directory.

    Copies media from SOURCE_DIR into data_dir/media/<dataset_name>/ and builds the dataset.
    """
    from pixano.datasets import DatasetInfo

    builder_map = {
        DatasetType.image: "pixano.datasets.builders.folders.image.ImageFolderBuilder",
        DatasetType.video: "pixano.datasets.builders.folders.video.VideoFolderBuilder",
        DatasetType.vqa: "pixano.datasets.builders.folders.vqa.VQAFolderBuilder",
    }

    # Resolve dataset name
    dataset_name = name if name is not None else source_dir.name

    # Derive library_dir and media_dir from data_dir
    resolved_library_dir = data_dir / "library"
    resolved_media_dir = data_dir / "media"

    # Copy media from source_dir into data_dir/media/<dataset_name>/
    dest_media = resolved_media_dir / dataset_name

    if mode == ImportMode.create:
        if dest_media.exists():
            typer.echo(f"Error: '{dest_media}' already exists. Use --mode overwrite or --mode add.", err=True)
            raise typer.Exit(code=1)
        dest_media.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, dest_media)
    elif mode == ImportMode.overwrite:
        if dest_media.exists():
            shutil.rmtree(dest_media)
        dest_media.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, dest_media)
    elif mode == ImportMode.add:
        dest_media.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(source_dir, dest_media, dirs_exist_ok=True)

    typer.echo(f"Copied media from '{source_dir}' to '{dest_media}'.")

    # Resolve builder class
    import importlib

    module_path, class_name = builder_map[type].rsplit(".", 1)
    module = importlib.import_module(module_path)
    builder_cls = getattr(module, class_name)

    # Resolve schema
    dataset_item = None
    if schema is not None:
        dataset_item = load_schema(schema)

    info = DatasetInfo(name=dataset_name, description=description)

    builder = builder_cls(
        media_dir=resolved_media_dir,
        library_dir=resolved_library_dir,
        dataset_item=dataset_item,
        info=info,
        dataset_path=dataset_name,
        use_image_name_as_id=use_image_name_as_id,
    )

    dataset = builder.build(mode=mode.value)
    typer.echo(f"Dataset '{dataset_name}' built successfully ({dataset.num_rows} items).")
