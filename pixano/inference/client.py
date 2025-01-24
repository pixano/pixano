# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import re
from typing import Any, Literal

import requests  # type: ignore[import-untyped]
from pixano_inference.pydantic.models import ModelInfo
from pixano_inference.settings import Settings
from pydantic import field_validator
from requests import HTTPError, Response


url_validation_regex = re.compile(  # from Django
    r"^(?:http|ftp)s?://"  # http:// or https://
    r"(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+(?:[A-Z]{2,6}\.?|[A-Z0-9-]{2,}\.?)|"  # domain...
    r"localhost|"  # localhost...
    r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})"  # ...or ip
    r"(?::\d+)?"  # optional port
    r"(?:/?|[/?]\S+)$",
    re.IGNORECASE,
)


class PixanoInferenceClient(Settings):
    """Pixano Inference Client."""

    url: str

    @field_validator("url", mode="after")
    def _validate_url(cls, v):
        if re.match(url_validation_regex, v) is None:
            raise ValueError(f"Invalid URL, got '{v}'.")
        if v.endswith("/"):
            v = v[:-1]
        return v

    @staticmethod
    def connect(url: str) -> "PixanoInferenceClient":
        """Connect to pixano inference.

        Args:
            url: The URL of the pixano inference server.
        """
        settings = Settings.model_validate_json(requests.get(f"{url}/app/settings").json())
        client = PixanoInferenceClient(url=url, **settings.model_dump())
        return client

    def _rest_call(self, path: str, method: Literal["GET", "POST", "PUT", "DELETE"], **kwargs) -> Response:
        """Perform a REST call to the pixano inference server."""
        match method:
            case "GET":
                request_fn = requests.get
            case "POST":
                request_fn = requests.post
            case "PUT":
                request_fn = requests.put
            case "DELETE":
                request_fn = requests.delete
            case _:
                raise ValueError(
                    f"Invalid REST call method. Expected one of ['GET', 'POST', 'PUT', 'DELETE'], but got '{method}'."
                )

        url = f"{self.url}/{path}"
        response = request_fn(url, **kwargs)
        if not response.ok:
            raise HTTPError(response.status_code, f"{response.url} failed: {response.text}.")

        return response

    def get(self, path: str) -> Response:
        """Perform a GET request to the pixano inference server.

        Args:
            path: The path of the request.
        """
        return self._rest_call(path=path, method="GET")

    def post(self, path: str, **kwargs: Any) -> Response:
        """Perform a POST request to the pixano inference server.

        Args:
            path: The path of the request.
            kwargs: The keyword arguments to pass to the request.
        """
        return self._rest_call(path=path, method="POST", **kwargs)

    def put(self, path: str, **kwargs: Any) -> Response:
        """Perform a PUT request to the pixano inference server.

        Args:
            path: The path of the request.
            kwargs: The keyword arguments to pass to the request.
        """
        return self._rest_call(path=path, method="PUT", **kwargs)

    def delete(self, path: str) -> Response:
        """Perform a DELETE request to the pixano inference server.

        Args:
            path: The path of the request.
        """
        return self._rest_call(path=path, method="DELETE")

    def list_models(self) -> list[ModelInfo]:
        """List all models."""
        response = self.get("app/models")
        return [ModelInfo.model_validate(model) for model in response.json()]
