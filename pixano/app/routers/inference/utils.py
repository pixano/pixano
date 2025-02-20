# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from fastapi import HTTPException
from pixano_inference.client import PixanoInferenceClient

from pixano.app.settings import Settings


def get_client_from_settings(settings: Settings) -> PixanoInferenceClient:
    """Get the Pixano inference client from the settings."""
    client = settings.pixano_inference_client
    if client is None:
        raise HTTPException(status_code=500, detail="PixanoInferenceClient not set in settings")
    return client
