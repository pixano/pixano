# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests for resizable view previews (`?size=`) and text-excerpt view previews."""

import io
import tempfile
from functools import lru_cache
from pathlib import Path

import PIL.Image
import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.features import Image, Record, Text


DATASET_ID = "preview_resize_dataset"
BASE = f"/datasets/{DATASET_ID}"

TEXT_CONTENT = "lorem ipsum " * 40  # 480 chars → excerpt must truncate at 160


def _png_bytes(width: int, height: int) -> bytes:
    buffer = io.BytesIO()
    PIL.Image.new("RGB", (width, height), color=(30, 90, 200)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture(scope="module")
def client() -> TestClient:
    tmp = Path(tempfile.mkdtemp())
    target = tmp / "library" / DATASET_ID
    dataset = Dataset.create(
        target,
        DatasetInfo(
            id=DATASET_ID,
            name=DATASET_ID,
            description="d",
            record=Record,
            views={"image": Image, "text": Text},
        ),
    )
    records = [Record(id=f"r{i}") for i in range(4)]
    # r0: embedded image with a real full-resolution blob (800x600).
    embedded = Image.from_bytes(record_id="r0", logical_name="image", raw_bytes=_png_bytes(800, 600), id="img_full")
    # r1: image carrying only a stored preview (no raw_bytes) — resize must fall back.
    preview_only = Image(
        id="img_preview_only",
        record_id="r1",
        logical_name="image",
        uri="r1.jpg",
        width=64,
        height=64,
        format="png",
        preview=_png_bytes(64, 64),
        preview_format="png",
    )
    # r2: datalake image — the raw remote URL must pass through untouched.
    datalake = Image(
        id="img_remote",
        record_id="r2",
        logical_name="image",
        uri="https://datalake.example.com/r2.jpg",
        width=640,
        height=480,
        format="jpg",
    )
    # r3: text-only record — the card gets an excerpt, no thumbnail.
    text = Text(id="txt_0", record_id="r3", logical_name="text", content=TEXT_CONTENT)

    dataset.add_records({"records": records, "images": [embedded, preview_only, datalake], "texts": [text]})

    models_dir = tmp / "models"
    models_dir.mkdir()
    settings = Settings(library_dir=str(target.parent), models_dir=str(models_dir))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override
    return TestClient(app)


class TestPreviewResize:
    def test_resized_preview_bounds_the_larger_dimension(self, client: TestClient):
        resp = client.get(f"{BASE}/images/img_full/preview", params={"size": 256})
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/jpeg"
        image = PIL.Image.open(io.BytesIO(resp.content))
        assert max(image.size) == 256
        assert min(image.size) < 256  # aspect ratio preserved (800x600 → 256x192)

    def test_invalid_size_is_400(self, client: TestClient):
        resp = client.get(f"{BASE}/images/img_full/preview", params={"size": 300})
        assert resp.status_code == 400

    def test_etag_varies_by_size(self, client: TestClient):
        etag_small = client.get(f"{BASE}/images/img_full/preview", params={"size": 128}).headers["etag"]
        etag_large = client.get(f"{BASE}/images/img_full/preview", params={"size": 256}).headers["etag"]
        assert etag_small != etag_large

    def test_size_without_blob_falls_back_to_stored_preview(self, client: TestClient):
        resp = client.get(f"{BASE}/images/img_preview_only/preview", params={"size": 256})
        assert resp.status_code == 200
        assert resp.content == _png_bytes(64, 64)

    def test_unsized_preview_still_serves_the_stored_blob(self, client: TestClient):
        resp = client.get(f"{BASE}/images/img_preview_only/preview")
        assert resp.status_code == 200
        assert resp.content == _png_bytes(64, 64)


class TestViewPreviewDescriptors:
    @pytest.fixture()
    def previews(self, client: TestClient) -> dict:
        resp = client.get(f"{BASE}/records", params={"include": "view_previews", "limit": 10})
        assert resp.status_code == 200
        return {item["id"]: item.get("view_previews", {}) for item in resp.json()["items"]}

    def test_embedded_image_gets_a_sized_preview_url(self, previews: dict):
        assert previews["r0"]["image"]["preview_url"] == f"{BASE}/images/img_full/preview?size=256"

    def test_datalake_uri_passes_through_unsized(self, previews: dict):
        assert previews["r2"]["image"]["preview_url"] == "https://datalake.example.com/r2.jpg"

    def test_text_view_yields_a_truncated_excerpt(self, previews: dict):
        descriptor = previews["r3"]["text"]
        assert descriptor["kind"] == "text"
        assert descriptor["resource"] == "texts"
        assert descriptor["preview_url"] == ""
        assert descriptor["excerpt"] == TEXT_CONTENT[:160]
        assert len(descriptor["excerpt"]) == 160
