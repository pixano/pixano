# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What the interface needs to know about the UIs this deployment exposes."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from pixano.api.settings import Settings, get_settings


router = APIRouter(prefix="/app", tags=["App"])


class UIOptionsResponse(BaseModel):
    """Which UIs the deployment exposes.

    Attributes:
        new_ui_enabled: Whether the v1.0 workspace UI can be reached. The legacy UI shows its
            button that switches to the new one only when it is.
    """

    new_ui_enabled: bool


@router.get("/ui", response_model=UIOptionsResponse, operation_id="get_ui_options")
def get_ui_options(settings: Annotated[Settings, Depends(get_settings)]) -> UIOptionsResponse:
    """Tell the interface which UIs this deployment exposes."""
    return UIOptionsResponse(new_ui_enabled=settings.activate_ui_v1_0)
