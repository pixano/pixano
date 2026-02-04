# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import importlib.util
from pathlib import Path

import typer

from pixano.datasets.dataset_schema import DatasetItem


def load_schema(specifier: str) -> type[DatasetItem]:
    """Load a DatasetItem subclass from a ``path/to/file.py:ClassName`` specifier.

    Args:
        specifier: String in the format ``path/to/file.py:ClassName``.

    Returns:
        The loaded DatasetItem subclass.

    Raises:
        typer.BadParameter: If the specifier format is invalid, the file
            cannot be loaded, the class is not found, or the class is not
            a DatasetItem subclass.
    """
    if ":" not in specifier:
        raise typer.BadParameter(f"Schema must be in 'path/to/file.py:ClassName' format, got '{specifier}'")

    file_path_str, class_name = specifier.rsplit(":", 1)
    file_path = Path(file_path_str).resolve()

    if not file_path.is_file():
        raise typer.BadParameter(f"Schema file not found: {file_path}")

    spec = importlib.util.spec_from_file_location("_user_schema", file_path)
    if spec is None or spec.loader is None:
        raise typer.BadParameter(f"Cannot load module from: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cls = getattr(module, class_name, None)
    if cls is None:
        raise typer.BadParameter(f"Class '{class_name}' not found in {file_path}")

    if not (isinstance(cls, type) and issubclass(cls, DatasetItem)):
        raise typer.BadParameter(f"'{class_name}' is not a DatasetItem subclass")

    return cls
