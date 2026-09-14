# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Les types de jobs que ce worker sait exécuter."""

from .base import Chunk, JobKind
from .fake import FakeKind, FakeParams
from .registry import Registry


def default_registry() -> Registry:
    """Le registre livré avec ce worker."""
    registry = Registry()
    registry.register(FakeKind())
    return registry


__all__ = ["Chunk", "FakeKind", "FakeParams", "JobKind", "Registry", "default_registry"]
