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
