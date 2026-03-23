# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""End-to-end tests for the v2 REST API.

Four realistic dataset scenarios:
1. Static image with bbox + mask annotations
2. Multi-view image (rgb + thermal) with annotations on both views
3. Video with tracklet annotations (per-frame bboxes)
4. Multi-view video with tracklets on different views

Cross-cutting tests:
- Error responses (400/404/422)
- PaginatedResponse structure
"""

import tempfile
from functools import lru_cache
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets.builders.dataset_builder import DatasetBuilder
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import BBox, CompressedRLE, Entity, Image, Record, SchemaGroup, SequenceFrame
from pixano.schemas.annotations.tracklet import Tracklet


# ---------------------------------------------------------------------------
# Helper: create a test client from a dataset
# ---------------------------------------------------------------------------


def _make_client(dataset: Dataset) -> TestClient:
    tmp = Path(tempfile.mkdtemp())
    models_dir = tmp / "models"
    models_dir.mkdir()

    settings = Settings(
        library_dir=str(dataset.path.parent),
        models_dir=str(models_dir),
    )

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override
    return TestClient(app)


def _make_mask(mask_id: str, record_id: str, entity_id: str, view_id: str, **kwargs) -> CompressedRLE:
    """Create a valid CompressedRLE from a zero mask."""
    return CompressedRLE.from_mask(
        np.zeros((480, 640), dtype=np.uint8),
        id=mask_id,
        record_id=record_id,
        entity_id=entity_id,
        source_type="ground_truth",
        source_name="Ground Truth",
        view_id=view_id,
        **kwargs,
    )


def _blob_bytes(label: str) -> bytes:
    """Deterministic binary payload for streaming tests."""

    return label.encode("utf-8")


# ===========================================================================
# Scenario 1: Static image with bbox + mask annotations
# ===========================================================================

STATIC_IMAGE_DATASET_ID = "static_image_dataset"


class StaticImageBuilder(DatasetBuilder):
    def __init__(self, target_dir: Path, info: DatasetInfo):
        base = info.model_dump(include={"id", "name", "description", "size", "preview", "workspace", "storage_mode"})
        info = DatasetInfo(
            **base,
            record=Record,
            views={"image": Image},
            entity=Entity,
            bbox=BBox,
            mask=CompressedRLE,
        )
        super().__init__(target_dir=target_dir, info=info)

    def generate_data(self):
        for i in range(3):
            record_id = f"record_{i}"
            image = Image(
                id=f"image_{i}",
                record_id=record_id,
                logical_name="image",
                uri=f"image_{i}.jpg",
                width=640,
                height=480,
                format="jpg",
                preview=_blob_bytes(f"image_preview_{i}"),
                preview_format="png",
            )

            entities = []
            bboxes = []
            masks = []

            for j in range(2):
                entity_id = f"entity_{i}_{j}"
                entities.append(Entity(id=entity_id, record_id=record_id))

                bboxes.append(
                    BBox(
                        id=f"bbox_{i}_{j}",
                        record_id=record_id,
                        entity_id=entity_id,
                        source_type="ground_truth",
                        source_name="Ground Truth",
                        view_id="image",
                        coords=[0.1 * j, 0.1 * j, 0.2, 0.2],
                        format="xywh",
                        is_normalized=True,
                        confidence=0.9,
                    )
                )

                masks.append(_make_mask(f"mask_{i}_{j}", record_id, entity_id, "image"))

            yield {
                self.record_table_name: self.record_schema(id=record_id, split="train" if i < 2 else "test"),
                "images": image,
                "entities": entities,
                "bboxes": bboxes,
                "masks": masks,
            }


@pytest.fixture(scope="module")
def static_image_dataset() -> Dataset:
    tmp = Path(tempfile.mkdtemp())
    target = tmp / STATIC_IMAGE_DATASET_ID
    info = DatasetInfo(
        id=STATIC_IMAGE_DATASET_ID,
        name=STATIC_IMAGE_DATASET_ID,
        description="Static image dataset for v2 API testing",
        workspace=WorkspaceType.IMAGE,
    )
    builder = StaticImageBuilder(target_dir=target, info=info)
    return builder.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="module")
def static_image_client(static_image_dataset: Dataset) -> TestClient:
    return _make_client(static_image_dataset)


STATIC_BASE = f"/datasets/{STATIC_IMAGE_DATASET_ID}"


class TestStaticImage:
    """Scenario 1: Static image with bbox + mask annotations."""

    def test_list_datasets(self, static_image_client: TestClient):
        resp = static_image_client.get("/datasets")
        assert resp.status_code == 200
        body = resp.json()
        assert len(body) == 1
        assert body[0]["id"] == STATIC_IMAGE_DATASET_ID
        assert body[0]["num_records"] == 3
        assert body[0]["record"]["base"] == "Record"

    def test_get_dataset_info(self, static_image_client: TestClient):
        resp = static_image_client.get(f"/datasets/{STATIC_IMAGE_DATASET_ID}/info")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == STATIC_IMAGE_DATASET_ID
        assert body["num_records"] == 3
        assert body["views"]["image"]["base"] == "Image"

    def test_legacy_dataset_info_route_is_gone(self, static_image_client: TestClient):
        resp = static_image_client.get(f"/datasets/info/{STATIC_IMAGE_DATASET_ID}")
        assert resp.status_code == 404

    def test_list_records(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/records")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 3
        assert len(body["items"]) == 3
        assert "view_previews" not in body["items"][0]

    def test_list_records_with_view_previews(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/records", params={"include": "view_previews"})
        assert resp.status_code == 200
        body = resp.json()
        preview = body["items"][0]["view_previews"]["image"]
        assert preview == {
            "resource": "images",
            "id": "image_0",
            "kind": "image",
            "preview_url": f"{STATIC_BASE}/images/image_0/preview",
        }

    def test_list_records_rejects_unknown_include(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/records", params={"include": "view_previews,unknown"})
        assert resp.status_code == 400

    def test_get_record(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/records/record_0")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "record_0"
        assert body["split"] == "train"

    def test_list_images(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/images")
        assert resp.status_code == 200
        assert resp.json()["total"] == 3

    def test_list_record_images(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/records/record_0/images")
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    def test_get_image(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/images/image_0")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "image_0"
        assert body["src"] == "image_0.jpg"

    def test_get_image_preview(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/images/image_0/preview")
        assert resp.status_code == 200
        assert resp.content == _blob_bytes("image_preview_0")
        assert resp.headers["content-type"] == "image/png"

    def test_list_entities(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/entities")
        assert resp.status_code == 200
        assert resp.json()["total"] == 6  # 3 records * 2 entities

    def test_list_entities_filter_by_record(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/entities", params={"record_id": "record_1"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        for ent in body["items"]:
            assert ent["record_id"] == "record_1"

    def test_list_bboxes(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/bboxes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 6

    def test_list_bboxes_filter_by_entity(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/bboxes", params={"entity_id": "entity_0_0"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["entity_id"] == "entity_0_0"

    def test_list_bboxes_filter_by_record(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/bboxes", params={"record_id": "record_2"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        for b in body["items"]:
            assert b["record_id"] == "record_2"

    def test_get_bbox(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/bboxes/bbox_0_0")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "bbox_0_0"
        assert body["coords"] == [0.0, 0.0, 0.2, 0.2]
        assert body["format"] == "xywh"
        assert body["is_normalized"] is True
        assert body["confidence"] == 0.9

    def test_list_masks(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/masks")
        assert resp.status_code == 200
        assert resp.json()["total"] == 6

    def test_get_mask(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/masks/mask_0_0")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "mask_0_0"
        assert body["size"] == [480, 640]
        assert isinstance(body["counts"], str)

    def test_list_masks_filter_by_entity(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/masks", params={"entity_id": "entity_1_0"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["entity_id"] == "entity_1_0"

    def test_create_bbox(self, static_image_client: TestClient):
        resp = static_image_client.post(
            f"{STATIC_BASE}/bboxes",
            json={
                "id": "bbox_new",
                "record_id": "record_0",
                "entity_id": "entity_0_0",
                "source_type": "ground_truth",
                "source_name": "Ground Truth",
                "view_id": "image",
                "coords": [0.1, 0.2, 0.3, 0.4],
                "format": "xywh",
                "is_normalized": True,
                "confidence": 0.85,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["id"] == "bbox_new"
        assert body["confidence"] == 0.85

    def test_update_bbox(self, static_image_client: TestClient):
        resp = static_image_client.put(
            f"{STATIC_BASE}/bboxes/bbox_0_0",
            json={"confidence": 0.95},
        )
        assert resp.status_code == 200
        assert resp.json()["confidence"] == 0.95

    def test_delete_bbox(self, static_image_client: TestClient):
        # Create then delete
        static_image_client.post(
            f"{STATIC_BASE}/bboxes",
            json={
                "id": "bbox_to_delete",
                "record_id": "record_0",
                "entity_id": "entity_0_0",
                "coords": [0.0, 0.0, 0.1, 0.1],
                "format": "xywh",
                "is_normalized": True,
            },
        )
        resp = static_image_client.delete(f"{STATIC_BASE}/bboxes/bbox_to_delete")
        assert resp.status_code == 204

        # Verify it's gone
        resp2 = static_image_client.get(f"{STATIC_BASE}/bboxes/bbox_to_delete")
        assert resp2.status_code == 404


# ===========================================================================
# Scenario 2: Multi-view image (rgb + thermal) with annotations on both views
# ===========================================================================

MULTI_VIEW_IMAGE_DATASET_ID = "multi_view_image_dataset"


class MultiViewImageBuilder(DatasetBuilder):
    def __init__(self, target_dir: Path, info: DatasetInfo):
        base = info.model_dump(include={"id", "name", "description", "size", "preview", "workspace", "storage_mode"})
        info = DatasetInfo(
            **base,
            record=Record,
            views={"rgb": Image, "thermal": Image},
            entity=Entity,
            bbox=BBox,
        )
        super().__init__(target_dir=target_dir, info=info)

    def generate_data(self):
        for i in range(2):
            record_id = f"record_{i}"
            rgb = Image(
                id=f"rgb_{i}",
                record_id=record_id,
                logical_name="rgb",
                uri=f"rgb_{i}.jpg",
                width=640,
                height=480,
                format="jpg",
                preview=_blob_bytes(f"rgb_preview_{i}"),
                preview_format="png",
            )
            thermal = Image(
                id=f"thermal_{i}",
                record_id=record_id,
                logical_name="thermal",
                uri=f"thermal_{i}.jpg",
                width=640,
                height=480,
                format="jpg",
                preview=_blob_bytes(f"thermal_preview_{i}"),
                preview_format="png",
            )

            entities = []
            bboxes = []

            for j in range(2):
                entity_id = f"entity_{i}_{j}"
                entities.append(Entity(id=entity_id, record_id=record_id))

                # One bbox on rgb view
                bboxes.append(
                    BBox(
                        id=f"bbox_rgb_{i}_{j}",
                        record_id=record_id,
                        entity_id=entity_id,
                        source_type="ground_truth",
                        source_name="Ground Truth",
                        view_id="rgb",
                        coords=[0.1, 0.1, 0.2, 0.2],
                        format="xywh",
                        is_normalized=True,
                        confidence=0.9,
                    )
                )

                # One bbox on thermal view
                bboxes.append(
                    BBox(
                        id=f"bbox_thermal_{i}_{j}",
                        record_id=record_id,
                        entity_id=entity_id,
                        source_type="ground_truth",
                        source_name="Ground Truth",
                        view_id="thermal",
                        coords=[0.15, 0.15, 0.25, 0.25],
                        format="xywh",
                        is_normalized=True,
                        confidence=0.85,
                    )
                )

            yield {
                self.record_table_name: self.record_schema(id=record_id, split="train"),
                "images": [rgb, thermal],
                "entities": entities,
                "bboxes": bboxes,
            }


@pytest.fixture(scope="module")
def multi_view_image_dataset() -> Dataset:
    tmp = Path(tempfile.mkdtemp())
    target = tmp / MULTI_VIEW_IMAGE_DATASET_ID
    info = DatasetInfo(
        id=MULTI_VIEW_IMAGE_DATASET_ID,
        name=MULTI_VIEW_IMAGE_DATASET_ID,
        description="Multi-view image dataset for v2 API testing",
        workspace=WorkspaceType.IMAGE,
    )
    builder = MultiViewImageBuilder(target_dir=target, info=info)
    return builder.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="module")
def multi_view_image_client(multi_view_image_dataset: Dataset) -> TestClient:
    return _make_client(multi_view_image_dataset)


MV_IMAGE_BASE = f"/datasets/{MULTI_VIEW_IMAGE_DATASET_ID}"


class TestMultiViewImage:
    """Scenario 2: Multi-view image (rgb + thermal) with annotations on both views."""

    def test_list_images(self, multi_view_image_client: TestClient):
        """A shared image table exposes all logical views without a table filter."""
        resp = multi_view_image_client.get(f"{MV_IMAGE_BASE}/images")
        assert resp.status_code == 200
        assert resp.json()["total"] == 4

    def test_list_images_filter_by_view_name(self, multi_view_image_client: TestClient):
        for logical_name in ("rgb", "thermal"):
            resp = multi_view_image_client.get(f"{MV_IMAGE_BASE}/images", params={"view_name": logical_name})
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 2
            assert all(view["logical_name"] == logical_name for view in body["items"])

    def test_list_record_images_filter_by_view_name(self, multi_view_image_client: TestClient):
        for logical_name in ("rgb", "thermal"):
            resp = multi_view_image_client.get(
                f"{MV_IMAGE_BASE}/records/record_0/images", params={"view_name": logical_name}
            )
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 1
            assert body["items"][0]["logical_name"] == logical_name

    def test_list_bboxes_total(self, multi_view_image_client: TestClient):
        """Total bboxes: 2 records * 2 entities * 2 views = 8."""
        resp = multi_view_image_client.get(f"{MV_IMAGE_BASE}/bboxes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 8

    def test_filter_bboxes_by_view_name_rgb(self, multi_view_image_client: TestClient):
        resp = multi_view_image_client.get(f"{MV_IMAGE_BASE}/bboxes", params={"view_name": "rgb"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 4  # 2 records * 2 entities
        for b in body["items"]:
            assert b["view_id"] == "rgb"

    def test_filter_bboxes_by_view_name_thermal(self, multi_view_image_client: TestClient):
        resp = multi_view_image_client.get(f"{MV_IMAGE_BASE}/bboxes", params={"view_name": "thermal"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 4
        for b in body["items"]:
            assert b["view_id"] == "thermal"

    def test_entity_has_annotations_in_both_views(self, multi_view_image_client: TestClient):
        """Each entity should have exactly 2 bboxes: one on rgb, one on thermal."""
        resp = multi_view_image_client.get(f"{MV_IMAGE_BASE}/bboxes", params={"entity_id": "entity_0_0"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2
        view_names = {b["view_id"] for b in body["items"]}
        assert view_names == {"rgb", "thermal"}

    def test_list_entities(self, multi_view_image_client: TestClient):
        resp = multi_view_image_client.get(f"{MV_IMAGE_BASE}/entities")
        assert resp.status_code == 200
        assert resp.json()["total"] == 4  # 2 records * 2 entities


# ===========================================================================
# Scenario 3: Video with tracklet annotations (per-frame bboxes)
# ===========================================================================

VIDEO_DATASET_ID = "video_dataset"
NUM_FRAMES = 5


class VideoBuilder(DatasetBuilder):
    def __init__(self, target_dir: Path, info: DatasetInfo):
        base = info.model_dump(include={"id", "name", "description", "size", "preview", "workspace", "storage_mode"})
        info = DatasetInfo(
            **base,
            record=Record,
            views={"frames": SequenceFrame},
            entity=Entity,
            tracklet=Tracklet,
            bbox=BBox,
        )
        super().__init__(target_dir=target_dir, info=info)

    def generate_data(self):
        for i in range(2):
            record_id = f"record_{i}"

            frames = []
            for f_idx in range(NUM_FRAMES):
                frames.append(
                    SequenceFrame(
                        id=f"frame_{i}_{f_idx}",
                        record_id=record_id,
                        logical_name="frames",
                        uri="",
                        width=640,
                        height=480,
                        format="png",
                        raw_bytes=_blob_bytes(f"frame_{i}_{f_idx}"),
                        preview=_blob_bytes(f"frame_preview_{i}_{f_idx}"),
                        preview_format="png",
                        timestamp=f_idx * 0.1,
                        frame_index=f_idx,
                    )
                )

            entity_id = f"entity_{i}"
            tracklet_id = f"tracklet_{i}"
            entity = Entity(id=entity_id, record_id=record_id)
            tracklet = Tracklet(
                id=tracklet_id,
                record_id=record_id,
                entity_id=entity_id,
                source_type="ground_truth",
                source_name="Ground Truth",
                view_id="frames",
                start_timestep=0,
                end_timestep=NUM_FRAMES - 1,
                start_timestamp=0.0,
                end_timestamp=(NUM_FRAMES - 1) * 0.1,
            )

            bboxes = []
            for f_idx in range(NUM_FRAMES):
                bboxes.append(
                    BBox(
                        id=f"bbox_{i}_{f_idx}",
                        record_id=record_id,
                        entity_id=entity_id,
                        source_type="ground_truth",
                        source_name="Ground Truth",
                        view_id="frames",
                        tracklet_id=tracklet_id,
                        frame_index=f_idx,
                        coords=[0.1, 0.1, 0.2, 0.2],
                        format="xywh",
                        is_normalized=True,
                        confidence=0.9,
                    )
                )

            yield {
                self.record_table_name: self.record_schema(id=record_id, split="train"),
                "sequence_frames": frames,
                "entities": [entity],
                "tracklets": [tracklet],
                "bboxes": bboxes,
            }


@pytest.fixture(scope="module")
def video_dataset() -> Dataset:
    tmp = Path(tempfile.mkdtemp())
    target = tmp / VIDEO_DATASET_ID
    info = DatasetInfo(
        id=VIDEO_DATASET_ID,
        name=VIDEO_DATASET_ID,
        description="Video dataset for v2 API testing",
        workspace=WorkspaceType.VIDEO,
    )
    builder = VideoBuilder(target_dir=target, info=info)
    return builder.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="module")
def video_client(video_dataset: Dataset) -> TestClient:
    return _make_client(video_dataset)


VIDEO_BASE = f"/datasets/{VIDEO_DATASET_ID}"


class TestVideo:
    """Scenario 3: Video with tracklet annotations (per-frame bboxes)."""

    def test_list_tracklets(self, video_client: TestClient):
        resp = video_client.get(f"{VIDEO_BASE}/tracklets")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2  # 1 per record

    def test_get_tracklet(self, video_client: TestClient):
        resp = video_client.get(f"{VIDEO_BASE}/tracklets/tracklet_0")
        assert resp.status_code == 200
        body = resp.json()
        assert body["id"] == "tracklet_0"
        assert body["start_timestep"] == 0
        assert body["end_timestep"] == NUM_FRAMES - 1

    def test_list_bboxes_total(self, video_client: TestClient):
        """Total bboxes: 2 records * 5 frames = 10."""
        resp = video_client.get(f"{VIDEO_BASE}/bboxes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 10

    def test_filter_bboxes_by_tracklet_id(self, video_client: TestClient):
        resp = video_client.get(f"{VIDEO_BASE}/bboxes", params={"tracklet_id": "tracklet_0"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == NUM_FRAMES
        for b in body["items"]:
            assert b["tracklet_id"] == "tracklet_0"

    def test_filter_bboxes_by_frame_index(self, video_client: TestClient):
        resp = video_client.get(f"{VIDEO_BASE}/bboxes", params={"frame_index": 2})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 2  # 1 per record at frame 2
        for b in body["items"]:
            assert b["frame_index"] == 2

    def test_list_sframes(self, video_client: TestClient):
        """Total frames: 2 records * 5 frames = 10."""
        resp = video_client.get(f"{VIDEO_BASE}/sframes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 10

    def test_list_video_records_with_view_previews(self, video_client: TestClient):
        resp = video_client.get(f"{VIDEO_BASE}/records", params={"include": "view_previews"})
        assert resp.status_code == 200
        body = resp.json()
        preview = body["items"][0]["view_previews"]["frames"]
        assert preview == {
            "resource": "sframes",
            "id": "frame_0_0",
            "kind": "image",
            "preview_url": f"{VIDEO_BASE}/sframes/frame_0_0/preview",
        }

    def test_stream_sframe_blob(self, video_client: TestClient):
        resp = video_client.get(f"{VIDEO_BASE}/sframes/frame_0_0/blob")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == _blob_bytes("frame_0_0")

    def test_stream_sframe_preview(self, video_client: TestClient):
        resp = video_client.get(f"{VIDEO_BASE}/sframes/frame_0_0/preview")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "image/png"
        assert resp.content == _blob_bytes("frame_preview_0_0")

    def test_stream_record_sframe_batch(self, video_client: TestClient):
        resp = video_client.get(
            f"{VIDEO_BASE}/records/record_0/sframes/batch",
            params={"start_frame": 1, "batch_size": 2},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("multipart/x-mixed-replace; boundary=")
        assert resp.headers["x-total-frames"] == "2"
        assert resp.headers["x-start-frame"] == "1"
        assert resp.headers["x-batch-size"] == "2"
        assert b"X-Frame-Index: 1" in resp.content
        assert b"X-Frame-Index: 2" in resp.content
        assert _blob_bytes("frame_0_1") in resp.content
        assert _blob_bytes("frame_0_2") in resp.content
        assert _blob_bytes("frame_0_0") not in resp.content

    def test_list_entities(self, video_client: TestClient):
        resp = video_client.get(f"{VIDEO_BASE}/entities")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_create_tracklet_and_bbox(self, video_client: TestClient):
        """Create entity -> tracklet -> per-frame bbox hierarchy."""
        # Create entity
        resp = video_client.post(
            f"{VIDEO_BASE}/entities",
            json={"id": "entity_new", "record_id": "record_0"},
        )
        assert resp.status_code == 201

        # Create tracklet
        resp = video_client.post(
            f"{VIDEO_BASE}/tracklets",
            json={
                "id": "tracklet_new",
                "record_id": "record_0",
                "entity_id": "entity_new",
                "source_type": "ground_truth",
                "source_name": "Ground Truth",
                "view_id": "frames",
                "start_timestep": 0,
                "end_timestep": 2,
                "start_timestamp": 0.0,
                "end_timestamp": 0.2,
            },
        )
        assert resp.status_code == 201

        # Create per-frame bbox
        resp = video_client.post(
            f"{VIDEO_BASE}/bboxes",
            json={
                "id": "bbox_new_f0",
                "record_id": "record_0",
                "entity_id": "entity_new",
                "tracklet_id": "tracklet_new",
                "view_id": "frames",
                "frame_index": 0,
                "coords": [0.1, 0.1, 0.3, 0.3],
                "format": "xywh",
                "is_normalized": True,
                "confidence": 0.95,
            },
        )
        assert resp.status_code == 201
        body = resp.json()
        assert body["tracklet_id"] == "tracklet_new"
        assert body["frame_index"] == 0


# ===========================================================================
# Scenario 4: Multi-view video with tracklets on different views
# ===========================================================================

MV_VIDEO_DATASET_ID = "multi_view_video_dataset"
MV_NUM_FRAMES = 3


class MultiViewVideoBuilder(DatasetBuilder):
    def __init__(self, target_dir: Path, info: DatasetInfo):
        base = info.model_dump(include={"id", "name", "description", "size", "preview", "workspace", "storage_mode"})
        info = DatasetInfo(
            **base,
            record=Record,
            views={"rgb": SequenceFrame, "thermal": SequenceFrame},
            entity=Entity,
            tracklet=Tracklet,
            bbox=BBox,
            mask=CompressedRLE,
        )
        super().__init__(target_dir=target_dir, info=info)

    def generate_data(self):
        record_id = "record_0"

        rgb_frames = []
        thermal_frames = []
        for f_idx in range(MV_NUM_FRAMES):
            rgb_frames.append(
                SequenceFrame(
                    id=f"rgb_frame_{f_idx}",
                    record_id=record_id,
                    logical_name="rgb",
                    uri="",
                    width=640,
                    height=480,
                    format="png",
                    raw_bytes=_blob_bytes(f"rgb_frame_{f_idx}"),
                    preview=_blob_bytes(f"rgb_frame_preview_{f_idx}"),
                    preview_format="png",
                    timestamp=f_idx * 0.1,
                    frame_index=f_idx,
                )
            )
            thermal_frames.append(
                SequenceFrame(
                    id=f"thermal_frame_{f_idx}",
                    record_id=record_id,
                    logical_name="thermal",
                    uri="",
                    width=640,
                    height=480,
                    format="png",
                    raw_bytes=_blob_bytes(f"thermal_frame_{f_idx}"),
                    preview=_blob_bytes(f"thermal_frame_preview_{f_idx}"),
                    preview_format="png",
                    timestamp=f_idx * 0.1,
                    frame_index=f_idx,
                )
            )

        entity_id = "entity_0"
        entity = Entity(id=entity_id, record_id=record_id)

        # Tracklet on rgb for bboxes
        bbox_tracklet_id = "tracklet_bbox_rgb"
        bbox_tracklet = Tracklet(
            id=bbox_tracklet_id,
            record_id=record_id,
            entity_id=entity_id,
            source_type="ground_truth",
            source_name="Ground Truth",
            view_id="rgb",
            start_timestep=0,
            end_timestep=MV_NUM_FRAMES - 1,
            start_timestamp=0.0,
            end_timestamp=(MV_NUM_FRAMES - 1) * 0.1,
        )

        # Tracklet on thermal for masks
        mask_tracklet_id = "tracklet_mask_thermal"
        mask_tracklet = Tracklet(
            id=mask_tracklet_id,
            record_id=record_id,
            entity_id=entity_id,
            source_type="ground_truth",
            source_name="Ground Truth",
            view_id="thermal",
            start_timestep=0,
            end_timestep=MV_NUM_FRAMES - 1,
            start_timestamp=0.0,
            end_timestamp=(MV_NUM_FRAMES - 1) * 0.1,
        )

        bboxes = []
        masks = []
        for f_idx in range(MV_NUM_FRAMES):
            bboxes.append(
                BBox(
                    id=f"bbox_rgb_{f_idx}",
                    record_id=record_id,
                    entity_id=entity_id,
                    source_type="ground_truth",
                    source_name="Ground Truth",
                    view_id="rgb",
                    tracklet_id=bbox_tracklet_id,
                    frame_index=f_idx,
                    coords=[0.1, 0.1, 0.2, 0.2],
                    format="xywh",
                    is_normalized=True,
                    confidence=0.9,
                )
            )

            masks.append(
                _make_mask(
                    f"mask_thermal_{f_idx}",
                    record_id,
                    entity_id,
                    "thermal",
                    tracklet_id=mask_tracklet_id,
                    frame_index=f_idx,
                )
            )

        yield {
            self.record_table_name: self.record_schema(id=record_id, split="train"),
            "sequence_frames": rgb_frames + thermal_frames,
            "entities": [entity],
            "tracklets": [bbox_tracklet, mask_tracklet],
            "bboxes": bboxes,
            "masks": masks,
        }


@pytest.fixture(scope="module")
def multi_view_video_dataset() -> Dataset:
    tmp = Path(tempfile.mkdtemp())
    target = tmp / MV_VIDEO_DATASET_ID
    info = DatasetInfo(
        id=MV_VIDEO_DATASET_ID,
        name=MV_VIDEO_DATASET_ID,
        description="Multi-view video dataset for v2 API testing",
        workspace=WorkspaceType.VIDEO,
    )
    builder = MultiViewVideoBuilder(target_dir=target, info=info)
    return builder.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="module")
def multi_view_video_client(multi_view_video_dataset: Dataset) -> TestClient:
    return _make_client(multi_view_video_dataset)


MV_VIDEO_BASE = f"/datasets/{MV_VIDEO_DATASET_ID}"


class TestMultiViewVideo:
    """Scenario 4: Multi-view video with tracklets on different views."""

    def test_list_sframes(self, multi_view_video_client: TestClient):
        """A shared frame table exposes all logical views without a table filter."""
        resp = multi_view_video_client.get(f"{MV_VIDEO_BASE}/sframes")
        assert resp.status_code == 200
        assert resp.json()["total"] == 6

    def test_list_sframes_filter_by_view_name(self, multi_view_video_client: TestClient):
        for logical_name in ("rgb", "thermal"):
            resp = multi_view_video_client.get(f"{MV_VIDEO_BASE}/sframes", params={"view_name": logical_name})
            assert resp.status_code == 200
            body = resp.json()
            assert body["total"] == 3
            assert all(view["logical_name"] == logical_name for view in body["items"])

    def test_stream_record_sframe_batch_for_one_view(self, multi_view_video_client: TestClient):
        resp = multi_view_video_client.get(
            f"{MV_VIDEO_BASE}/records/record_0/sframes/batch",
            params={"view_name": "rgb", "batch_size": 3},
        )
        assert resp.status_code == 200
        assert _blob_bytes("rgb_frame_0") in resp.content
        assert _blob_bytes("rgb_frame_1") in resp.content
        assert _blob_bytes("rgb_frame_2") in resp.content
        assert _blob_bytes("thermal_frame_0") not in resp.content

    def test_stream_record_sframe_batch_for_thermal_view(self, multi_view_video_client: TestClient):
        resp = multi_view_video_client.get(
            f"{MV_VIDEO_BASE}/records/record_0/sframes/batch",
            params={"view_name": "thermal", "start_frame": 1, "batch_size": 2},
        )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("multipart/x-mixed-replace; boundary=")
        assert resp.headers["x-total-frames"] == "2"
        assert b"X-Frame-Index: 1" in resp.content
        assert b"X-Frame-Index: 2" in resp.content
        assert _blob_bytes("thermal_frame_1") in resp.content
        assert _blob_bytes("thermal_frame_2") in resp.content
        assert _blob_bytes("rgb_frame_1") not in resp.content

    def test_list_tracklets(self, multi_view_video_client: TestClient):
        """2 tracklets: 1 bbox on rgb, 1 mask on thermal."""
        resp = multi_view_video_client.get(f"{MV_VIDEO_BASE}/tracklets")
        assert resp.status_code == 200
        assert resp.json()["total"] == 2

    def test_filter_tracklets_by_view_name_rgb(self, multi_view_video_client: TestClient):
        resp = multi_view_video_client.get(f"{MV_VIDEO_BASE}/tracklets", params={"view_name": "rgb"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == "tracklet_bbox_rgb"

    def test_filter_tracklets_by_view_name_thermal(self, multi_view_video_client: TestClient):
        resp = multi_view_video_client.get(f"{MV_VIDEO_BASE}/tracklets", params={"view_name": "thermal"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == 1
        assert body["items"][0]["id"] == "tracklet_mask_thermal"

    def test_filter_bboxes_by_tracklet_id(self, multi_view_video_client: TestClient):
        resp = multi_view_video_client.get(f"{MV_VIDEO_BASE}/bboxes", params={"tracklet_id": "tracklet_bbox_rgb"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == MV_NUM_FRAMES
        for b in body["items"]:
            assert b["tracklet_id"] == "tracklet_bbox_rgb"
            assert b["view_id"] == "rgb"

    def test_filter_masks_by_tracklet_id(self, multi_view_video_client: TestClient):
        resp = multi_view_video_client.get(f"{MV_VIDEO_BASE}/masks", params={"tracklet_id": "tracklet_mask_thermal"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == MV_NUM_FRAMES
        for m in body["items"]:
            assert m["tracklet_id"] == "tracklet_mask_thermal"
            assert m["view_id"] == "thermal"

    def test_bboxes_only_on_rgb(self, multi_view_video_client: TestClient):
        """All bboxes should be on rgb view."""
        resp = multi_view_video_client.get(f"{MV_VIDEO_BASE}/bboxes")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == MV_NUM_FRAMES
        for b in body["items"]:
            assert b["view_id"] == "rgb"

    def test_masks_only_on_thermal(self, multi_view_video_client: TestClient):
        """All masks should be on thermal view."""
        resp = multi_view_video_client.get(f"{MV_VIDEO_BASE}/masks")
        assert resp.status_code == 200
        body = resp.json()
        assert body["total"] == MV_NUM_FRAMES
        for m in body["items"]:
            assert m["view_id"] == "thermal"


# ===========================================================================
# Cross-cutting: Error responses (using scenario 1 client)
# ===========================================================================


class TestErrorResponses:
    """Tests for consistent error responses."""

    def test_dataset_not_found(self, static_image_client: TestClient):
        resp = static_image_client.get("/datasets/nonexistent/records")
        assert resp.status_code == 404

    def test_resource_not_found(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/records/nonexistent")
        assert resp.status_code == 404

    def test_delete_nonexistent(self, static_image_client: TestClient):
        resp = static_image_client.delete(f"{STATIC_BASE}/entities/nonexistent")
        assert resp.status_code == 404

    def test_invalid_pagination(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/records", params={"limit": 0})
        assert resp.status_code == 422

    def test_422_on_invalid_body(self, static_image_client: TestClient):
        resp = static_image_client.post(f"{STATIC_BASE}/entities", json={})
        assert resp.status_code == 422

    def test_create_bbox_invalid_entity(self, static_image_client: TestClient):
        resp = static_image_client.post(
            f"{STATIC_BASE}/bboxes",
            json={
                "id": "bbox_bad_entity",
                "record_id": "record_0",
                "entity_id": "nonexistent_entity",
                "coords": [0.1, 0.2, 0.3, 0.4],
                "format": "xywh",
                "is_normalized": True,
            },
        )
        assert resp.status_code == 400

    def test_create_entity_invalid_record(self, static_image_client: TestClient):
        resp = static_image_client.post(
            f"{STATIC_BASE}/entities",
            json={"id": "entity_bad", "record_id": "nonexistent"},
        )
        assert resp.status_code == 400


# ===========================================================================
# Cross-cutting: PaginatedResponse structure (using scenario 1 client)
# ===========================================================================


class TestPaginatedResponse:
    """Tests that all list endpoints return consistent PaginatedResponse."""

    @pytest.mark.parametrize(
        "endpoint",
        [
            f"{STATIC_BASE}/records",
            f"{STATIC_BASE}/images",
            f"{STATIC_BASE}/entities",
            f"{STATIC_BASE}/bboxes",
            f"{STATIC_BASE}/masks",
        ],
    )
    def test_paginated_response_structure(self, static_image_client: TestClient, endpoint: str):
        resp = static_image_client.get(endpoint)
        assert resp.status_code == 200
        body = resp.json()
        assert set(body.keys()) == {"items", "total", "limit", "offset"}
        assert isinstance(body["items"], list)
        assert isinstance(body["total"], int)
        assert isinstance(body["limit"], int)
        assert isinstance(body["offset"], int)

    def test_pagination_limit_offset(self, static_image_client: TestClient):
        resp = static_image_client.get(f"{STATIC_BASE}/records", params={"limit": 2, "offset": 0})
        assert resp.status_code == 200
        body = resp.json()
        assert len(body["items"]) == 2
        assert body["total"] == 3
        assert body["limit"] == 2
        assert body["offset"] == 0

        # Second page
        resp2 = static_image_client.get(f"{STATIC_BASE}/records", params={"limit": 2, "offset": 2})
        assert resp2.status_code == 200
        body2 = resp2.json()
        assert len(body2["items"]) == 1


# ---------------------------------------------------------------------------
# Empty library
# ---------------------------------------------------------------------------


class TestEmptyLibrary:
    """Verify the app works gracefully with no datasets."""

    def test_list_datasets_returns_empty(self):
        tmp = Path(tempfile.mkdtemp())
        settings = Settings(library_dir=str(tmp), models_dir=str(tmp))

        @lru_cache
        def _override():
            return settings

        app = create_app(settings)
        app.dependency_overrides[get_settings] = _override
        client = TestClient(app)

        resp = client.get("/datasets")
        assert resp.status_code == 200
        assert resp.json() == []
