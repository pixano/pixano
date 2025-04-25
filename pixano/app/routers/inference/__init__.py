# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pixano_inference.client import PixanoInferenceClient

from pixano.app.settings import Settings, get_settings

from . import conditional_generation, mask_generation, models, zero_shot_detection


router = APIRouter(prefix="/inference", tags=["Inference"])
router.include_router(conditional_generation.router)
router.include_router(models.router)
router.include_router(zero_shot_detection.router)
router.include_router(mask_generation.router)


@router.post("/connect")
async def connect_inference(url: str, settings: Annotated[Settings, Depends(get_settings)]) -> None:
    """Connect to Pixano Inference."""
    try:
        client = PixanoInferenceClient.connect(url)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Impossible to connect to Pixano Inference from url: {url}")

    settings.pixano_inference_client = client
    return


__all__ = ["router"]
