# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Les types de jobs que ce worker sait exécuter."""

from .base import Chunk, JobKind, JobParams, Outcome, QuarantinedItem, TransientError
from .embeddings import EmbeddingsKind, EmbeddingsParams
from .fake import FakeKind, FakeParams
from .label import LabelKind, LabelParams
from .registry import Registry


def default_registry(inference_url: str = "", api_key: str = "", demo_kinds: bool = False) -> Registry:
    """Le registre livré avec ce worker.

    L'URL d'inférence est passée aux types qui en ont besoin plutôt que lue dans
    l'environnement par chacun : un type ne doit pas avoir à connaître le déploiement.

    Args:
        inference_url: L'adresse du serveur d'inférence.
        api_key: Sa clé d'API, vide s'il n'en demande pas.
        demo_kinds: Enregistrer aussi `fake` et `label`. Ils existent pour éprouver le moteur
            et le montrer ; ils laissent écrire n'importe où dans un dataset, et n'ont donc pas
            leur place dans un déploiement partagé (revue indépendante, C1).
    """
    registry = Registry()
    if demo_kinds:
        registry.register(FakeKind())
        registry.register(LabelKind())
    registry.register(EmbeddingsKind(inference_url, api_key))
    return registry


__all__ = [
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
    "default_registry",
]
