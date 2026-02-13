# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import base64
import hashlib
import tempfile
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from PIL import Image
from pydantic import PositiveInt

from pixano.app.settings import Settings, get_settings


router = APIRouter(prefix="/thumbnail", tags=["Thumbnail"])

THUMBNAIL_CACHE_DIR = Path(tempfile.gettempdir()) / "pixano_thumbnails"
THUMBNAIL_CACHE_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/{b64_image_path}", name="get_thumbnail")
def get_thumbnail(
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
        StreamingResponse or FileResponse
    """
    try:
        image_path = base64.b64decode(b64_image_path).decode("utf-8")
    except Exception:
        raise HTTPException(status_code=400, detail="Unable to decode the image path.")

    # Check disk cache first
    cache_key = hashlib.md5(f"{image_path}_{max_size}".encode()).hexdigest()
    cache_path = THUMBNAIL_CACHE_DIR / f"{cache_key}.jpg"

    if cache_path.exists():
        return FileResponse(
            cache_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400", "ETag": cache_key},
        )

    # Generate thumbnail
    try:
        image = Image.open(settings.media_dir / Path(image_path))
    except Exception:
        raise HTTPException(status_code=404, detail="Requested image cannot be found.")

    if max_size > max(image.width, image.height):
        max_size = max(image.width, image.height)
    image.thumbnail((max_size, max_size))

    # Save to disk cache as JPEG
    image.convert("RGB").save(cache_path, format="JPEG", quality=85)

    return FileResponse(
        cache_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400", "ETag": cache_key},
    )
