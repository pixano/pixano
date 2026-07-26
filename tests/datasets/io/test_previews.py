# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import io
from pathlib import Path

import PIL.Image
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from tests.datasets.io.formats.test_jsonl_importer import _case


def _import_corpus(name: str, tmp_path: Path):
    case = _case(name, tmp_path / "src")
    dataset, _ = case.run_import(tmp_path / "data")
    return dataset


class TestPreviewStamping:
    def test_imported_images_carry_png_thumbnails(self, tmp_path: Path):
        dataset = _import_corpus("mel", tmp_path)
        rows = dataset.open_table("images").search().select(["preview", "preview_format"]).limit(None).to_list()
        assert rows
        for row in rows:
            assert row["preview_format"] == "png"
            thumbnail = PIL.Image.open(io.BytesIO(row["preview"]))
            assert thumbnail.format == "PNG"
            assert max(thumbnail.size) <= 64

    def test_only_first_sequence_frames_carry_thumbnails(self, tmp_path: Path):
        # One poster per record/view is all the grid uses; stamping every frame
        # is per-row PIL work that starves concurrent API requests during imports.
        dataset = _import_corpus("frames_masks", tmp_path)
        rows = (
            dataset.open_table("sequence_frames")
            .search()
            .select(["frame_index", "preview_format"])
            .limit(None)
            .to_list()
        )
        assert rows
        assert all(row["preview_format"] == "png" for row in rows if row["frame_index"] == 0)
        assert all(row["preview_format"] == "" for row in rows if row["frame_index"] != 0)

    def test_uri_mode_rows_have_no_thumbnail(self, tmp_path: Path):
        dataset = _import_corpus("lerobot_window", tmp_path)  # remote videos, nothing embedded
        rows = dataset.open_table("videos").search().select(["preview_format"]).limit(None).to_list()
        assert rows and all(row["preview_format"] == "" for row in rows)

    def test_preview_stamping_is_idempotent(self, tmp_path: Path):
        first = _import_corpus("mel", tmp_path / "one")
        second = _import_corpus("mel", tmp_path / "two")
        previews_first = sorted(
            (row["id"], row["preview"])
            for row in first.open_table("images").search().select(["id", "preview"]).limit(None).to_list()
        )
        previews_second = sorted(
            (row["id"], row["preview"])
            for row in second.open_table("images").search().select(["id", "preview"]).limit(None).to_list()
        )
        assert previews_first == previews_second


class TestPreviewApi:
    def _client(self, data_dir: Path) -> TestClient:
        settings = Settings(library_dir=str(data_dir / "library"))
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        return TestClient(app)

    def test_preview_route_serves_imported_thumbnails(self, tmp_path: Path):
        dataset = _import_corpus("mel", tmp_path)
        client = self._client(tmp_path / "data")

        records = client.get(f"/datasets/{dataset.info.id}/records", params={"include": "view_previews"}).json()
        descriptor = records["items"][0]["view_previews"]["image"]
        # Explorer previews request a grid-sized thumbnail, resized from the embedded blob.
        assert descriptor["preview_url"].endswith("/preview?size=256")

        response = client.get(descriptor["preview_url"])
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/jpeg"
        image = PIL.Image.open(io.BytesIO(response.content))
        assert image.format == "JPEG"
        assert max(image.size) <= 256

    def test_datalake_uri_rows_expose_the_remote_url(self, tmp_path: Path):
        dataset = _import_corpus("mixed_media", tmp_path)  # embedded photo + remote video
        client = self._client(tmp_path / "data")

        records = client.get(f"/datasets/{dataset.info.id}/records", params={"include": "view_previews"}).json()
        previews = records["items"][0]["view_previews"]
        assert previews["image"]["preview_url"].endswith("/preview?size=256")  # embedded -> route
        embedded = client.get(previews["image"]["preview_url"])
        assert embedded.status_code == 200
