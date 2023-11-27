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

from functools import lru_cache

from fastapi import APIRouter, HTTPException

from pixano.data import Dataset, DatasetInfo, Settings

# TMP: Mock data
from .mock_data import datasets

router = APIRouter(tags=["datasets"])


@lru_cache
def get_settings():
    """Get app settings

    Returns:
        Settings: App settings
    """

    return Settings()


@router.get("/datasets", response_model=list[DatasetInfo])
async def get_datasets() -> list[DatasetInfo]:
    """Load dataset list

    Returns:
        list[DatasetInfo]: List of dataset infos
    """

    # TMP: Mock data
    if len(datasets) > 0:
        return list(datasets.values())
    else:
        raise HTTPException(status_code=404, detail="No dataset found")

    # # Load datasets
    # infos = DatasetInfo.load_directory(
    #     directory=get_settings().data_dir,
    #     load_thumbnail=True,
    # )

    # # Return datasets
    # if infos:
    #     return infos
    # else:
    #     raise HTTPException(status_code=404, detail="No dataset found")


@router.get("/datasets/{ds_id}", response_model=DatasetInfo)
async def get_dataset(ds_id: str) -> DatasetInfo:
    """Load dataset

    Args:
        ds_id (str): Dataset ID

    Returns:
        DatasetInfo: Dataset info
    """

    # TMP: Mock data
    if ds_id in datasets:
        return datasets[ds_id]
    else:
        raise HTTPException(status_code=404, detail="Dataset not found")

    # # Load dataset
    # dataset = Dataset.find(
    #     id=ds_id,
    #     directory=get_settings().data_dir,
    # )

    # # Return dataset info
    # if dataset:
    #     return dataset.load_info(load_stats=True)
    # else:
    #     raise HTTPException(status_code=404, detail="Dataset not found")
