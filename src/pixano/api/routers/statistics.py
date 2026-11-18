# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""REST endpoints for statistics: the library's, composed by people, and what a dataset offers to compose."""

import threading
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, ConfigDict, Field

from pixano.api.routers._deps import get_dataset_dep
from pixano.api.settings import Settings, get_settings
from pixano.datasets import Dataset
from pixano.datasets.statistic_choices import DatasetStatisticChoices, choices_for, statistic_applies
from pixano.statistics.computed import ComputedStatistic
from pixano.statistics.definitions import (
    MAX_DESCRIPTION_LENGTH,
    MAX_LABEL_LENGTH,
    StatisticChoices,
    StatisticDefinition,
    define_statistic,
)
from pixano.statistics.registry import StatisticRegistry


# The library's statistics, and what each dataset offers and holds of them.
router = APIRouter(prefix="/statistics", tags=["Statistics"])
dataset_router = APIRouter(prefix="/datasets/{dataset_id}/statistics", tags=["Statistics"])

_registries: dict[str, StatisticRegistry] = {}
# Two first requests at once would each make a registry, and each its own lock on additions.
_registries_lock = threading.Lock()


def get_statistic_registry(settings: Annotated[Settings, Depends(get_settings)]) -> StatisticRegistry:
    """The registry of the library the application serves.

    One per library, kept for the life of the application: the registry serialises the additions
    it receives.

    Args:
        settings: The application's settings, which name the library.

    Returns:
        The library's registry.
    """
    key = str(settings.library_dir)
    with _registries_lock:
        registry = _registries.get(key)
        if registry is None:
            registry = _registries[key] = StatisticRegistry(settings.library_dir)
    return registry


class ComposeStatisticRequest(BaseModel):
    """A statistic a person composes.

    Attributes:
        choices: What it is made of.
        label: What a person reads in place of its name; made from the choices when empty.
        description: What the person writes about it.
    """

    model_config = ConfigDict(extra="forbid")

    choices: StatisticChoices
    label: str = Field(default="", max_length=MAX_LABEL_LENGTH)
    description: str = Field(default="", max_length=MAX_DESCRIPTION_LENGTH)


@router.get(
    "/definitions",
    response_model=list[StatisticDefinition],
    operation_id="list_statistic_definitions",
    summary="List the library's statistics",
    description=(
        "Every statistic people composed in this library that is still computed as it was composed, "
        "per record first, then per object."
    ),
)
def list_statistic_definitions(
    registry: Annotated[StatisticRegistry, Depends(get_statistic_registry)],
) -> list[StatisticDefinition]:
    """Return the library's statistics still computed as they were composed.

    One composed before its measure changed is left out: no job computes it any more, and the same
    choices compose the statistic of the new version.
    """
    return [definition for definition in registry.definitions() if definition.is_current]


@router.post(
    "/definitions",
    response_model=StatisticDefinition,
    status_code=201,
    operation_id="compose_statistic",
    summary="Compose a statistic",
    description=(
        "Add a statistic to the library, composed from fixed choices. Its name, unit and type follow "
        "from them. Composing one the library holds already answers it, as it was stored, with 200."
    ),
)
def compose_statistic(
    request: ComposeStatisticRequest,
    response: Response,
    registry: Annotated[StatisticRegistry, Depends(get_statistic_registry)],
) -> StatisticDefinition:
    """Add a statistic to the library, or return the one already there."""
    stored, added = registry.add(define_statistic(request.choices, request.label, request.description))
    if not added:
        response.status_code = 200
    return stored


@dataset_router.get(
    "",
    response_model=list[ComputedStatistic],
    operation_id="list_dataset_statistics",
    summary="List the statistics a dataset holds the values of",
    description=(
        "Each statistic whose values the dataset holds, as it was composed when they were computed, "
        "with the job that computed them last and when."
    ),
)
def list_dataset_statistics(dataset: Dataset = Depends(get_dataset_dep)) -> list[ComputedStatistic]:
    """Return the statistics the dataset holds the values of."""
    return list(dataset.info.statistics)


@dataset_router.get(
    "/choices",
    response_model=DatasetStatisticChoices,
    operation_id="get_statistic_choices",
    summary="What a dataset offers to compose a statistic from",
    description=(
        "The annotation kinds the dataset holds and how each can be measured, the attributes of its "
        "objects with their values, and the filters on origin and review status."
    ),
)
def get_statistic_choices(dataset: Dataset = Depends(get_dataset_dep)) -> DatasetStatisticChoices:
    """Return what the dataset offers to compose a statistic from."""
    return choices_for(dataset)


@dataset_router.get(
    "/definitions",
    response_model=list[StatisticDefinition],
    operation_id="list_dataset_statistic_definitions",
    summary="List the library's statistics that apply to a dataset",
    description=(
        "The statistics of the library this dataset holds what to compute for, among those still "
        "computed as they were composed."
    ),
)
def list_dataset_statistic_definitions(
    registry: Annotated[StatisticRegistry, Depends(get_statistic_registry)],
    dataset: Dataset = Depends(get_dataset_dep),
) -> list[StatisticDefinition]:
    """Return the library's statistics that apply to the dataset."""
    return [
        definition
        for definition in registry.definitions()
        if definition.is_current and statistic_applies(definition.choices, dataset)
    ]
