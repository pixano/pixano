# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What the embeddings kind does with each family of failure.

The inference is simulated, and that is what makes these cases reproducible: a corrupt image,
a missing path, a service that restarts. The simulation reproduces what the real inference
answers — measured, not assumed: a 500 `internal_error` for a corrupt image as for a missing
path, and for the whole batch as soon as a single image in it is bad.
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
    """What sent bytes designate; the witness image, a real PNG, stays itself."""
    if not data_uri.startswith("data:"):
        return data_uri
    raw = base64.b64decode(data_uri.split(",", 1)[1])
    return raw.decode() if raw.startswith(b"/medias/") else "witness"


class _Inference:
    """An inference that refuses any batch containing an image designated as bad."""

    def __init__(self) -> None:
        self.bad: set[str] = set()
        # Refuse every path, accept bytes: a server that does not read its media mount.
        self.refuses_paths = False
        self.status_for_everything: int | None = None
        self.unreachable = False
        self.transport_error: Exception | None = None
        # Rank of the call from which the server stops answering: the case of a service that
        # goes down, or flaps while restarting, in the middle of the search for a faulty image.
        self.unreachable_from_call: int | None = None
        self.calls: list[list[str]] = []

    def client(self, *_args: Any, **_kwargs: Any) -> "_Inference":
        return self

    def __enter__(self) -> "_Inference":
        return self

    def __exit__(self, *_exc: Any) -> None:
        return None

    def list_models(self) -> list[Any]:
        if self.unreachable:
            raise PixanoInferenceError(0, "connection_error", "[Errno 111] Connection refused")
        return [SimpleNamespace(name="clip", model_path="MobileCLIP2-S2")]

    def embedding(self, request: Any, **_kwargs: Any) -> Any:
        images = list(request.image)
        self.calls.append(images)
        if self.unreachable or (
            self.unreachable_from_call is not None and len(self.calls) > self.unreachable_from_call
        ):
            # What the official client really raises: it wraps connection errors in a
            # PixanoInferenceError with status 0. Simulating an httpx.ConnectError, as the first
            # version of this test did, let the defect through in production.
            raise PixanoInferenceError(0, "connection_error", "[Errno 111] Connection refused")
        if self.transport_error is not None:
            raise self.transport_error
        if self.status_for_everything is not None:
            raise PixanoInferenceError(self.status_for_everything, "error", "refused")
        # A damaged image is damaged as bytes too: what the simulated reader gives as the bytes
        # of an image is its path, so that the simulator recognises it in both forms.
        identities = {_decoded(image) for image in images}
        if self.bad & identities:
            raise PixanoInferenceError(500, "internal_error", "Inference error.")
        if self.refuses_paths and any(not image.startswith("data:") for image in images):
            raise PixanoInferenceError(500, "internal_error", "Inference error.")
        vectors = np.ones((len(images), DIM), dtype=np.float32)
        return SimpleNamespace(data=SimpleNamespace(embeddings=SimpleNamespace(to_numpy=lambda: vectors)))


class _Reader:
    """A dataset where some records have no image, and others a lost image."""

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
            return ResolvedMedia(bytes_to_data_uri(view.uri.encode()), carried_bytes=True, reason="bytes")
        return ResolvedMedia(view.uri, carried_bytes=False, reason="path")


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
        """The heart of the quarantine: the seven other images of the batch are saved."""
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
        """The search for the culprit costs nothing on the day there is none."""
        _run(_Reader())

        assert len(inference.calls) == 1

    def test_a_lost_image_is_quarantined_without_calling_inference(self, inference: _Inference) -> None:
        _, outcome = _run(_Reader(lost={"r2"}))

        assert outcome.produced == 7
        assert [(item.item_id, item.reason) for item in outcome.quarantined] == [("r2", "media not found")]
        assert "/medias/r2.jpg" not in inference.calls[0]


class TestSkipped:
    def test_a_record_without_image_is_skipped_not_quarantined(self, inference: _Inference) -> None:
        """The nuScenes case: a lidar sweep without a camera is not an error."""
        _, outcome = _run(_Reader(without_image={"r1", "r3", "r4"}))

        assert (outcome.produced, outcome.skipped, outcome.quarantined) == (5, 3, [])

    def test_a_chunk_without_any_image_calls_nothing(self, inference: _Inference) -> None:
        _, outcome = _run(_Reader(without_image=set(RECORDS)))

        assert (outcome.produced, outcome.skipped) == (0, 8)
        assert inference.calls == []


class TestTransientFailures:
    def test_an_unreachable_inference_is_transient(self, inference: _Inference) -> None:
        inference.unreachable = True

        with pytest.raises(TransientError, match="does not answer"):
            _run(_Reader())

    @pytest.mark.parametrize("code", ["connection_error", "timeout"])
    def test_no_answer_at_all_is_transient(self, inference: _Inference, code: str) -> None:
        """Status 0: the client received no answer at all. No image can be held responsible for it."""
        inference.transport_error = PixanoInferenceError(0, code, "no answer")

        with pytest.raises(TransientError):
            _run(_Reader())

    def test_a_transport_error_the_client_lets_through_is_transient(self, inference: _Inference) -> None:
        """The client only wraps three httpx errors; the others come up raw."""
        inference.transport_error = httpx.RemoteProtocolError("connection cut in the middle of the answer")

        with pytest.raises(TransientError):
            _run(_Reader())

    def test_an_outage_during_the_search_is_not_blamed_on_the_images(self, inference: _Inference) -> None:
        """The defect observed on the real stack, by cutting the inference off mid-job.

        A first call succeeds, the next ones find the connection refused. Seven healthy images
        went to quarantine because "not everything had failed". An image is only blamed on an
        answer from the server, never on its silence.
        """
        inference.bad = {"/medias/r6.jpg"}
        inference.unreachable_from_call = 2

        with pytest.raises(TransientError):
            _run(_Reader())

    @pytest.mark.parametrize("status", [408, 429, 502, 503, 504])
    def test_a_come_back_later_answer_is_transient(self, inference: _Inference, status: int) -> None:
        inference.status_for_everything = status

        with pytest.raises(TransientError, match="come back later"):
            _run(_Reader())

    def test_a_single_refused_image_is_quarantined_when_the_witness_passes(self, inference: _Inference) -> None:
        """Step 1 review: a batch of one corrupt image failed the whole job.

        The last chunk of a dataset often has only one image, and on a lidar dataset most chunks
        do too. "No image passed" was true there from the first damaged image: the chunk was
        replayed until failure, and the job ended in error.
        """
        inference.bad = {"/medias/r0.jpg"}

        _, outcome = _run(_Reader(), records=["r0"])

        assert (outcome.produced, [item.item_id for item in outcome.quarantined]) == (0, ["r0"])

    def test_a_single_image_among_records_without_image_is_quarantined_too(self, inference: _Inference) -> None:
        inference.bad = {"/medias/r5.jpg"}

        _, outcome = _run(_Reader(without_image=set(RECORDS) - {"r5"}))

        assert (outcome.produced, outcome.skipped, len(outcome.quarantined)) == (0, 7, 1)


class TestWitness:
    """Architecture review, point 3: on an entirely refused batch, the server is what decides.

    A generated witness image, sent as bytes: refused, the server is not well; accepted, the
    images are at fault — unless the server does not read the paths it is given.
    """

    @staticmethod
    def _witness_calls(inference: _Inference) -> list[list[str]]:
        return [call for call in inference.calls if len(call) == 1 and _decoded(call[0]) == "witness"]

    def test_a_whole_batch_of_bad_images_is_quarantined_when_the_witness_passes(self, inference: _Inference) -> None:
        """What the previous threshold took for an outage: eight damaged images, a server that is fine."""
        inference.bad = {f"/medias/{r}.jpg" for r in RECORDS}

        _, outcome = _run(_Reader())

        assert (outcome.produced, len(outcome.quarantined)) == (0, 8)
        assert len(self._witness_calls(inference)) == 1

    def test_a_server_refusing_the_witness_is_presumed_down(self, inference: _Inference) -> None:
        inference.status_for_everything = 500

        with pytest.raises(TransientError, match="witness image"):
            _run(_Reader())

    def test_the_witness_is_not_sent_when_something_embedded(self, inference: _Inference) -> None:
        inference.bad = {"/medias/r0.jpg"}

        _run(_Reader())

        assert self._witness_calls(inference) == []

    def test_a_server_that_cannot_read_its_media_mount_is_told_apart_from_bad_images(
        self, inference: _Inference
    ) -> None:
        """The witness passes, every path is refused, the same image passes as bytes: it is the mount."""
        inference.refuses_paths = True

        with pytest.raises(TransientError, match="does not read the media storage"):
            _run(_Reader())

    def test_images_sent_as_bytes_are_not_resent(self, inference: _Inference) -> None:
        """Nothing to resend: they already travelled as bytes, the refusal is theirs."""
        inference.bad = {f"/medias/{r}.jpg" for r in RECORDS}

        _, outcome = _run(_Reader(carried_bytes=True))

        assert len(outcome.quarantined) == 8
        single = [call for call in inference.calls if len(call) == 1 and _decoded(call[0]) != "witness"]
        assert len(single) == 8, "the eight isolations, and no resend"


class TestFatalFailures:
    @pytest.mark.parametrize("status", [401, 403, 404])
    def test_an_error_no_image_could_cause_is_fatal(self, inference: _Inference, status: int) -> None:
        """An unknown model or a denied access: splitting the batch would change nothing."""
        inference.status_for_everything = status

        with pytest.raises(PixanoInferenceError):
            _run(_Reader())

        assert len(inference.calls) == 1, "no search for a culprit on an error that depends on no image"


class TestModelOfTheExistingTable:
    """Refused at planning, before the inference runs over the whole dataset."""

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


class TestModelIdentity:
    """What the provenance of every vector says about the model that produced it."""

    def test_names_the_model_and_the_checkpoint_the_server_loaded(self, inference: _Inference) -> None:
        identity = KIND.model_identity(PARAMS)

        assert (identity.name, identity.version) == ("clip", "MobileCLIP2-S2")

    def test_a_server_that_cannot_be_asked_still_gives_the_name(self, inference: _Inference) -> None:
        """A provenance that cannot be completed must not fail the chunk."""
        inference.unreachable = True
        kind = EmbeddingsKind("http://inference", "")

        identity = kind.model_identity(PARAMS)

        assert (identity.name, identity.version) == ("clip", None)

    def test_a_failed_query_is_asked_again_rather_than_remembered(self, inference: _Inference) -> None:
        """One unreachable moment must not leave every later row of the process without a version."""
        kind = EmbeddingsKind("http://inference", "")
        inference.unreachable = True
        kind.model_identity(PARAMS)
        inference.unreachable = False

        assert kind.model_identity(PARAMS).version == "MobileCLIP2-S2"

    def test_engine_parameters_stay_out_of_the_provenance(self) -> None:
        recorded = KIND.provenance_params(KIND.validate_params({"model": "clip", "chunk_size": 3}))

        assert recorded == {"model": "clip", "normalize": True}
