# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path
from importlib import resources
import shutil

import typer


def init(
) -> None:
    """Initialize a Pixano data directory."""
    data_dir = Path('./my_data')
    template_dir = Path('./examples')
    for subdir in ["library", "media", "models"]:
        (data_dir / subdir).mkdir(parents=True, exist_ok=True)
    typer.echo(f"Initialized Pixano data directory at {data_dir}")

    copy_template(template_dir)

def copy_template(target_dir: str):
    with resources.path("pixano", "examples") as template_path:
        
        if target_dir.exists():
            return

        shutil.copytree(template_path, target_dir)
