# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import base64
import os
import tempfile
from functools import lru_cache
from pathlib import Path

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.inference.providers import PixanoInferenceProvider
from pixano.inference.types import InferenceTask


ASSETS_DIR = Path(__file__).parent.parent / "assets"
SAMPLE_DATA_DIR = ASSETS_DIR / "sample_data"
COCO_VAL_DIR = ASSETS_DIR / "coco_dataset" / "image" / "val"


skip_no_server = pytest.mark.skipif(
    "PIXANO_INFERENCE_URL" not in os.environ,
    reason="PIXANO_INFERENCE_URL not set — skipping E2E tests",
)


# ---------------------------------------------------------------------------
# Provider fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def inference_url() -> str:
    url = os.environ.get("PIXANO_INFERENCE_URL")
    if url is None:
        pytest.skip("PIXANO_INFERENCE_URL not set")
    return url


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def provider(inference_url: str) -> PixanoInferenceProvider:
    prov = await PixanoInferenceProvider.connect(inference_url)
    yield prov
    await prov.close()


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def sam2_model_name(provider: PixanoInferenceProvider) -> str:
    models = await provider.list_models(task=InferenceTask.MASK_GENERATION)
    if not models:
        pytest.skip("No image mask generation model available on server")
    return models[0].name


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def sam2_video_model_name(provider: PixanoInferenceProvider) -> str:
    """A prompted video tracker (SAM2).

    The server lists prompted and prompt-free trackers under the same task, so the model is picked by
    name (``PIXANO_E2E_SAM2_VIDEO_MODEL``, default ``sam2-video``), falling back to the first one.
    """
    models = await provider.list_models(task=InferenceTask.VIDEO_MASK_GENERATION)
    if not models:
        pytest.skip("No video mask generation model available on server")
    prompted = [model.name for model in models if (model.interface or {}).get("prompts")]
    preferred = os.environ.get("PIXANO_E2E_SAM2_VIDEO_MODEL") or (prompted[0] if prompted else "sam2-video")
    names = [model.name for model in models]
    return preferred if preferred in names else names[0]


@pytest_asyncio.fixture(scope="session", loop_scope="session")
async def tracking_by_detection_model_name(provider: PixanoInferenceProvider) -> str:
    """A prompt-free tracker (YOLO + ByteTrack), named by ``PIXANO_E2E_TRACKING_BY_DETECTION_MODEL``."""
    models = await provider.list_models(task=InferenceTask.VIDEO_MASK_GENERATION)
    prompt_free = [model.name for model in models if (model.interface or {}).get("prompt_free")]
    name = os.environ.get("PIXANO_E2E_TRACKING_BY_DETECTION_MODEL") or (
        prompt_free[0] if prompt_free else "yolo-bytetrack"
    )
    if name not in {model.name for model in models}:
        pytest.skip(f"No tracking-by-detection model '{name}' on server (set PIXANO_E2E_TRACKING_BY_DETECTION_MODEL)")
    return name


# ---------------------------------------------------------------------------
# Image fixtures
# ---------------------------------------------------------------------------


def _encode_image_base64(path: Path) -> str:
    suffix = path.suffix.lower()
    mime = "image/png" if suffix == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{mime};base64,{data}"


@pytest.fixture(scope="session")
def test_image_base64_png() -> str:
    path = COCO_VAL_DIR / "000000000139.png"
    assert path.exists(), f"Test image not found: {path}"
    return _encode_image_base64(path)


@pytest.fixture(scope="session")
def test_image_base64_jpg() -> str:
    path = COCO_VAL_DIR / "000000000285.jpg"
    assert path.exists(), f"Test image not found: {path}"
    return _encode_image_base64(path)


# ---------------------------------------------------------------------------
# Router fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def e2e_app_client(inference_url: str) -> TestClient:
    tmp = tempfile.mkdtemp()
    library_dir = Path(tmp) / "library"
    library_dir.mkdir()
    models_dir = Path(tmp) / "models"
    models_dir.mkdir()

    prov = PixanoInferenceProvider(url=inference_url)

    settings = Settings(
        library_dir=str(library_dir),
        models_dir=str(models_dir),
        inference_providers={"pixano-inference": prov},
        default_inference_provider="pixano-inference",
    )

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override

    return TestClient(app)
