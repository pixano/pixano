# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import base64
from io import BytesIO
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from PIL import Image
from pydantic import PositiveInt

from pixano.app.settings import Settings, get_settings


router = APIRouter(prefix="/thumbnail", tags=["Thumbnail"])


@router.get("/{b64_image_path}", name="get_thumbnail")
async def get_thumbnail(
    b64_image_path: str,
    settings: Annotated[Settings, Depends(get_settings)],
    max_size: PositiveInt = 128,
) -> StreamingResponse:
    """Generates a thumbnail for image found in media dir.

    Args:
        b64_image_path: image identifier in the media directory
        settings: App settings.
        max_size: maximal resolution of the image

    Returns:
        StreamingResponse
    """
    try:
        image_path = base64.b64decode(b64_image_path).decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to decode the image path.")

    try:
        image = Image.open(settings.media_dir / Path(image_path))  # ou depuis la DB, autre source…
    except Exception:
        raise HTTPException(status_code=404, detail="Requested image not found.")

    media_type = image.get_format_mimetype()
    image_format = image.format
    if max_size > max(image.width, image.height):
        max_size = max(image.width, image.height)
    image.thumbnail((max_size, max_size))  # génère le thumbnail

    buf = BytesIO()
    image.save(buf, format=image_format)
    buf.seek(0)
    return StreamingResponse(buf, media_type=media_type)
