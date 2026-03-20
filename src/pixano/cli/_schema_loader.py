# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import importlib.util
from pathlib import Path

import typer

from pixano.datasets.dataset_info import DatasetInfo


def load_info(specifier: str) -> DatasetInfo:
    """Load a ``DatasetInfo`` object from a ``path/to/file.py:attribute`` specifier.

    Args:
        specifier: String in the format ``path/to/file.py:attribute``.

    Returns:
        A deep copy of the loaded ``DatasetInfo`` instance.

    Raises:
        typer.BadParameter: If the specifier format is invalid, the file
            cannot be loaded, the attribute is not found, or the attribute is
            not a ``DatasetInfo`` instance.
    """
    if ":" not in specifier:
        raise typer.BadParameter(f"Info must be in 'path/to/file.py:attribute' format, got '{specifier}'")

    file_path_str, attribute_name = specifier.rsplit(":", 1)
    file_path = Path(file_path_str).resolve()

    if not file_path.is_file():
        raise typer.BadParameter(f"Info file not found: {file_path}")

    spec = importlib.util.spec_from_file_location("_user_schema", file_path)
    if spec is None or spec.loader is None:
        raise typer.BadParameter(f"Cannot load module from: {file_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    value = getattr(module, attribute_name, None)
    if value is None:
        raise typer.BadParameter(f"Attribute '{attribute_name}' not found in {file_path}")

    if isinstance(value, DatasetInfo):
        return value.model_copy(deep=True)

    if isinstance(value, type) and issubclass(value, DatasetInfo):
        return value().model_copy(deep=True)

    raise typer.BadParameter(f"'{attribute_name}' is not a DatasetInfo instance")
