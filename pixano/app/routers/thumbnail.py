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


@router.get("/embedded/{dataset_id}/{view_name}/{row_id}", name="get_embedded_thumbnail")
def get_embedded_thumbnail(
    dataset_id: str,
    view_name: str,
    row_id: str,
    settings: Annotated[Settings, Depends(get_settings)],
    max_size: PositiveInt = 128,
) -> FileResponse:
    """Generate a thumbnail from an embedded blob.

    Args:
        dataset_id: Dataset ID.
        view_name: View name (column prefix in media-type table).
        row_id: Row ID in the media-type table.
        settings: App settings.
        max_size: Maximum thumbnail dimension.

    Returns:
        FileResponse with the generated thumbnail.
    """
    from pixano.datasets.queries import TableQueryBuilder

    # Check disk cache first
    cache_key = hashlib.md5(f"emb_{dataset_id}_{view_name}_{row_id}_{max_size}".encode()).hexdigest()
    cache_path = THUMBNAIL_CACHE_DIR / f"{cache_key}.jpg"

    if cache_path.exists():
        return FileResponse(
            cache_path,
            media_type="image/jpeg",
            headers={"Cache-Control": "public, max-age=86400", "ETag": cache_key},
        )

    # Fetch blob from dataset
    from pixano.app.routers.utils import get_dataset

    dataset = get_dataset(dataset_id, settings.library_dir, settings.media_dir)

    if view_name not in dataset.schema.view_columns:
        raise HTTPException(status_code=404, detail=f"View '{view_name}' not found in dataset schema.")

    vc = dataset.schema.view_columns[view_name]
    table = dataset.open_table(vc.media_table)

    rows = (
        TableQueryBuilder(table, dataset._db_connection)
        .select(["id", view_name])
        .where(f"id = '{row_id}'")
        .to_list()
    )

    if not rows:
        raise HTTPException(status_code=404, detail=f"Row '{row_id}' not found.")

    blob = rows[0].get(view_name, b"")
    if not blob:
        raise HTTPException(status_code=404, detail="No blob data found for this view.")

    # Generate thumbnail
    import io

    image = Image.open(io.BytesIO(blob))
    if max_size > max(image.width, image.height):
        max_size = max(image.width, image.height)
    image.thumbnail((max_size, max_size))
    image.convert("RGB").save(cache_path, format="JPEG", quality=85)

    return FileResponse(
        cache_path,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=86400", "ETag": cache_key},
    )
