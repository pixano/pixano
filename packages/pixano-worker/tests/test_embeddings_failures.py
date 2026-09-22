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

import base64
from types import SimpleNamespace
from typing import Any

import httpx
import numpy as np
import pytest
from pixano_inference_client import PixanoInferenceError
from pixano_worker.kinds import EmbeddingsKind, TransientError
from pixano_worker.media import ResolvedMedia

from pixano.inference.media import bytes_to_data_uri


DIM = 4


def _decoded(data_uri: str) -> str:
    """Ce que désignent des octets envoyés ; l'image témoin, un vrai PNG, reste elle-même."""
    if not data_uri.startswith("data:"):
        return data_uri
    raw = base64.b64decode(data_uri.split(",", 1)[1])
    return raw.decode() if raw.startswith(b"/medias/") else "witness"


class _Inference:
    """Une inférence qui refuse tout lot contenant une image désignée comme mauvaise."""

    def __init__(self) -> None:
        self.bad: set[str] = set()
        # Refuser tout chemin, accepter les octets : un serveur qui ne lit pas son montage de médias.
        self.refuses_paths = False
        self.status_for_everything: int | None = None
        self.unreachable = False
        self.transport_error: Exception | None = None
        # Rang de l'appel à partir duquel le serveur ne répond plus : le cas d'un service qui
        # tombe, ou qui oscille en redémarrant, au milieu de la recherche d'une image fautive.
        self.unreachable_from_call: int | None = None
        self.calls: list[list[str]] = []

    def client(self, *_args: Any, **_kwargs: Any) -> "_Inference":
        return self

    def embedding(self, request: Any, **_kwargs: Any) -> Any:
        images = list(request.image)
        self.calls.append(images)
        if self.unreachable or (
            self.unreachable_from_call is not None and len(self.calls) > self.unreachable_from_call
        ):
            # Ce que le client officiel lève réellement : il enveloppe les erreurs de connexion
            # dans une PixanoInferenceError de statut 0. Simuler un httpx.ConnectError, comme le
            # faisait la première version de ce test, laissait passer le défaut en production.
            raise PixanoInferenceError(0, "connection_error", "[Errno 111] Connection refused")
        if self.transport_error is not None:
            raise self.transport_error
        if self.status_for_everything is not None:
            raise PixanoInferenceError(self.status_for_everything, "erreur", "refusé")
        # Une image abîmée l'est aussi en octets : ce que le lecteur simulé donne pour octets
        # d'une image, c'est son chemin, pour que le simulateur la reconnaisse sous les deux formes.
        identities = {_decoded(image) for image in images}
        if self.bad & identities:
            raise PixanoInferenceError(500, "internal_error", "Inference error.")
        if self.refuses_paths and any(not image.startswith("data:") for image in images):
            raise PixanoInferenceError(500, "internal_error", "Inference error.")
        vectors = np.ones((len(images), DIM), dtype=np.float32)
        return SimpleNamespace(data=SimpleNamespace(embeddings=SimpleNamespace(to_numpy=lambda: vectors)))


class _Reader:
    """Un dataset où certains enregistrements n'ont pas d'image, et d'autres une image perdue."""

    def __init__(
        self,
        without_image: set[str] = frozenset(),  # type: ignore[assignment]
        lost: set[str] = frozenset(),  # type: ignore[assignment]
        carried_bytes: bool = False,
    ) -> None:
        self.without_image = without_image
        self.lost = lost
        self.carried_bytes = carried_bytes
        self.dataset = SimpleNamespace(get_data=self._get_data, get_view_binary=self._get_view_binary)

    @staticmethod
    def _get_view_binary(table_name: str, row_id: str) -> tuple[bytes, str]:
        record_id = row_id.removeprefix("img-")
        return f"/medias/{record_id}.jpg".encode(), "image/jpeg"

    def _get_data(self, table_name: str, record_ids: list[str]) -> list[Any]:
        return [
            SimpleNamespace(id=f"img-{r}", record_id=r, uri=f"/medias/{r}.jpg")
            for r in record_ids
            if r not in self.without_image
        ]

    def resolve_media(self, table_name: str, view: Any) -> ResolvedMedia | None:
        if view.record_id in self.lost:
            return None
        if self.carried_bytes:
            return ResolvedMedia(bytes_to_data_uri(view.uri.encode()), carried_bytes=True, reason="octets")
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
        assert [(item.item_id, item.reason) for item in outcome.quarantined] == [("r2", "media not found")]
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

    @pytest.mark.parametrize("code", ["connection_error", "timeout"])
    def test_no_answer_at_all_is_transient(self, inference: _Inference, code: str) -> None:
        """Statut 0 : le client n'a reçu aucune réponse. Aucune image ne peut en être tenue responsable."""
        inference.transport_error = PixanoInferenceError(0, code, "pas de réponse")

        with pytest.raises(TransientError):
            _run(_Reader())

    def test_a_transport_error_the_client_lets_through_is_transient(self, inference: _Inference) -> None:
        """Le client n'enveloppe que trois erreurs httpx ; les autres remontent brutes."""
        inference.transport_error = httpx.RemoteProtocolError("connexion coupée en pleine réponse")

        with pytest.raises(TransientError):
            _run(_Reader())

    def test_an_outage_during_the_search_is_not_blamed_on_the_images(self, inference: _Inference) -> None:
        """Le défaut observé sur la pile réelle, en coupant l'inférence en plein job.

        Un premier appel aboutit, les suivants trouvent la connexion refusée. Sept images
        saines partaient en quarantaine parce que « tout n'avait pas échoué ». On n'accuse une
        image que sur une réponse du serveur, jamais sur son silence.
        """
        inference.bad = {"/medias/r6.jpg"}
        inference.unreachable_from_call = 2

        with pytest.raises(TransientError):
            _run(_Reader())

    @pytest.mark.parametrize("status", [408, 429, 502, 503, 504])
    def test_a_come_back_later_answer_is_transient(self, inference: _Inference, status: int) -> None:
        inference.status_for_everything = status

        with pytest.raises(TransientError, match="revenir plus tard"):
            _run(_Reader())

    def test_a_single_refused_image_is_quarantined_when_the_witness_passes(self, inference: _Inference) -> None:
        """Review de l'étape 1 : un lot d'une image corrompue faisait échouer tout le job.

        Le dernier chunk d'un dataset n'a souvent qu'une image, et sur un dataset lidar la plupart
        des chunks aussi. « Aucune image n'est passée » y était vrai dès la première image
        abîmée : le chunk était rejoué jusqu'à l'échec, et le job finissait en erreur.
        """
        inference.bad = {"/medias/r0.jpg"}

        _, outcome = _run(_Reader(), records=["r0"])

        assert (outcome.produced, [item.item_id for item in outcome.quarantined]) == (0, ["r0"])

    def test_a_single_image_among_records_without_image_is_quarantined_too(self, inference: _Inference) -> None:
        inference.bad = {"/medias/r5.jpg"}

        _, outcome = _run(_Reader(without_image=set(RECORDS) - {"r5"}))

        assert (outcome.produced, outcome.skipped, len(outcome.quarantined)) == (0, 7, 1)


class TestWitness:
    """Revue d'architecture, point 3 : sur un lot entièrement refusé, c'est le serveur qui départage.

    Une image témoin générée, envoyée en octets : refusée, le serveur ne va pas bien ; acceptée,
    les images sont en cause — sauf si le serveur ne lit pas les chemins qu'on lui donne.
    """

    @staticmethod
    def _witness_calls(inference: _Inference) -> list[list[str]]:
        return [call for call in inference.calls if len(call) == 1 and _decoded(call[0]) == "witness"]

    def test_a_whole_batch_of_bad_images_is_quarantined_when_the_witness_passes(self, inference: _Inference) -> None:
        """Ce que le seuil d'avant prenait pour une panne : huit images abîmées, un serveur qui va bien."""
        inference.bad = {f"/medias/{r}.jpg" for r in RECORDS}

        _, outcome = _run(_Reader())

        assert (outcome.produced, len(outcome.quarantined)) == (0, 8)
        assert len(self._witness_calls(inference)) == 1

    def test_a_server_refusing_the_witness_is_presumed_down(self, inference: _Inference) -> None:
        inference.status_for_everything = 500

        with pytest.raises(TransientError, match="image témoin"):
            _run(_Reader())

    def test_the_witness_is_not_sent_when_something_embedded(self, inference: _Inference) -> None:
        inference.bad = {"/medias/r0.jpg"}

        _run(_Reader())

        assert self._witness_calls(inference) == []

    def test_a_server_that_cannot_read_its_media_mount_is_told_apart_from_bad_images(
        self, inference: _Inference
    ) -> None:
        """Le témoin passe, les chemins sont tous refusés, la même image passe en octets : c'est le montage."""
        inference.refuses_paths = True

        with pytest.raises(TransientError, match="ne lit pas le stockage des médias"):
            _run(_Reader())

    def test_images_sent_as_bytes_are_not_resent(self, inference: _Inference) -> None:
        """Rien à renvoyer : elles ont déjà voyagé en octets, le refus est le leur."""
        inference.bad = {f"/medias/{r}.jpg" for r in RECORDS}

        _, outcome = _run(_Reader(carried_bytes=True))

        assert len(outcome.quarantined) == 8
        single = [call for call in inference.calls if len(call) == 1 and _decoded(call[0]) != "witness"]
        assert len(single) == 8, "les huit isolements, et aucun renvoi"


class TestFatalFailures:
    @pytest.mark.parametrize("status", [401, 403, 404])
    def test_an_error_no_image_could_cause_is_fatal(self, inference: _Inference, status: int) -> None:
        """Un modèle inconnu ou un accès refusé : découper le lot n'y changerait rien."""
        inference.status_for_everything = status

        with pytest.raises(PixanoInferenceError):
            _run(_Reader())

        assert len(inference.calls) == 1, "aucune recherche de coupable pour une erreur qui ne dépend d'aucune image"


class TestModelOfTheExistingTable:
    """Refusé à la planification, avant que l'inférence tourne sur tout le dataset."""

    class _PlanningReader:
        def __init__(self, space: dict[str, Any] | None) -> None:
            self.dataset = SimpleNamespace(record_embedding_space=lambda: space)

        def ids(self, table_name: str) -> list[str]:
            return RECORDS

    def test_a_dataset_without_embeddings_accepts_any_model(self) -> None:
        chunks = list(KIND.plan(self._PlanningReader(None), PARAMS))  # type: ignore[arg-type]

        assert sum(chunk.task_count for chunk in chunks) == len(RECORDS)

    def test_the_same_model_is_planned(self) -> None:
        reader = self._PlanningReader({"model_id": "clip", "dim": 512})

        assert list(KIND.plan(reader, PARAMS))  # type: ignore[arg-type]

    def test_another_model_fails_the_planning(self) -> None:
        reader = self._PlanningReader({"model_id": "dinov2", "dim": 512})

        with pytest.raises(ValueError, match="dinov2"):
            list(KIND.plan(reader, PARAMS))  # type: ignore[arg-type]
