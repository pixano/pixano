# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import typer


def init(
    data_dir: Path = typer.Argument(..., help="Path to initialize."),
) -> None:
    """Initialize a Pixano data directory."""
    for subdir in ["library", "media", "models"]:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)
    typer.echo(f"Initialized Pixano data directory at {data_dir}")
