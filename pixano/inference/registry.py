# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Provider registration and lookup.

This module provides a registry for inference providers, allowing them to be
registered and retrieved by name.
"""

from typing import Any

from .exceptions import ProviderNotFoundError
from .provider import InferenceProvider


# Global registry of provider classes
_PROVIDERS: dict[str, type[InferenceProvider]] = {}


def register_provider(name: str):
    """Decorator to register a provider class.

    Args:
        name: The name to register the provider under.

    Returns:
        A decorator that registers the class.

    Example:
        ```python
        @register_provider("my-provider")
        class MyProvider(InferenceProvider):
            ...
        ```
    """

    def decorator(cls: type[InferenceProvider]) -> type[InferenceProvider]:
        if not issubclass(cls, InferenceProvider):
            raise TypeError(f"Provider class must be a subclass of InferenceProvider, got {cls}")
        _PROVIDERS[name] = cls
        return cls

    return decorator


def get_provider(name: str, **kwargs: Any) -> InferenceProvider:
    """Get a provider instance by name.

    Args:
        name: The name of the provider to retrieve.
        **kwargs: Arguments to pass to the provider constructor.

    Returns:
        An instance of the requested provider.

    Raises:
        ProviderNotFoundError: If the provider is not registered.

    Example:
        ```python
        provider = get_provider("pixano-inference", url="http://localhost:8000")
        ```
    """
    if name not in _PROVIDERS:
        available = list_providers()
        raise ProviderNotFoundError(f"Unknown provider: '{name}'. Available providers: {available}")
    return _PROVIDERS[name](**kwargs)


def list_providers() -> list[str]:
    """List all registered provider names.

    Returns:
        List of registered provider names.
    """
    return list(_PROVIDERS.keys())


def is_provider_registered(name: str) -> bool:
    """Check if a provider is registered.

    Args:
        name: The provider name to check.

    Returns:
        True if the provider is registered, False otherwise.
    """
    return name in _PROVIDERS
