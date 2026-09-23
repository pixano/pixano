# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import pytest

from pixano.inference.exceptions import ProviderConnectionError
from pixano.inference.providers import PixanoInferenceProvider
from pixano.inference.types import (
    ImageMaskGenerationInput,
    ImageMaskGenerationResult,
    InferenceTask,
    NDArrayData,
    VideoMaskGenerationInput,
    VideoMaskGenerationResult,
)
from tests.e2e.conftest import skip_no_server


pytestmark = [skip_no_server, pytest.mark.e2e]


# ---------------------------------------------------------------------------
# Connection & discovery
# ---------------------------------------------------------------------------


class TestProviderConnection:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_connect_returns_provider(self, inference_url: str):
        prov = await PixanoInferenceProvider.connect(inference_url)
        try:
            assert isinstance(prov, PixanoInferenceProvider)
            assert prov.url == inference_url.rstrip("/")
        finally:
            await prov.close()

    @pytest.mark.asyncio
    async def test_connect_bad_url_raises(self):
        with pytest.raises(ProviderConnectionError):
            await PixanoInferenceProvider.connect("http://localhost:1")

    @pytest.mark.asyncio(loop_scope="session")
    async def test_get_server_info(self, provider: PixanoInferenceProvider):
        info = await provider.get_server_info()
        assert isinstance(info.version, str)
        assert isinstance(info.models, list)
        assert len(info.models) >= 1
        assert isinstance(info.models_to_task, dict)
        assert len(info.models_to_task) >= 1

    @pytest.mark.asyncio(loop_scope="session")
    async def test_list_models_unfiltered(self, provider: PixanoInferenceProvider):
        models = await provider.list_models()
        assert len(models) >= 1
        for m in models:
            assert m.name
            assert m.task

    @pytest.mark.asyncio(loop_scope="session")
    async def test_list_models_filtered(self, provider: PixanoInferenceProvider):
        models = await provider.list_models(task=InferenceTask.MASK_GENERATION)
        assert len(models) >= 1
        for m in models:
            assert m.task == InferenceTask.MASK_GENERATION.value


# ---------------------------------------------------------------------------
# Image mask generation
# ---------------------------------------------------------------------------


class TestImageMaskGeneration:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_point_prompt(
        self,
        provider: PixanoInferenceProvider,
        sam2_model_name: str,
        test_image_base64_png: str,
    ):
        input_data = ImageMaskGenerationInput(
            image=test_image_base64_png,
            model=sam2_model_name,
            points=[[[320, 213]]],
            labels=[[1]],
            multimask_output=True,
        )
        result = await provider.image_mask_generation(input_data, timeout=120.0)

        assert isinstance(result, ImageMaskGenerationResult)
        assert len(result.data.masks) == 1  # 1 prompt
        assert len(result.data.masks[0]) == 3  # multimask -> 3 masks
        for mask in result.data.masks[0]:
            assert len(mask.size) == 2
            assert mask.size[0] > 0 and mask.size[1] > 0
        assert result.data.scores is not None
        assert result.processing_time > 0

    @pytest.mark.asyncio(loop_scope="session")
    async def test_box_prompt(
        self,
        provider: PixanoInferenceProvider,
        sam2_model_name: str,
        test_image_base64_png: str,
    ):
        input_data = ImageMaskGenerationInput(
            image=test_image_base64_png,
            model=sam2_model_name,
            boxes=[[100, 100, 400, 300]],
            multimask_output=False,
        )
        result = await provider.image_mask_generation(input_data, timeout=120.0)

        assert isinstance(result, ImageMaskGenerationResult)
        assert len(result.data.masks) == 1
        assert len(result.data.masks[0]) == 1  # single mask

    @pytest.mark.asyncio(loop_scope="session")
    async def test_point_and_box(
        self,
        provider: PixanoInferenceProvider,
        sam2_model_name: str,
        test_image_base64_jpg: str,
    ):
        input_data = ImageMaskGenerationInput(
            image=test_image_base64_jpg,
            model=sam2_model_name,
            points=[[[293, 320]]],
            labels=[[1]],
            boxes=[[100, 100, 486, 540]],
            multimask_output=False,
        )
        result = await provider.image_mask_generation(input_data, timeout=120.0)

        assert isinstance(result, ImageMaskGenerationResult)
        assert len(result.data.masks) >= 1

    @pytest.mark.asyncio(loop_scope="session")
    async def test_embedding_return(
        self,
        provider: PixanoInferenceProvider,
        sam2_model_name: str,
        test_image_base64_png: str,
    ):
        input_data = ImageMaskGenerationInput(
            image=test_image_base64_png,
            model=sam2_model_name,
            points=[[[320, 213]]],
            labels=[[1]],
            multimask_output=False,
            return_image_embedding=True,
        )
        result = await provider.image_mask_generation(input_data, timeout=120.0)

        assert result.data.image_embedding is not None
        assert isinstance(result.data.image_embedding, NDArrayData)
        assert len(result.data.image_embedding.shape) >= 1
        assert len(result.data.image_embedding.values) > 0


# ---------------------------------------------------------------------------
# Video mask generation
# ---------------------------------------------------------------------------


class TestVideoMaskGeneration:
    @pytest.mark.asyncio(loop_scope="session")
    async def test_video_point_prompt(
        self,
        provider: PixanoInferenceProvider,
        sam2_video_model_name: str,
        test_image_base64_png: str,
    ):
        # Use 3 identical frames to simulate a short video
        frames = [test_image_base64_png] * 3
        input_data = VideoMaskGenerationInput(
            video=frames,
            model=sam2_video_model_name,
            objects_ids=[1],
            frame_indexes=[0],
            points=[[[320, 213]]],
            labels=[[1]],
        )
        result = await provider.video_mask_generation(input_data, timeout=180.0)

        assert isinstance(result, VideoMaskGenerationResult)
        assert result.status == "SUCCESS"
        assert len(result.data.masks) > 0

    @pytest.mark.asyncio(loop_scope="session")
    async def test_video_box_prompt(
        self,
        provider: PixanoInferenceProvider,
        sam2_video_model_name: str,
        test_image_base64_png: str,
    ):
        frames = [test_image_base64_png] * 2
        input_data = VideoMaskGenerationInput(
            video=frames,
            model=sam2_video_model_name,
            objects_ids=[1],
            frame_indexes=[0],
            boxes=[[100, 100, 400, 300]],
        )
        result = await provider.video_mask_generation(input_data, timeout=180.0)

        assert isinstance(result, VideoMaskGenerationResult)
        assert result.status == "SUCCESS"
        assert len(result.data.masks) > 0
        assert len(result.data.frame_indexes) > 0
