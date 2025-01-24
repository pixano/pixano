# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


import re

import pytest
import responses
from pixano_inference.pydantic import ModelInfo
from pixano_inference.settings import Settings
from requests import HTTPError

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
    @pytest.mark.parametrize("method", ["GET", "POST", "PUT", "DELETE"])
    def test_valid_rest_call(self, simple_pixano_inference_client, method):
        data = {"image_url": "https://example.com/image.jpg"}
        response = responses.Response(
            method=f"{method}",
            url=f"{URL}/data/",
            json=data,
            status=201,
        )
        responses.add(response)
        output_response = simple_pixano_inference_client._rest_call("data/", method)
        assert output_response.status_code == 201
        assert output_response.json() == data

    @responses.activate
    def test_invalid_rest_call(self, simple_pixano_inference_client):
        with pytest.raises(
            ValueError,
            match=re.escape(
                r"Invalid REST call method. Expected one of ['GET', 'POST', 'PUT', 'DELETE'], "
                r"but got 'WRONG_METHOD'."
            ),
        ):
            simple_pixano_inference_client._rest_call("data/", "WRONG_METHOD")

        responses.add(
            responses.Response(
                method="POST",
                url=f"{URL}/data/",
                json={
                    "error": "Invalid data.",
                },
                status=400,
            )
        )
        with pytest.raises(
            HTTPError, match=re.escape(f'[Errno 400] {URL}/data/ failed: {{"error": "Invalid data."}}.')
        ) as exc_info:
            simple_pixano_inference_client._rest_call("data/", "POST")
            assert exc_info.value.status_code == 400
            assert exc_info.value.response.json() == {
                "error": "Invalid data.",
            }

    @responses.activate
    def test_get(self, simple_pixano_inference_client):
        data = {"image_url": "https://example.com/image.jpg"}
        response = responses.Response(
            method="GET",
            url=f"{URL}/data/",
            json=data,
            status=200,
        )
        responses.add(response)
        assert simple_pixano_inference_client.get("data/").json() == data

    @responses.activate
    def test_post(self, simple_pixano_inference_client):
        data = {"image_url": "https://example.com/image.jpg"}
        response = responses.Response(
            method="POST",
            url=f"{URL}/data/",
            json=data,
            status=201,
        )
        responses.add(response)
        assert simple_pixano_inference_client.post("data/", json=data).json() == data

    @responses.activate
    def test_put(self, simple_pixano_inference_client):
        data = {"image_url": "https://example.com/image.jpg"}
        response = responses.Response(
            method="PUT",
            url=f"{URL}/data/",
            json=data,
            status=201,
        )
        responses.add(response)
        assert simple_pixano_inference_client.put("data/", json=data).json() == data

    @responses.activate
    def test_delete(self, simple_pixano_inference_client):
        response = responses.Response(method="DELETE", url=f"{URL}/data/", status=204)
        responses.add(response)
        assert simple_pixano_inference_client.delete("data/").status_code == 204

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
