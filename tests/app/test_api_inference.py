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
from pixano.inference.exceptions import InferenceError
from pixano.inference.provider import InferenceProvider
from pixano.inference.providers.pixano_inference import PixanoInferenceProvider
from pixano.inference.types import (
    CompressedRLEData,
    DetectionOutput,
    DetectionResult,
    ModelInfo,
    NDArrayData,
    SegmentationInput,
    SegmentationOutput,
    SegmentationResult,
    ServerInfo,
    TrackingInput,
    TrackingJobStatus,
    TrackingOutput,
    TrackingResult,
    UsageInfo,
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
            app_name="Pixano Inference",
            app_version="1.2.3",
            app_description="Mock inference server",
            num_cpus=8,
            num_gpus=1,
            num_nodes=1,
            gpus_used=1.0,
            gpu_to_model={"0": "sam2"},
            models=["sam2", "sam2-video", "qwen-vl"],
            models_to_capability={"sam2": "segmentation", "sam2-video": "tracking", "qwen-vl": "vlm"},
        )
    )
    provider.list_models = AsyncMock(return_value=[])
    provider.vlm = AsyncMock()
    provider.segmentation = AsyncMock()
    provider.tracking = AsyncMock()
    provider.submit_tracking_job = AsyncMock()
    provider.get_tracking_job = AsyncMock()
    provider.cancel_tracking_job = AsyncMock()
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
    def test_list_servers_returns_empty_registry(self):
        client, _ = _make_client()

        response = client.get("/app/inference/servers/")

        assert response.status_code == 200
        assert response.json() == {
            "connected": False,
            "providers": [],
            "default_provider": None,
        }

    def test_list_servers_returns_seeded_provider(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        client, _ = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )

        response = client.get("/app/inference/servers/")

        assert response.status_code == 200
        assert response.json() == {
            "connected": True,
            "providers": [{"name": provider.name, "url": "http://127.0.0.1:7463"}],
            "default_provider": provider.name,
        }

    def test_register_server_adds_provider(self):
        client, settings = _make_client()
        provider = _make_mock_provider("pixano-inference", "http://127.0.0.1:7463")

        with patch(
            "pixano.api.routers.inference.PixanoInferenceProvider.connect",
            AsyncMock(return_value=provider),
        ) as connect_mock:
            response = client.post(
                "/app/inference/servers/",
                json={"url": "http://127.0.0.1:7463 "},
            )

        assert response.status_code == 200
        assert response.json() == {
            "status": "ok",
            "provider": {
                "name": "pixano-inference@127.0.0.1:7463",
                "url": "http://127.0.0.1:7463",
            },
            "default_provider": "pixano-inference@127.0.0.1:7463",
        }
        connect_mock.assert_awaited_once_with("http://127.0.0.1:7463")
        assert "pixano-inference@127.0.0.1:7463" in settings.inference_providers
        assert settings.default_inference_provider == "pixano-inference@127.0.0.1:7463"


class TestInferenceModels:
    def test_list_models_aggregates_providers(self):
        provider_a = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider_b = _make_mock_provider("pixano-inference@127.0.0.1:7464", "http://127.0.0.1:7464")
        provider_a.list_models = AsyncMock(
            return_value=[
                ModelInfo(
                    name="sam2",
                    capability="segmentation",
                    model_path="facebook/sam2-hiera-tiny",
                    model_class="SAM2",
                )
            ]
        )
        provider_b.list_models = AsyncMock(
            return_value=[
                ModelInfo(
                    name="qwen-vl",
                    capability="vlm",
                    model_path="Qwen/Qwen2.5-VL-3B-Instruct",
                    model_class="QwenVL",
                )
            ]
        )
        client, _ = _make_client(
            inference_providers={provider_a.name: provider_a, provider_b.name: provider_b},
            default_inference_provider=provider_a.name,
        )

        response = client.get("/app/inference/models/")

        assert response.status_code == 200
        assert response.json() == [
            {
                "name": "sam2",
                "task": "segmentation",
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
    def test_old_runtime_management_routes_are_not_exposed(self):
        client, _ = _make_client()

        for method, path in (
            ("get", "/app/settings/"),
            ("get", "/app/models/"),
            ("get", "/inference/status"),
            ("post", "/inference/connect?url=http://127.0.0.1:7463"),
            ("get", "/inference/models/list"),
            ("get", "/inference/models/list-all"),
            ("post", "/inference/models/instantiate"),
            ("delete", "/inference/models/delete/sam2"),
            ("post", "/inference/tasks/segmentation/image"),
            ("post", "/inference/tasks/tracking/video"),
            ("post", "/inference/tasks/conditional_generation/text-image"),
        ):
            response = getattr(client, method)(path)
            assert response.status_code == 404


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
        target_provider.segmentation = AsyncMock(
            return_value=SegmentationResult(
                data=SegmentationOutput(
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
            "/inference/segmentation",
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
        default_provider.segmentation.assert_not_called()
        target_provider.segmentation.assert_called_once()
        input_data = target_provider.segmentation.await_args.kwargs["input_data"]
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
            "/inference/segmentation",
            json={
                "model": "sam2",
                "dataset_id": dataset_id,
                "view_id": "missing-view",
            },
        )

        assert response.status_code == 404
        provider.segmentation.assert_not_called()

    def test_segment_image_preserves_upstream_client_error(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.segmentation = AsyncMock(
            side_effect=InferenceError("HTTP 400: Bad Request - Part exceeded maximum size of 1024KB.")
        )
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, _, view_id, _ = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/segmentation",
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
                    capability="tracking",
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
            "/inference/segmentation",
            json={
                "model": "sam2-video",
                "dataset_id": dataset_id,
                "view_id": view_id,
            },
        )

        assert response.status_code == 400
        assert response.json() == {"detail": "Model 'sam2-video' is tracking-only; use /inference/tracking"}
        provider.segmentation.assert_not_called()


class TestVideoTracking:
    def test_track_video_uses_default_provider(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.tracking = AsyncMock(
            return_value=TrackingResult(
                data=TrackingOutput(
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
            "/inference/tracking",
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
        provider.tracking.assert_called_once()
        input_data = provider.tracking.await_args.kwargs["input_data"]
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
            "/inference/tracking",
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
        provider.tracking.assert_not_called()

    def test_track_video_serializes_interval_keyframes(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.tracking = AsyncMock(
            return_value=TrackingResult(
                data=TrackingOutput(
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
            "/inference/tracking",
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
        provider.tracking.assert_called_once()
        input_data = provider.tracking.await_args.kwargs["input_data"]
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
        provider.tracking = AsyncMock(
            return_value=TrackingResult(
                data=TrackingOutput(
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
            "/inference/tracking",
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
        provider.tracking.assert_called_once()
        input_data = provider.tracking.await_args.kwargs["input_data"]
        assert input_data.frame_indexes == [0]
        assert input_data.propagate is False
        assert len(input_data.video) == 1

    def test_submit_tracking_job_stores_local_job_and_remaps_completed_frames(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.submit_tracking_job = AsyncMock(
            return_value=TrackingJobStatus(
                job_id="provider-job-1",
                status="running",
            )
        )
        provider.get_tracking_job = AsyncMock(
            return_value=TrackingJobStatus(
                job_id="provider-job-1",
                status="completed",
                data=TrackingOutput(
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
            "/inference/tracking/jobs",
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
        provider.submit_tracking_job.assert_called_once()
        input_data = provider.submit_tracking_job.await_args.kwargs["input_data"]
        assert input_data.frame_indexes == [0]
        assert input_data.propagate is False

        local_job_id = submit_response.json()["job_id"]
        poll_response = client.get(f"/inference/tracking/jobs/{local_job_id}")
        assert poll_response.status_code == 200
        assert poll_response.json()["status"] == "completed"
        assert poll_response.json()["data"]["frame_indexes"] == [2, 3]
        provider.get_tracking_job.assert_awaited_once_with("provider-job-1")

    def test_cancel_tracking_job_marks_job_canceled(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.submit_tracking_job = AsyncMock(
            return_value=TrackingJobStatus(
                job_id="provider-job-2",
                status="running",
            )
        )
        provider.cancel_tracking_job = AsyncMock(
            return_value=TrackingJobStatus(
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
            "/inference/tracking/jobs",
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
        cancel_response = client.delete(f"/inference/tracking/jobs/{local_job_id}")
        assert cancel_response.status_code == 200
        assert cancel_response.json()["status"] == "canceled"
        provider.cancel_tracking_job.assert_awaited_once_with("provider-job-2")

        poll_response = client.get(f"/inference/tracking/jobs/{local_job_id}")
        assert poll_response.status_code == 200
        assert poll_response.json()["status"] == "canceled"
        provider.get_tracking_job.assert_not_called()

    def test_track_video_preserves_upstream_client_error(self):
        provider = _make_mock_provider("pixano-inference@127.0.0.1:7463", "http://127.0.0.1:7463")
        provider.tracking = AsyncMock(side_effect=InferenceError("HTTP 400: Bad Request - Invalid binary metadata"))
        client, settings = _make_client(
            inference_providers={provider.name: provider},
            default_inference_provider=provider.name,
        )
        dataset_id, record_id, _, _ = _create_dataset_with_embedded_views(settings.library_dir)

        response = client.post(
            "/inference/tracking",
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


class TestPixanoInferenceProviderBinaryRequests:
    def test_binary_segmentation_request_sends_metadata_as_json_file_part(self):
        provider = PixanoInferenceProvider("http://127.0.0.1:7463")

        files = provider._build_binary_segmentation_request(  # noqa: SLF001 - testing request builder contract
            SegmentationInput(
                model="sam2",
                image=b"image-bytes",
                high_resolution_features=[NDArrayData(values=[0.5], shape=[1, 1])],
                mask_input=NDArrayData(values=[0.1, 0.2, 0.3, 0.4], shape=[1, 2, 2]),
                return_logits=True,
            )
        )

        metadata_part = files[0]
        assert metadata_part[0] == "metadata"
        assert metadata_part[1][0] == "metadata.json"
        assert metadata_part[1][2] == "application/json"

    def test_binary_tracking_request_sends_metadata_as_json_file_part(self):
        provider = PixanoInferenceProvider("http://127.0.0.1:7463")

        files = provider._build_binary_tracking_request(  # noqa: SLF001 - testing request builder contract
            TrackingInput(
                model="sam2-video",
                video=[b"frame-0", b"frame-1"],
                objects_ids=[1],
                frame_indexes=[0],
                propagate=False,
            )
        )

        metadata_part = files[0]
        assert metadata_part[0] == "metadata"
        assert metadata_part[1][0] == "metadata.json"
        assert metadata_part[1][2] == "application/json"
        assert json.loads(metadata_part[1][1])["propagate"] is False


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
