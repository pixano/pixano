# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================


from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Body, Depends, HTTPException

from pixano.app.settings import Settings, get_settings
from pixano.inference import (
    InferenceProvider,
    PixanoInferenceProvider,
    ProviderConnectionError,
    get_provider,
    list_providers,
)

from . import conditional_generation, mask_generation, models, zero_shot_detection


router = APIRouter(prefix="/inference", tags=["Inference"])
router.include_router(conditional_generation.router)
router.include_router(models.router)
router.include_router(zero_shot_detection.router)
router.include_router(mask_generation.router)


@router.get("/status")
async def get_inference_status(settings: Annotated[Settings, Depends(get_settings)]):
    """Get current inference connection status."""
    providers = [
        {"name": name, "url": provider.url if hasattr(provider, "url") else None}
        for name, provider in settings.inference_providers.items()
    ]
    return {
        "connected": len(providers) > 0,
        "providers": providers,
        "default": settings.default_inference_provider,
    }


def _provider_key(provider: InferenceProvider, url: str) -> str:
    """Derive a unique key for a provider from its name and URL."""
    parsed = urlparse(url)
    return f"{provider.name}@{parsed.hostname}:{parsed.port or 80}"


@router.post("/connect")
async def connect_inference(
    url: str,
    settings: Annotated[Settings, Depends(get_settings)],
    provider_type: Annotated[str, Body(embed=True)] = "pixano-inference",
) -> dict[str, str]:
    """Connect to an inference provider.

    Args:
        url: The URL of the inference server.
        settings: App settings.
        provider_type: The type of provider to connect to (default: "pixano-inference").

    Returns:
        A dict with status and provider name.

    Raises:
        HTTPException: If connection fails.
    """
    # Check if a provider with this URL is already connected
    for key, existing in settings.inference_providers.items():
        if hasattr(existing, "url") and existing.url.rstrip("/") == url.rstrip("/"):
            return {"status": "already_connected", "provider": key}

    provider: InferenceProvider
    try:
        if provider_type == "pixano-inference":
            # Use the specialized connect method for pixano-inference
            provider = await PixanoInferenceProvider.connect(url)
        else:
            # Generic provider instantiation
            provider = get_provider(provider_type, url=url)
    except ProviderConnectionError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=404, detail=f"Failed to connect to {provider_type} at {url}: {e}")

    # Derive unique key from provider name + URL to avoid collisions
    provider_key = _provider_key(provider, url)
    settings.inference_providers[provider_key] = provider

    # Set as default if no default is set
    if settings.default_inference_provider is None:
        settings.default_inference_provider = provider_key

    return {"status": "connected", "provider": provider_key}


@router.get("/providers")
async def list_available_providers() -> list[str]:
    """List available provider types that can be connected to."""
    return list_providers()


@router.get("/connected")
async def list_connected_providers(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, list[str] | str | None]:
    """List currently connected providers."""
    return {
        "providers": list(settings.inference_providers.keys()),
        "default": settings.default_inference_provider,
    }


@router.post("/disconnect/{provider_name}")
async def disconnect_provider(
    provider_name: str,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    """Disconnect from an inference provider.

    Args:
        provider_name: Name of the provider to disconnect.
        settings: App settings.

    Returns:
        A dict with status.

    Raises:
        HTTPException: If provider is not connected.
    """
    if provider_name not in settings.inference_providers:
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' is not connected")

    provider = settings.inference_providers.pop(provider_name)

    # Close the provider if it has a close method
    if hasattr(provider, "close"):
        await provider.close()

    # Update default if necessary
    if settings.default_inference_provider == provider_name:
        if settings.inference_providers:
            settings.default_inference_provider = next(iter(settings.inference_providers.keys()))
        else:
            settings.default_inference_provider = None

    return {"status": "disconnected", "provider": provider_name}


__all__ = ["router"]
