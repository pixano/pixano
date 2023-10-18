# @Copyright: CEA-LIST/DIASI/SIALV/LVA (2023)
# @Author: CEA-LIST/DIASI/SIALV/LVA <pixano@cea.fr>
# @License: CECILL-C
#
# This software is a collaborative computer program whose purpose is to
# generate and explore labeled data for computer vision applications.
# This software is governed by the CeCILL-C license under French law and
# abiding by the rules of distribution of free software. You can use,
# modify and/ or redistribute the software under the terms of the CeCILL-C
# license as circulated by CEA, CNRS and INRIA at the following URL
#
# http://www.cecill.info

import os
import re
from pathlib import Path


def natural_key(string: str) -> list:
    """Return key for string natural sort

    Args:
        string (str): Input string

    Returns:
        list: Sort key
    """

    return [int(s) if s.isdecimal() else s for s in re.split(r"(\d+)", string)]


def estimate_size(folder_path: Path) -> str:
    """Estimate folder size and return it as a human-readable string

    Args:
        folder_path (Path): Folder path

    Returns:
        str: Folder size as a human-readable string
    """

    # Estimate size
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(folder_path):
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
    f = ("%.2f" % total_size).rstrip("0").rstrip(".")
    readable_size = "%s %s" % (f, suffixes[i])

    return readable_size
