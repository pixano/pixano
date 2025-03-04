# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import shortuuid
from fastapi import HTTPException
from pixano_inference.client import PixanoInferenceClient

from pixano.app.settings import Settings
from pixano.datasets import Dataset
from pixano.features import Source


def get_client_from_settings(settings: Settings) -> PixanoInferenceClient:
    """Get the Pixano inference client from the settings."""
    client = settings.pixano_inference_client
    if client is None:
        raise HTTPException(status_code=500, detail="PixanoInferenceClient not set in settings")
    return client


def get_model_source(dataset: Dataset, model: str):
    """Get the model's source from a given Dataset and Model.

    If it exists in the database already it returns that one otherwise creates a new instance.
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
