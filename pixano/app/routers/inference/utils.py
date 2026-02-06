# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shortuuid
from fastapi import HTTPException

from pixano.app.settings import Settings
from pixano.datasets import Dataset
from pixano.features import Source
from pixano.inference import InferenceProvider


def get_provider_from_settings(settings: Settings, provider_name: str | None = None) -> InferenceProvider:
    """Get an inference provider from the settings.

    Args:
        settings: App settings.
        provider_name: Name of the provider to get. If None, uses the default provider.

    Returns:
        The requested InferenceProvider.

    Raises:
        HTTPException: If no provider is connected or the requested provider is not found.
    """
    if not settings.inference_providers:
        raise HTTPException(status_code=500, detail="No inference provider connected")

    if provider_name is None:
        provider_name = settings.default_inference_provider

    if provider_name is None or provider_name not in settings.inference_providers:
        raise HTTPException(
            status_code=500,
            detail=f"Inference provider '{provider_name}' not found. Connected providers: "
            f"{list(settings.inference_providers.keys())}",
        )

    return settings.inference_providers[provider_name]


def get_model_source(dataset: Dataset, model: str) -> Source:
    """Get the model's source from a given Dataset and Model.

    If it exists in the database already it returns that one otherwise creates a new instance.

    Args:
        dataset: The dataset to get/create the source in.
        model: The model name.

    Returns:
        The Source object for the model.

    Raises:
        HTTPException: If multiple sources exist for the same model.
    """
    sources: list[Source] = dataset.get_data(table_name="source", limit=2, where=f"name='{model}' AND kind='model'")
    # TODO: enforce check consistency for source to have a unique name instead of checking here.
    if len(sources) > 1:
        raise HTTPException(status_code=400, detail="Only one source for model is allowed.")
    elif len(sources) == 0:
        source = Source(id=shortuuid.uuid(), name=model, kind="model")
        dataset.add_data("source", data=[source])
    else:
        source = sources[0]
    return source
