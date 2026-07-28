# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests for the inference API router."""

import io
import json
import tempfile
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient
from PIL import Image as PILImage

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.inference.exceptions import InferenceRequestError
from pixano.inference.provider import InferenceProvider
from pixano.inference.providers.pixano_inference import PixanoInferenceProvider
from pixano.inference.types import (
    CompressedRLEData,
    DetectionOutput,
    DetectionResult,
    ImageMaskGenerationOutput,
    ImageMaskGenerationResult,
    ModelInfo,
    NDArrayData,
    ServerInfo,
    UsageInfo,
    VideoMaskGenerationJobStatus,
    VideoMaskGenerationOutput,
    VideoMaskGenerationResult,
    VLMOutput,
    VLMResult,
)
from pixano.schemas import Image, Record, SequenceFrame


def _make_mock_provider(name: str, url: str) -> MagicMock:
    provider = MagicMock(spec=InferenceProvider)
    provider.name = name
    provider.url = url
    provider.get_server_info = AsyncMock(
        return_value=ServerInfo(
            version="1.2.3",
            models=["sam2", "sam2-video", "qwen-vl"],
            models_to_task={
                "sam2": "image_mask_generation",
                "sam2-video": "video_mask_generation",
                "qwen-vl": "vlm",
            },
        )
    )
    provider.list_models = AsyncMock(return_value=[])
    provider.vlm = AsyncMock()
    provider.image_mask_generation = AsyncMock()
    provider.video_mask_generation = AsyncMock()
    provider.submit_video_mask_generation_job = AsyncMock()
    provider.get_video_mask_generation_job = AsyncMock()
    provider.cancel_video_mask_generation_job = AsyncMock()
    provider.detection = AsyncMock()
    return provider


def _make_client(inference_providers=None, default_inference_provider=None) -> tuple[TestClient, Settings]:
    tmp = Path(tempfile.mkdtemp())
    models_dir = tmp / "models"
    models_dir.mkdir()
    library_dir = tmp / "library"
    library_dir.mkdir()

    kwargs: dict = {
        "library_dir": str(library_dir),
        "models_dir": str(models_dir),
    }
    if inference_providers is not None:
        kwargs["inference_providers"] = inference_providers
    if default_inference_provider is not None:
        kwargs["default_inference_provider"] = default_inference_provider

    settings = Settings(**kwargs)

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override
    return TestClient(app), settings


def _png_bytes(color: tuple[int, int, int]) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (8, 8), color=color).save(buffer, format="PNG")
    return buffer.getvalue()


def _create_dataset_with_embedded_views(library_dir: Path) -> tuple[str, str, str, bytes]:
    dataset = Dataset.create(
        library_dir / "inference-fixture",
        DatasetInfo(
            name="inference-fixture",
            description="Dataset for inference router tests.",
            record=Record,
            views={"image": Image, "sequence_frame": SequenceFrame},
        ),
    )
    record = Record(id="record-1")
    image = Image.from_bytes(
        record_id=record.id,
        logical_name="camera",
        raw_bytes=_png_bytes((255, 0, 0)),
        id="image-view-1",
    )
    frames = [
        SequenceFrame.from_bytes(
            record_id=record.id,
            logical_name="camera",
            raw_bytes=_png_bytes((0, 255, 0)),
            timestamp=0.0,
            frame_index=0,
            id="frame-view-0",
        ),
        SequenceFrame.from_bytes(
            record_id=record.id,
            logical_name="camera",
            raw_bytes=_png_bytes((0, 0, 255)),
            timestamp=1.0,
            frame_index=1,
            id="frame-view-1",
        ),
        SequenceFrame.from_bytes(
            record_id=record.id,
            logical_name="camera",
            raw_bytes=_png_bytes((255, 255, 0)),
            timestamp=2.0,
            frame_index=2,
            id="frame-view-2",
        ),
        SequenceFrame.from_bytes(
            record_id=record.id,
            logical_name="camera",
            raw_bytes=_png_bytes((255, 0, 255)),
            timestamp=3.0,
            frame_index=3,
            id="frame-view-3",
        ),
    ]
    dataset.add_records({"records": record, "images": image, "sequence_frames": frames})
    return dataset.info.id, record.id, image.id, image.raw_bytes


class TestInferenceRegistry:
    def test_connected_returns_empty_registry(self):
        client, _ = _make_client()

        response = client.get("/inference/connected")

        assert response.status_code == 200
        assert response.json() == {
            "connected": False,
            "providers": {},
            "default_provider": None,
        }

    def test_connected_returns_seeded_provider(self):
        provider = _make_mock_provider("pixano-inference", "http://127.0.0.1:7463")
        client, _ = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )

        response = client.get("/inference/connected")

        assert response.status_code == 200
        assert response.json() == {
            "connected": True,
            "providers": {"pixano-inference": {"url": "http://127.0.0.1:7463"}},
            "default_provider": "pixano-inference",
        }

    def test_connect_registers_pixano_inference_singleton(self):
        client, settings = _make_client()
        provider = _make_mock_provider("pixano-inference", "http://127.0.0.1:7463")

        with patch(
            "pixano.api.routers.inference.PixanoInferenceProvider.connect",
            AsyncMock(return_value=provider),
        ) as connect_mock:
            response = client.post("/inference/connect", params={"url": "http://127.0.0.1:7463 "})

        assert response.status_code == 200
        assert response.json() == {
            "status": "connected",
            "provider": "pixano-inference",
            "url": "http://127.0.0.1:7463",
        }
        connect_mock.assert_awaited_once_with("http://127.0.0.1:7463", api_key=None)
        assert "pixano-inference" in settings.inference_providers
        assert settings.default_inference_provider == "pixano-inference"

    def test_connect_bad_url_is_400(self):
        client, _ = _make_client()
        response = client.post("/inference/connect", params={"url": "not-a-url"})
        assert response.status_code == 400


class TestInferenceModels:
    def test_list_models_aggregates_providers(self):
        provider_a = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider_b = _make_mock_provider("pixano-inference@127.0.0.1:7464", "http://127.0.0.1:7464")
        provider_a.list_models = AsyncMock(
            return_value=[
                ModelInfo(
                    name="sam2",
                    task="image_mask_generation",
                    model_path="facebook/sam2-hiera-tiny",
                    model_class="SAM2",
                )
            ]
        )
        provider_b.list_models = AsyncMock(
            return_value=[
                ModelInfo(
                    name="qwen-vl",
                    task="vlm",
                    model_path="Qwen/Qwen2.5-VL-3B-Instruct",
                    model_class="QwenVL",
                )
            ]
        )
        client, _ = _make_client(
            inference_providers={provider_a.name: provider_a, provider_b.name: provider_b},
            default_inference_provider=provider_a.name,
        )

        response = client.get("/inference/models/list")

        assert response.status_code == 200
        assert response.json() == [
            {
                "name": "sam2",
                "task": "image_mask_generation",
                "provider_name": provider_a.name,
                "model_path": "facebook/sam2-hiera-tiny",
                "model_class": "SAM2",
            },
            {
                "name": "qwen-vl",
                "task": "vlm",
                "provider_name": provider_b.name,
                "model_path": "Qwen/Qwen2.5-VL-3B-Instruct",
                "model_class": "QwenVL",
            },
        ]


class TestLegacyRoutesRemoved:
    def test_old_management_routes_are_not_exposed(self):
        client, _ = _make_client()

        for method, path in (
            ("get", "/app/inference/servers/"),
            ("get", "/app/inference/models/"),
            ("get", "/app/settings/"),
            ("get", "/inference/status"),
            ("get", "/inference/models/list-all"),
            ("post", "/inference/models/instantiate"),
            ("delete", "/inference/models/delete/sam2"),
            ("post", "/inference/segmentation"),
            ("post", "/inference/tracking"),
        ):
            response = getattr(client, method)(path)
            assert response.status_code == 404, f"{method} {path} should be gone"

    def test_new_discovery_routes_are_exposed(self):
        client, _ = _make_client()
        # The realigned routes exist (200 with no providers, not a 404 route-not-found).
        assert client.get("/inference/connected").status_code == 200
        assert client.get("/inference/models/list").status_code == 200


class TestImageSegmentation:
    def test_segment_image_uses_requested_provider(self):
        default_provider = _make_mock_provider(
            "pixano-inference@127.0.0.1:7463",
            "http://127.0.0.1:7463",
        )
        target_provider = _make_mock_provider(
            "pixano-inference@127.0.0.1:7464",
            "http://127.0.0.1:7464",
        )
        target_provider.image_mask_generation = AsyncMock(
            return_value=ImageMaskGenerationResult(
                data=ImageMaskGenerationOutput(
                    masks=[[CompressedRLEData(size=[8, 8], counts=b"abc")]],
                    scores=NDArrayData(values=[0.98], shape=[1, 1]),
                    image_embedding=NDArrayData(values=[1.0, 2.0], shape=[1, 2]),
                    high_resolution_features=[NDArrayData(values=[0.5], shape=[1, 1])],
                    mask_logits=NDArrayData(values=[0.1, 0.2, 0.3, 0.4], shape=[1, 2, 2]),
                ),
                timestamp=datetime.fromisoformat("2026-03-20T10:00:00"),
                processing_time=0.12,
                metadata={"backend": "mock"},
                id="seg-1",
                status="SUCCESS",
            )
        )
        client, settings = _make_client(
            inference_providers={
                default_provider.name: default_provider,
                target_provider.name: target_provider,
            },
            default_inference_provider=default_provider.name,
        )
        dataset_id, _, view_id, expected_image_bytes = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/image_mask_generation",
            json={
                "model": "sam2",
                "provider_name": target_provider.name,
                "dataset_id": dataset_id,
                "view_id": view_id,
                "image_embedding": {"values": [1.0, 2.0], "shape": [1, 2]},
                "high_resolution_features": [{"values": [0.5], "shape": [1, 1]}],
                "mask_input": {"values": [0.1, 0.2, 0.3, 0.4], "shape": [1, 2, 2]},
                "points": [[[16, 24], [32, 48]]],
                "labels": [[1, 0]],
                "boxes": [[10, 12, 64, 72]],
                "return_image_embedding": True,
                "return_logits": True,
            },
        )

        assert response.status_code == 200
        assert response.json()["data"]["masks"][0][0] == {"size": [8, 8], "counts": "abc"}
        assert response.json()["data"]["mask_logits"] == {
            "values": [0.1, 0.2, 0.3, 0.4],
            "shape": [1, 2, 2],
        }
        default_provider.image_mask_generation.assert_not_called()
        target_provider.image_mask_generation.assert_called_once()
        input_data = target_provider.image_mask_generation.await_args.kwargs["input_data"]
        assert input_data.image == expected_image_bytes
        assert input_data.boxes == [[10, 12, 64, 72]]
        assert input_data.mask_input == NDArrayData(values=[0.1, 0.2, 0.3, 0.4], shape=[1, 2, 2])
        assert input_data.return_logits is True

    def test_segment_image_returns_404_for_unknown_view(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, _, _, _ = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/image_mask_generation",
            json={
                "model": "sam2",
                "dataset_id": dataset_id,
                "view_id": "missing-view",
            },
        )

        assert response.status_code == 404
        provider.image_mask_generation.assert_not_called()

    def test_segment_image_preserves_upstream_client_error(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.image_mask_generation = AsyncMock(
            side_effect=InferenceRequestError(
                status_code=400, code="bad_request", message="Part exceeded maximum size of 1024KB."
            )
        )
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, _, view_id, _ = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/image_mask_generation",
            json={
                "model": "sam2",
                "dataset_id": dataset_id,
                "view_id": view_id,
            },
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Part exceeded maximum size of 1024KB."}

    def test_segment_image_rejects_tracking_only_model(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.list_models = AsyncMock(
            return_value=[
                ModelInfo(
                    name="sam2-video",
                    task="video_mask_generation",
                    model_path="facebook/sam2-hiera-tiny",
                    model_class="SAM2Video",
                )
            ]
        )
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, _, view_id, _ = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/image_mask_generation",
            json={
                "model": "sam2-video",
                "dataset_id": dataset_id,
                "view_id": view_id,
            },
        )

        assert response.status_code == 400
        assert response.json() == {
            "detail": "Model 'sam2-video' is a video_mask_generation model; use /inference/video_mask_generation"
        }
        provider.image_mask_generation.assert_not_called()


class TestVideoTracking:
    def test_track_video_uses_default_provider(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.video_mask_generation = AsyncMock(
            return_value=VideoMaskGenerationResult(
                data=VideoMaskGenerationOutput(
                    objects_ids=[7],
                    frame_indexes=[0, 1],
                    masks=[
                        CompressedRLEData(size=[8, 8], counts=b"abc"),
                        CompressedRLEData(size=[8, 8], counts=b"xyz"),
                    ],
                ),
                timestamp=datetime.fromisoformat("2026-03-20T10:05:00"),
                processing_time=0.45,
                metadata={"backend": "mock"},
                id="track-1",
                status="SUCCESS",
            )
        )
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, record_id, _, _ = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/video_mask_generation",
            json={
                "model": "sam2-video",
                "dataset_id": dataset_id,
                "record_id": record_id,
                "view_name": "camera",
                "start_frame_index": 0,
                "frame_count": 2,
                "objects_ids": [7],
                "prompt_frame_indexes": [1],
                "points": [[[4, 4]]],
                "labels": [[1]],
            },
        )

        assert response.status_code == 200
        assert response.json()["data"]["frame_indexes"] == [0, 1]
        provider.video_mask_generation.assert_called_once()
        input_data = provider.video_mask_generation.await_args.kwargs["input_data"]
        assert len(input_data.video) == 2
        assert input_data.frame_indexes == [1]

    def test_track_video_rejects_prompt_index_outside_window(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, record_id, _, _ = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/video_mask_generation",
            json={
                "model": "sam2-video",
                "dataset_id": dataset_id,
                "record_id": record_id,
                "view_name": "camera",
                "start_frame_index": 0,
                "frame_count": 1,
                "objects_ids": [7],
                "prompt_frame_indexes": [99],
            },
        )

        assert response.status_code == 400
        provider.video_mask_generation.assert_not_called()

    def test_track_video_serializes_interval_keyframes(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.video_mask_generation = AsyncMock(
            return_value=VideoMaskGenerationResult(
                data=VideoMaskGenerationOutput(
                    objects_ids=[7],
                    frame_indexes=[0, 1],
                    masks=[
                        CompressedRLEData(size=[8, 8], counts=b"abc"),
                        CompressedRLEData(size=[8, 8], counts=b"xyz"),
                    ],
                ),
                timestamp=datetime.fromisoformat("2026-03-20T10:05:00"),
                processing_time=0.45,
                metadata={"backend": "mock"},
                id="track-interval-1",
                status="SUCCESS",
            )
        )
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, record_id, _, _ = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/video_mask_generation",
            json={
                "model": "sam2-video",
                "dataset_id": dataset_id,
                "record_id": record_id,
                "view_name": "camera",
                "start_frame_index": 1,
                "frame_count": 3,
                "objects_ids": [7],
                "interval": {
                    "start_frame": 2,
                    "end_frame": 3,
                    "direction": "forward",
                },
                "keyframes": [
                    {
                        "frame_index": 2,
                        "mask": {
                            "size": [8, 8],
                            "counts": [4, 8, 52],
                        },
                    }
                ],
            },
        )

        assert response.status_code == 200
        provider.video_mask_generation.assert_called_once()
        input_data = provider.video_mask_generation.await_args.kwargs["input_data"]
        assert input_data.frame_indexes == [1]
        assert input_data.interval == {"start_frame": 1, "end_frame": 2, "direction": "forward"}
        assert input_data.propagate is True
        assert input_data.keyframes == [
            {
                "frame_index": 1,
                "mask": {
                    "size": [8, 8],
                    "counts": [4, 8, 52],
                },
            }
        ]

    def test_track_video_serializes_non_propagating_single_frame_prompt(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.video_mask_generation = AsyncMock(
            return_value=VideoMaskGenerationResult(
                data=VideoMaskGenerationOutput(
                    objects_ids=[7],
                    frame_indexes=[0],
                    masks=[CompressedRLEData(size=[8, 8], counts=b"abc")],
                ),
                timestamp=datetime.fromisoformat("2026-03-20T10:05:00"),
                processing_time=0.45,
                metadata={"backend": "mock"},
                id="track-single-1",
                status="SUCCESS",
            )
        )
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, record_id, _, _ = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/video_mask_generation",
            json={
                "model": "sam2-video",
                "dataset_id": dataset_id,
                "record_id": record_id,
                "view_name": "camera",
                "start_frame_index": 2,
                "frame_count": 1,
                "objects_ids": [7],
                "prompt_frame_indexes": [2],
                "points": [[[4, 4]]],
                "labels": [[1]],
                "propagate": False,
            },
        )

        assert response.status_code == 200
        provider.video_mask_generation.assert_called_once()
        input_data = provider.video_mask_generation.await_args.kwargs["input_data"]
        assert input_data.frame_indexes == [0]
        assert input_data.propagate is False
        assert len(input_data.video) == 1

    def test_submit_tracking_job_stores_local_job_and_remaps_completed_frames(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.submit_video_mask_generation_job = AsyncMock(
            return_value=VideoMaskGenerationJobStatus(
                job_id="provider-job-1",
                status="running",
            )
        )
        provider.get_video_mask_generation_job = AsyncMock(
            return_value=VideoMaskGenerationJobStatus(
                job_id="provider-job-1",
                status="completed",
                data=VideoMaskGenerationOutput(
                    objects_ids=[7],
                    frame_indexes=[0, 1],
                    masks=[
                        CompressedRLEData(size=[8, 8], counts=b"abc"),
                        CompressedRLEData(size=[8, 8], counts=b"xyz"),
                    ],
                ),
                metadata={"backend": "mock"},
                timestamp=datetime.fromisoformat("2026-03-20T10:05:00"),
                processing_time=0.45,
            )
        )
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, record_id, _, _ = _create_dataset_with_embedded_views(settings.library_dir)

        submit_response = client.post(
            "/inference/video_mask_generation/jobs",
            json={
                "model": "sam2-video",
                "dataset_id": dataset_id,
                "record_id": record_id,
                "view_name": "camera",
                "start_frame_index": 2,
                "frame_count": 2,
                "objects_ids": [7],
                "prompt_frame_indexes": [2],
                "points": [[[4, 4]]],
                "labels": [[1]],
                "propagate": False,
            },
        )

        assert submit_response.status_code == 200
        assert submit_response.json()["status"] == "running"
        provider.submit_video_mask_generation_job.assert_called_once()
        input_data = provider.submit_video_mask_generation_job.await_args.kwargs["input_data"]
        assert input_data.frame_indexes == [0]
        assert input_data.propagate is False

        local_job_id = submit_response.json()["job_id"]
        poll_response = client.get(f"/inference/video_mask_generation/jobs/{local_job_id}")
        assert poll_response.status_code == 200
        assert poll_response.json()["status"] == "completed"
        assert poll_response.json()["data"]["frame_indexes"] == [2, 3]
        provider.get_video_mask_generation_job.assert_awaited_once_with("provider-job-1")

    def test_cancel_tracking_job_marks_job_canceled(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.submit_video_mask_generation_job = AsyncMock(
            return_value=VideoMaskGenerationJobStatus(
                job_id="provider-job-2",
                status="running",
            )
        )
        provider.cancel_video_mask_generation_job = AsyncMock(
            return_value=VideoMaskGenerationJobStatus(
                job_id="provider-job-2",
                status="canceled",
                detail="Tracking job canceled.",
            )
        )
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, record_id, _, _ = _create_dataset_with_embedded_views(settings.library_dir)

        submit_response = client.post(
            "/inference/video_mask_generation/jobs",
            json={
                "model": "sam2-video",
                "dataset_id": dataset_id,
                "record_id": record_id,
                "view_name": "camera",
                "start_frame_index": 0,
                "frame_count": 1,
                "objects_ids": [7],
                "prompt_frame_indexes": [0],
                "points": [[[4, 4]]],
                "labels": [[1]],
                "propagate": False,
            },
        )

        local_job_id = submit_response.json()["job_id"]
        cancel_response = client.delete(f"/inference/video_mask_generation/jobs/{local_job_id}")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "canceled"
        provider.cancel_video_mask_generation_job.assert_awaited_once_with("provider-job-2")

        poll_response = client.get(f"/inference/video_mask_generation/jobs/{local_job_id}")
        assert poll_response.status_code == 200
        assert poll_response.json()["status"] == "canceled"
        provider.get_video_mask_generation_job.assert_not_called()

    def test_track_video_preserves_upstream_client_error(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.video_mask_generation = AsyncMock(
            side_effect=InferenceRequestError(status_code=400, code="bad_request", message="Invalid binary metadata")
        )
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, record_id, _, _ = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/video_mask_generation",
            json={
                "model": "sam2-video",
                "dataset_id": dataset_id,
                "record_id": record_id,
                "view_name": "camera",
                "start_frame_index": 0,
                "frame_count": 2,
                "objects_ids": [7],
                "prompt_frame_indexes": [1],
            },
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Invalid binary metadata"}


class TestVLM:
    def test_vlm_uses_requested_provider(self):
        default_provider = _make_mock_provider(
            "pixano-inference@127.0.0.1:7463",
            "http://127.0.0.1:7463",
        )
        target_provider = _make_mock_provider(
            "pixano-inference@127.0.0.1:7464",
            "http://127.0.0.1:7464",
        )
        target_provider.vlm = AsyncMock(
            return_value=VLMResult(
                data=VLMOutput(
                    generated_text="A cat on a red mat.",
                    usage=UsageInfo(prompt_tokens=12, completion_tokens=7, total_tokens=19),
                    generation_config={"temperature": 0.2},
                ),
                timestamp=datetime.fromisoformat("2026-03-20T10:10:00"),
                processing_time=0.25,
                metadata={"backend": "mock"},
                id="vlm-1",
                status="SUCCESS",
            )
        )
        client, _ = _make_client(
            inference_providers={
                default_provider.name: default_provider,
                target_provider.name: target_provider,
            },
            default_inference_provider=default_provider.name,
        )

        response = client.post(
            "/inference/vlm",
            json={
                "model": "qwen-vl",
                "provider_name": target_provider.name,
                "prompt": "Describe the image.",
                "images": ["http://example.com/image.jpg"],
            },
        )

        assert response.status_code == 200
        assert response.json()["data"]["generated_text"] == "A cat on a red mat."
        default_provider.vlm.assert_not_called()
        target_provider.vlm.assert_called_once()


class TestDetection:
    def test_detection_uses_default_provider_when_provider_omitted(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.detection = AsyncMock(
            return_value=DetectionResult(
                data=DetectionOutput(
                    boxes=[[0, 0, 10, 10]],
                    scores=[0.91],
                    classes=["cat"],
                ),
                timestamp=datetime.fromisoformat("2026-03-20T10:15:00"),
                processing_time=0.11,
                metadata={"backend": "mock"},
                id="det-1",
                status="SUCCESS",
            )
        )
        client, _ = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )

        response = client.post(
            "/inference/detection",
            json={
                "model": "grounding-dino",
                "image": "http://example.com/image.jpg",
                "classes": ["cat"],
            },
        )

        assert response.status_code == 200
        assert response.json()["data"] == {
            "boxes": [[0, 0, 10, 10]],
            "scores": [0.91],
            "classes": ["cat"],
        }
        provider.detection.assert_called_once()
