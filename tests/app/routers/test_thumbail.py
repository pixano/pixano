# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import base64
from pathlib import Path

from fastapi.applications import FastAPI
from fastapi.testclient import TestClient

from pixano.app.settings import Settings
from tests.assets.sample_data.metadata import IMAGE_JPG_ASSET_URL


def test_get_thumbnail(app_and_settings_with_client: tuple[FastAPI, Settings, TestClient]):
    app, settings, client = app_and_settings_with_client

    # copy image in media_dir
    basename = Path(IMAGE_JPG_ASSET_URL).name
    encoded_basename = base64.b64encode(basename.encode("utf-8")).decode("utf-8")
    max_size = 128

    # url = app.url_path_for('get_thumbnail', b64_image_path=encoded_basename )
    response = client.get(f"/thumbnail/{encoded_basename}?max_size={max_size}")
    assert response.status_code == 200
    assert response.headers["content-Type"] == "image/jpeg"
    # assert response.content == ??

    response = client.get(f"/thumbnail/{encoded_basename}?max_size={2000}")
    assert response.status_code == 200

    response = client.get(f"/thumbnail/abcd123456?max_size={max_size}")
    assert response.status_code == 400
    assert response.json() == {"detail": "Unable to decode the image path."}

    encoded_basename = base64.b64encode("missing_image.jpg".encode("utf-8")).decode("utf-8")
    response = client.get(f"/thumbnail/{encoded_basename}?max_size={max_size}")
    assert response.status_code == 404
    assert response.json() == {"detail": "Requested image cannot be found."}
