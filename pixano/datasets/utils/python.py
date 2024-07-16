# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os
import re
from pathlib import Path


def natural_key(string: str) -> list:
    """Return key for string natural sort.

    Args:
        string (str): Input string

    Returns:
        list: Sort key
    """
    return [int(s) if s.isdecimal() else s for s in re.split(r"(\d+)", string)]


def estimate_folder_size(folder_path: Path) -> str:
    """Estimate folder size and return it as a human-readable string.

    Args:
        folder_path (Path): Folder path

    Returns:
        str: Folder size as a human-readable string
    """
    # Estimate size
    total_size = 0.0
    for dirpath, _, filenames in os.walk(folder_path):
        for f in filenames:
            fp = os.path.join(dirpath, f)
            # skip if it is symbolic link
            if not os.path.islink(fp):
                total_size += os.path.getsize(fp)

    # Format size
    i = 0
    suffixes = ["B", "KB", "MB", "GB", "TB", "PB"]
    while total_size >= 1024 and i < len(suffixes) - 1:
        total_size /= 1024.0
        i += 1
    f = (f"{total_size:.2f}").rstrip("0").rstrip(".")
    readable_size = f"{f} {suffixes[i]}"

    return readable_size


def issubclass_strict(obj: type, cls: type, strict: bool = False) -> bool:
    """Check if the given object is of the given class type or a subclass of the given class type.

    Args:
        obj (type): The object to check.
        cls (type): The class to compare against.
        strict (bool, optional): If True, the object must be of the given class type.

    Returns:
        bool: True if the object is of the given class type or a subclass of the given class type.
    """
    if strict:
        return obj == cls
    return issubclass(obj, cls)


def get_super_type_from_dict(sub_type: type, dict_types: dict[str, type]) -> type | None:
    """Get the first super type in a dictionary of types from type."""
    if sub_type in dict_types.values():
        return sub_type

    sup_type = None
    for dict_type in dict_types.values():
        if issubclass(sub_type, dict_type):
            sup_type = dict_type
            break

    if sup_type is None:
        return None

    found_type = True
    while found_type:
        found_type = False
        for dict_type in dict_types.values():
            if issubclass(sub_type, dict_type) and issubclass(dict_type, sup_type) and dict_type is not sup_type:
                sup_type = dict_type
                found_type = True
                break

    return sup_type
