# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Shared dependencies for API routers."""

from pathlib import Path
from typing import Annotated

from fastapi import Depends, HTTPException, Query

from pixano.api.settings import Settings, get_settings
from pixano.datasets import Dataset


# Dataset cache (reuses the same pattern as v1 utils.py)
_dataset_cache: dict[str, Dataset] = {}


def get_dataset_dep(
    dataset_id: str,
    settings: Settings = Depends(get_settings),
) -> Dataset:
    """FastAPI dependency to get a dataset by ID.

    Args:
        dataset_id: Dataset ID from the URL path.
        settings: App settings.

    Returns:
        The dataset.
    """
    cache_key = f"{dataset_id}:{settings.library_dir}"
    if cache_key in _dataset_cache:
        return _dataset_cache[cache_key]
    try:
        dataset = Dataset.find(dataset_id, settings.library_dir)
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=f"Dataset '{dataset_id}' not found.",
        )
    _dataset_cache[cache_key] = dataset
    return dataset


class PaginationParams:
    """Pagination query parameters.

    Attributes:
        limit: Maximum resources per page (1-1000, default 100).
        offset: Number of resources to skip (default 0).
    """

    def __init__(
        self,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        self.limit = limit
        self.offset = offset


class FilterParams:
    """Common filter query parameters.

    Attributes:
        record_id: Filter by record ID.
        entity_id: Filter by entity ID.
        view_name: Filter by view name.
        source_type: Filter by source type.
        tracklet_id: Filter by tracklet ID.
        frame_index: Filter by frame index.
        where: Custom SQL where clause.
    """

    def __init__(
        self,
        record_id: str | None = None,
        entity_id: str | None = None,
        view_name: str | None = None,
        source_type: str | None = None,
        tracklet_id: str | None = None,
        frame_index: int | None = None,
        where: str | None = None,
    ):
        self.record_id = record_id
        self.entity_id = entity_id
        self.view_name = view_name
        self.source_type = source_type
        self.tracklet_id = tracklet_id
        self.frame_index = frame_index
        self.where = where
