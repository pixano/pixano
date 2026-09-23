# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The job kinds this worker knows how to run."""

from .base import (
    CONFIRM_MARKER,
    MODEL_TASK_MARKER,
    Chunk,
    JobKind,
    JobParams,
    Outcome,
    QuarantinedItem,
    TransientError,
    media_chunks,
)
from .embeddings import EmbeddingsKind, EmbeddingsParams
from .fake import FakeKind, FakeParams
from .label import LabelKind, LabelParams
from .registry import Registry


def default_registry(inference_url: str = "", api_key: str = "", demo_kinds: bool = False) -> Registry:
    """The registry shipped with this worker.

    The inference URL is handed to the kinds that need it rather than read from the
    environment by each of them: a kind should not have to know about the deployment.

    Args:
        inference_url: The address of the inference server.
        api_key: Its API key, empty if it does not ask for one.
        demo_kinds: Also register `fake` and `label`. They exist to exercise the engine and to
            show it off; they let anyone write anywhere in a dataset, and so have no place in a
            shared deployment (independent review, C1).
    """
    registry = Registry()
    if demo_kinds:
        registry.register(FakeKind())
        registry.register(LabelKind())
    registry.register(EmbeddingsKind(inference_url, api_key))
    return registry


__all__ = [
    "CONFIRM_MARKER",
    "MODEL_TASK_MARKER",
    "Chunk",
    "FakeKind",
    "EmbeddingsKind",
    "EmbeddingsParams",
    "FakeParams",
    "JobKind",
    "JobParams",
    "LabelKind",
    "LabelParams",
    "Outcome",
    "QuarantinedItem",
    "Registry",
    "TransientError",
    "media_chunks",
    "default_registry",
]
