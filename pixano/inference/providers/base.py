# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from abc import abstractmethod
from typing import Any, Literal

import httpx

from ..exceptions import InferenceError, ProviderConnectionError
from ..provider import InferenceProvider


class HTTPProvider(InferenceProvider):
    """Base class for HTTP-based inference providers.

    This class provides common HTTP client functionality that can be
    shared by providers that communicate over HTTP.

    Attributes:
        url: The base URL of the inference server.
    """

    def __init__(self, url: str):
        """Initialize the HTTP provider.

        Args:
            url: The base URL of the inference server.
        """
        self._url = url.rstrip("/")
        self._client: httpx.AsyncClient | None = None

    @property
    def url(self) -> str:
        """The base URL of the inference server."""
        return self._url

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=httpx.Timeout(120.0))
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def _request(
        self,
        method: Literal["GET", "POST", "PUT", "DELETE"],
        path: str,
        timeout: int | float = 60,
        **kwargs: Any,
    ) -> httpx.Response:
        """Perform an HTTP request.

        Args:
            method: HTTP method to use.
            path: URL path (relative to base URL).
            timeout: Request timeout in seconds.
            **kwargs: Additional arguments to pass to httpx.

        Returns:
            The HTTP response.

        Raises:
            ProviderConnectionError: If the request fails.
            InferenceError: If the server returns an error.
        """
        client = await self._get_client()

        if path.startswith("/"):
            path = path[1:]

        url = f"{self._url}/{path}"

        try:
            match method:
                case "GET":
                    response = await client.get(url, timeout=timeout, **kwargs)
                case "POST":
                    response = await client.post(url, timeout=timeout, **kwargs)
                case "PUT":
                    response = await client.put(url, timeout=timeout, **kwargs)
                case "DELETE":
                    response = await client.delete(url, timeout=timeout, **kwargs)
                case _:
                    raise ValueError(f"Unsupported HTTP method: {method}")

            self._raise_for_status(response)
            return response

        except httpx.ConnectError as e:
            raise ProviderConnectionError(f"Failed to connect to {url}: {e}") from e
        except httpx.TimeoutException as e:
            raise ProviderConnectionError(f"Request to {url} timed out: {e}") from e

    def _raise_for_status(self, response: httpx.Response) -> None:
        """Raise an exception if the response indicates an error.

        Args:
            response: The HTTP response to check.

        Raises:
            InferenceError: If the response indicates an error.
        """
        if response.is_success:
            return

        error_msg = f"HTTP {response.status_code}: {response.reason_phrase}"
        try:
            json_response = response.json()
            if "detail" in json_response:
                error_msg += f" - {json_response['detail']}"
            if "error" in json_response:
                error_msg += f" - {json_response['error']}"
        except Exception:
            pass

        raise InferenceError(error_msg)

    async def get(self, path: str, timeout: int | float = 60, **kwargs: Any) -> httpx.Response:
        """Perform a GET request.

        Args:
            path: URL path.
            timeout: Request timeout.
            **kwargs: Additional request arguments.

        Returns:
            The HTTP response.
        """
        return await self._request("GET", path, timeout=timeout, **kwargs)

    async def post(self, path: str, timeout: int | float = 60, **kwargs: Any) -> httpx.Response:
        """Perform a POST request.

        Args:
            path: URL path.
            timeout: Request timeout.
            **kwargs: Additional request arguments.

        Returns:
            The HTTP response.
        """
        return await self._request("POST", path, timeout=timeout, **kwargs)

    async def put(self, path: str, timeout: int | float = 60, **kwargs: Any) -> httpx.Response:
        """Perform a PUT request.

        Args:
            path: URL path.
            timeout: Request timeout.
            **kwargs: Additional request arguments.

        Returns:
            The HTTP response.
        """
        return await self._request("PUT", path, timeout=timeout, **kwargs)

    async def delete(self, path: str, timeout: int | float = 60, **kwargs: Any) -> httpx.Response:
        """Perform a DELETE request.

        Args:
            path: URL path.
            timeout: Request timeout.
            **kwargs: Additional request arguments.

        Returns:
            The HTTP response.
        """
        return await self._request("DELETE", path, timeout=timeout, **kwargs)

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider name."""
        ...
