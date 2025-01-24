# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import pytest
import responses
from pixano_inference.pydantic import ModelInfo
from pixano_inference.settings import Settings

from pixano.inference import PixanoInferenceClient


URL = "http://localhost:8081"


class TestPixanoInferenceClient:
    def test_init_client(self):
        client = PixanoInferenceClient(url=URL)
        assert client.url == URL

        client = PixanoInferenceClient(url=f"{URL}/")
        assert client.url == URL

        with pytest.raises(ValueError, match="Invalid URL, got 'wrongurl'."):
            client = PixanoInferenceClient(url="wrongurl")

    @responses.activate
    def test_connect(self):
        settings = Settings(num_cpus=1, num_gpus=0)
        response = responses.Response(
            method="GET", url=f"{URL}/app/settings", json=settings.model_dump_json(), status=200
        )
        responses.add(response)
        expected_output = settings.model_dump()
        expected_output.update({"url": URL})

        client = PixanoInferenceClient.connect(URL)
        assert client.model_dump() == expected_output

    @responses.activate
    def test_list_models(self, simple_pixano_inference_client):
        models_info = [
            ModelInfo(**{"name": "sam", "provider": "transformers", "task": "image_mask_generation"}),
            ModelInfo(**{"name": "sam2", "provider": "sam2", "task": "video_mask_generation"}),
        ]
        response = responses.Response(
            method="GET", url=f"{URL}/app/models", json=[m.model_dump() for m in models_info], status=200
        )
        responses.add(response)

        assert simple_pixano_inference_client.list_models() == models_info
