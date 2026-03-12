# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os
import re
from collections import OrderedDict
from pathlib import Path
from typing import Any, Sequence


def natural_key(string: str) -> list:
    """Return key for string natural sort.

    Args:
        string: Input string.

    Returns:
        Sort key.
    """
    return [int(s) if s.isdecimal() else s for s in re.split(r"(\d+)", string)]


def estimate_folder_size(folder_path: Path) -> str:
    """Estimate a folder size and return it as a human-readable string.

    Args:
        folder_path: Folder path.

    Returns:
        Folder size as a human-readable string.
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


def get_super_type_from_dict(sub_type: type, dict_types: dict[str, type]) -> type | None:
    """Get the first super type in a dictionary of types for the given type.

    Args:
        sub_type: Sub type to find the super type for.
        dict_types: Dictionary of types.

    Returns:
        Super type if found, None otherwise.
    """
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


def to_sql_list(ids: str | Sequence[str] | set[str]) -> str:
    """Convert a list of IDs to a SQL-friendly string.

    Args:
        ids: List of IDs.

    Returns:
        SQL-friendly string of IDs.
    """
    if isinstance(ids, str):
        return f"('{ids}')"
    elif len(ids) == 0:
        raise ValueError("IDs must not be empty.")
    else:
        for id in ids:
            if not isinstance(id, str):
                raise ValueError("IDs must be strings.")
    ids = list(dict.fromkeys(ids))  # Keep order and remove duplicates
    if len(ids) == 1:
        return f"('{ids.pop()}')"
    return str(tuple(ids))


def fn_sort_dict(dict_: dict[str, Any], order_by: list[str], descending: list[bool]) -> tuple[Any, ...]:
    """Function to sort a dictionary by multiple keys in different orders.

    Args:
        dict_: Dictionary to sort.
        order_by: List of keys to sort by.
        descending: List of booleans indicating the order for each key.
    """
    key: list[Any] = []
    for col, desc in zip(order_by, descending, strict=True):
        value = dict_.get(col)
        if desc:
            if isinstance(value, (int, float)):
                key.append(-value)
            elif isinstance(value, str):
                key.append("".join(chr(255 - ord(c)) for c in value))
            elif value is bool:
                key.append(not value)
            elif value is None:
                key.append(None)
            else:
                raise ValueError(
                    f"Cannot sort by {type(value)} in descending order. "
                    "Please use open an issue if you need this feature."
                )
        else:
            key.append(value)
    return tuple(key)


def unique_list(sequence: Sequence[Any]) -> list[Any]:
    """Select unique elements in a list while keeping order.

    Args:
        sequence: Input sequence.

    Returns:
        List of unique elements.
    """
    return list(OrderedDict.fromkeys(sequence))
