# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Ce que le type d'embeddings fait de chaque famille d'échec.

L'inférence est simulée, et c'est ce qui rend ces cas reproductibles : une image corrompue,
un chemin absent, un service qui redémarre. La simulation reprend ce que l'inférence réelle
répond — mesuré, pas supposé : un 500 `internal_error` pour une image corrompue comme pour
un chemin absent, et pour le lot entier dès qu'une seule image y est mauvaise.
"""

from types import SimpleNamespace
from typing import Any

import httpx
import numpy as np
import pytest
from pixano_inference_client import PixanoInferenceError
from pixano_worker.kinds import EmbeddingsKind, TransientError
from pixano_worker.media import ResolvedMedia


DIM = 4


class _Inference:
    """Une inférence qui refuse tout lot contenant une image désignée comme mauvaise."""

    def __init__(self) -> None:
        self.bad: set[str] = set()
        self.status_for_everything: int | None = None
        self.unreachable = False
        self.calls: list[list[str]] = []

    def client(self, *_args: Any, **_kwargs: Any) -> "_Inference":
        return self

    def embedding(self, request: Any, **_kwargs: Any) -> Any:
        images = list(request.image)
        self.calls.append(images)
        if self.unreachable:
            raise httpx.ConnectError("connexion refusée")
        if self.status_for_everything is not None:
            raise PixanoInferenceError(self.status_for_everything, "erreur", "refusé")
        if self.bad & set(images):
            raise PixanoInferenceError(500, "internal_error", "Inference error.")
        vectors = np.ones((len(images), DIM), dtype=np.float32)
        return SimpleNamespace(data=SimpleNamespace(embeddings=SimpleNamespace(to_numpy=lambda: vectors)))


class _Reader:
    """Un dataset où certains enregistrements n'ont pas d'image, et d'autres une image perdue."""

    def __init__(self, without_image: set[str] = frozenset(), lost: set[str] = frozenset()) -> None:  # type: ignore[assignment]
        self.without_image = without_image
        self.lost = lost
        self.dataset = SimpleNamespace(get_data=self._get_data)

    def _get_data(self, table_name: str, record_ids: list[str]) -> list[Any]:
        return [
            SimpleNamespace(id=f"img-{r}", record_id=r, uri=f"/medias/{r}.jpg")
            for r in record_ids
            if r not in self.without_image
        ]

    def resolve_media(self, table_name: str, view: Any) -> ResolvedMedia | None:
        if view.record_id in self.lost:
            return None
        return ResolvedMedia(view.uri, carried_bytes=False, reason="chemin")


@pytest.fixture
def inference(monkeypatch: pytest.MonkeyPatch) -> _Inference:
    fake = _Inference()
    monkeypatch.setattr("pixano_worker.kinds.embeddings.SyncPixanoInferenceClient", fake.client)
    return fake


KIND = EmbeddingsKind("http://inference", "")
PARAMS = KIND.validate_params({"model": "clip"})
RECORDS = [f"r{i}" for i in range(8)]


def _run(reader: _Reader, records: list[str] = RECORDS) -> tuple[dict[str, Any], Any]:
    payload = {"record_ids": records}
    result = KIND.process(reader, payload, PARAMS)  # type: ignore[arg-type]
    return result, KIND.outcome(result, payload, len(records))


class TestItemFailures:
    def test_one_corrupt_image_costs_only_itself(self, inference: _Inference) -> None:
        """Le cœur de la quarantaine : les sept autres images du lot sont sauvées."""
        inference.bad = {"/medias/r5.jpg"}

        result, outcome = _run(_Reader())

        assert outcome.produced == 7
        assert [item.item_id for item in outcome.quarantined] == ["r5"]
        assert outcome.quarantined[0].detail == {
            "status": 500,
            "code": "internal_error",
            "message": "Inference error.",
        }
        assert "r5" not in result["record_ids"]

    def test_several_corrupt_images_are_all_isolated(self, inference: _Inference) -> None:
        inference.bad = {"/medias/r0.jpg", "/medias/r7.jpg"}

        _, outcome = _run(_Reader())

        assert outcome.produced == 6
        assert sorted(item.item_id for item in outcome.quarantined) == ["r0", "r7"]

    def test_a_healthy_batch_costs_a_single_call(self, inference: _Inference) -> None:
        """La recherche du coupable ne coûte rien le jour où il n'y en a pas."""
        _run(_Reader())

        assert len(inference.calls) == 1

    def test_a_lost_image_is_quarantined_without_calling_inference(self, inference: _Inference) -> None:
        _, outcome = _run(_Reader(lost={"r2"}))

        assert outcome.produced == 7
        assert [(item.item_id, item.reason) for item in outcome.quarantined] == [("r2", "média introuvable")]
        assert "/medias/r2.jpg" not in inference.calls[0]


class TestSkipped:
    def test_a_record_without_image_is_skipped_not_quarantined(self, inference: _Inference) -> None:
        """Le cas nuScenes : un relevé lidar sans caméra n'est pas une erreur."""
        _, outcome = _run(_Reader(without_image={"r1", "r3", "r4"}))

        assert (outcome.produced, outcome.skipped, outcome.quarantined) == (5, 3, [])

    def test_a_chunk_without_any_image_calls_nothing(self, inference: _Inference) -> None:
        _, outcome = _run(_Reader(without_image=set(RECORDS)))

        assert (outcome.produced, outcome.skipped) == (0, 8)
        assert inference.calls == []


class TestTransientFailures:
    def test_an_unreachable_inference_is_transient(self, inference: _Inference) -> None:
        inference.unreachable = True

        with pytest.raises(TransientError, match="ne répond pas"):
            _run(_Reader())

    @pytest.mark.parametrize("status", [408, 429, 502, 503, 504])
    def test_a_come_back_later_answer_is_transient(self, inference: _Inference, status: int) -> None:
        inference.status_for_everything = status

        with pytest.raises(TransientError, match="revenir plus tard"):
            _run(_Reader())

    def test_an_inference_refusing_every_image_is_presumed_down(self, inference: _Inference) -> None:
        """Toutes les images refusées une à une : une panne est bien plus probable qu'un lot entièrement corrompu."""
        inference.bad = {f"/medias/{r}.jpg" for r in RECORDS}

        with pytest.raises(TransientError, match="refuse les 8"):
            _run(_Reader())


class TestFatalFailures:
    @pytest.mark.parametrize("status", [401, 403, 404])
    def test_an_error_no_image_could_cause_is_fatal(self, inference: _Inference, status: int) -> None:
        """Un modèle inconnu ou un accès refusé : découper le lot n'y changerait rien."""
        inference.status_for_everything = status

        with pytest.raises(PixanoInferenceError):
            _run(_Reader())

        assert len(inference.calls) == 1, "aucune recherche de coupable pour une erreur qui ne dépend d'aucune image"
