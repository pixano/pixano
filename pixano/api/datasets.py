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

import json
from pathlib import Path

from pydantic import BaseSettings

from pixano.core import Image
from pixano.data import Dataset, DatasetInfo


class Settings(BaseSettings):
    """Dataset library settings

    Attributes:
        data_dir (Path): Dataset library directory
    """

    data_dir: Path = Path.cwd() / "library"


def load_dataset_list(settings: Settings) -> list[DatasetInfo]:
    """Load all dataset info files in library

    Args:
        settings (Settings): Dataset library settings

    Returns:
        list[DatasetInfo]: Dataset info files
    """

    infos = []
    for json_file in sorted(settings.data_dir.glob("*/db.json")):
        # Load dataset info
        info = DatasetInfo.parse_file(json_file)
        # Load thumbnail
        preview_path = json_file.parent / "preview.png"
        if preview_path.is_file():
            im = Image(uri=preview_path.absolute().as_uri())
            info.preview = im.url
        # Load categories
        info.categories = getattr(info, "categories", [])
        if info.categories is None:
            info.categories = []
        # Save dataset info
        infos.append(info)
    return infos


def load_dataset(ds_id: str, settings: Settings) -> Dataset:
    """Load dataset based on its ID

    Args:
        ds_id (str): Dataset ID
        settings (Settings): Dataset library

    Returns:
        Dataset: Dataset
    """

    for json_file in settings.data_dir.glob("*/db.json"):
        info = DatasetInfo.parse_file(json_file)
        if ds_id == info.id:
            return Dataset(json_file.parent)


def load_dataset_stats(ds: Dataset, settings: Settings) -> dict:
    """Load dataset stats based on its ID

    Args:
        ds (Dataset): Dataset
        settings (Settings): Dataset Library

    Returns:
        list[dict]: Dataset stats
    """

    stats_file = ds.path / "stats.json"
    if stats_file.is_file():
        with open(stats_file, "r", encoding="utf-8") as f:
            return json.load(f)
