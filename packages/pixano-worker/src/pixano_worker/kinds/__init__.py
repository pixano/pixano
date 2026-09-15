# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Les types de jobs que ce worker sait exécuter."""

from .base import Chunk, JobKind, JobParams
from .fake import FakeKind, FakeParams
from .label import LabelKind, LabelParams
from .registry import Registry


def default_registry() -> Registry:
    """Le registre livré avec ce worker."""
    registry = Registry()
    registry.register(FakeKind())
    registry.register(LabelKind())
    return registry


__all__ = [
    "Chunk",
    "FakeKind",
    "FakeParams",
    "JobKind",
    "JobParams",
    "LabelKind",
    "LabelParams",
    "Registry",
    "default_registry",
]
