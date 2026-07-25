# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Inference-specific exceptions."""


class InferenceError(Exception):
    """Base exception for inference errors."""

    pass


class ProviderNotFoundError(InferenceError):
    """Raised when a requested provider is not found."""

    pass


class ProviderConnectionError(InferenceError):
    """Raised when connection to a provider fails."""

    pass


class InferenceTimeoutError(InferenceError):
    """Raised when inference takes too long."""

    pass


class ModelNotFoundError(InferenceError):
    """Raised when a requested model is not available."""

    pass


class TaskNotSupportedError(InferenceError):
    """Raised when a task is not supported by the provider."""

    pass


class InvalidRequestError(InferenceError):
    """Raised when the request is invalid."""

    pass


class InferenceRequestError(InferenceError):
    """Raised when the inference server rejects a request.

    Bridges the client's ``PixanoInferenceError`` so the API layer can map a server
    error to an HTTP status without regex-parsing error strings.

    Attributes:
        status_code: HTTP status code returned by the inference server.
        code: Machine-readable error code from the server envelope.
        request_id: Server request id, if provided.
    """

    def __init__(self, status_code: int, code: str, message: object, request_id: str | None = None) -> None:
        """Initialize the error with the server's status code, code, message and request id."""
        self.status_code = status_code
        self.code = code
        self.request_id = request_id
        super().__init__(str(message))
