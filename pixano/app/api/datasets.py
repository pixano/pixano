# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from pixano.app.settings import Settings, get_settings
from pixano.datasets import Dataset, DatasetLibrary


router = APIRouter(tags=["datasets"])


@router.get("/datasets", response_model=list[DatasetLibrary])
async def get_datasets(
    settings: Annotated[Settings, Depends(get_settings)],
) -> list[DatasetLibrary]:
    """Load dataset list.

    Args:
        settings (Settings): App settings

    Returns:
        list[DatasetInfo]: List of dataset infos
    """
    # Load datasets
    infos = DatasetLibrary.load_directory(
        directory=settings.data_dir, load_thumbnail=True
    )

    # Return datasets
    if infos:
        return infos
    raise HTTPException(
        status_code=404,
        detail=f"No datasets found in {settings.data_dir.absolute()}",
    )


####### why do we need this one ?? should be removed ? ################
@router.get("/datasets/{ds_id}", response_model=DatasetLibrary)
async def get_dataset(
    ds_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> DatasetLibrary:
    """Load dataset.

    **!!! UNUSED ? !!!**

    Args:
        ds_id (str): Dataset ID
        settings (Settings): App settings

    Returns:
        DatasetLibrary: Dataset library info
    """
    # Load dataset
    dataset = Dataset.find(ds_id, settings.data_dir)

    # Return dataset info
    if dataset:
        # return dataset.load_info(load_stats=True, load_features_values=True)
        ### TMP missing stats and features_values
        tables = DatasetLibrary.tables_from_schema(dataset.dataset_schema)
        legacy_info = {
            "id": dataset.info.id,
            "name": dataset.info.name,
            "description": dataset.info.description,
            "estimated_size": dataset.info.size,
            "num_elements": dataset.info.num_elements,
            "preview": "",
            "tables": tables,
        }
        return legacy_info
    raise HTTPException(
        status_code=404,
        detail=f"Dataset {ds_id} not found in {settings.data_dir.absolute()}",
    )
