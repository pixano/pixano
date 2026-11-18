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
import io
from types import SimpleNamespace
from typing import Any

import httpx
import numpy as np
import pytest
from pixano_inference.client import PixanoInferenceError
from pixano_worker.kinds import CONFIRM_MARKER, EmbeddingsKind, TransientError
from pixano_worker.kinds.inference import QUERY_TIMEOUT_S
from pixano_worker.media import MediaResolver, ResolvedMedia
from pixano_worker.writer import ModelIdentity

from pixano.datasets.embedding_spaces import AmbiguousModelError
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
        self.code_for_everything = "error"
        self.unreachable = False
        self.transport_error: Exception | None = None
        # Rank of the call from which the server stops answering: the case of a service that
        # goes down, or flaps while restarting, in the middle of the search for a faulty image.
        self.unreachable_from_call: int | None = None
        self.calls: list[list[str]] = []
        self.opened = self.closed = 0
        # What `GET /v1/models` lists, when a test says; else the model, served with the weights below.
        self.models: list[Any] | None = None
        # The weights the server serves the model with, and whether it answers which.
        self.model_path: str | None = "MobileCLIP2-S2"
        self.models_unreachable = False

    def client(self, *_args: Any, **_kwargs: Any) -> "_Inference":
        self.opened += 1
        return self

    def __enter__(self) -> "_Inference":
        return self

    def __exit__(self, *_exc: Any) -> None:
        self.closed += 1

    def list_models(self) -> list[Any]:
        if self.unreachable or self.models_unreachable:
            raise PixanoInferenceError(0, "connection_error", "[Errno 111] Connection refused")
        if self.models is not None:
            return self.models
        return [SimpleNamespace(name="clip", model_path=self.model_path, capability="embedding")]

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
            raise PixanoInferenceError(self.status_for_everything, self.code_for_everything, "refused")
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
    """A table of images — one per record here — where some are missing and others lost.

    A medium's identifier is the name its test refers to ("r5"); its record is "rec-r5". The
    two differ on purpose, so that a test cannot pass by confusing a medium with its record.

    As in a real dataset, a view designated by path carries no bytes of its own: only its file
    can be read, through `open_media`. The dataset is not reachable at all, so that nothing here
    reads a medium another way.
    """

    def __init__(
        self,
        missing: set[str] = frozenset(),  # type: ignore[assignment]
        lost: set[str] = frozenset(),  # type: ignore[assignment]
        carried_bytes: bool = False,
    ) -> None:
        self.missing = missing
        self.lost = lost
        self.carried_bytes = carried_bytes
        self.media = MediaResolver("/medias", "/medias")

    @staticmethod
    def open_media(table_name: str, view: Any) -> Any:
        """The file a view names, as this worker reads it: here its path, so that the simulated
        inference recognises an image in both forms."""
        return io.BytesIO(view.uri.encode())

    def rows(self, table_name: str, ids: list[str]) -> list[Any]:
        return [
            SimpleNamespace(id=view_id, record_id=f"rec-{view_id}", uri=f"/medias/{view_id}.jpg")
            for view_id in ids
            if view_id not in self.missing
        ]

    def resolve_media(self, table_name: str, view: Any) -> ResolvedMedia | None:
        if view.id in self.lost:
            return None
        if self.carried_bytes:
            return ResolvedMedia(bytes_to_data_uri(view.uri.encode()), designation="bytes", reason="bytes")
        return ResolvedMedia(view.uri, designation="path", reason="path")


@pytest.fixture
def inference(monkeypatch: pytest.MonkeyPatch) -> _Inference:
    fake = _Inference()
    monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", fake.client)
    return fake


KIND = EmbeddingsKind("http://inference", "")
PARAMS = KIND.validate_params({"model": "clip"})
RECORDS = [f"r{i}" for i in range(8)]


def _run(reader: _Reader, records: list[str] = RECORDS) -> tuple[dict[str, Any], Any]:
    payload = {"table": "images", "view_ids": records}
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
            "record_id": "rec-r5",
        }
        assert "r5" not in result["view_ids"]
        assert result["record_ids"] == [f"rec-{view_id}" for view_id in result["view_ids"]]

    def test_several_corrupt_images_are_all_isolated(self, inference: _Inference) -> None:
        inference.bad = {"/medias/r0.jpg", "/medias/r7.jpg"}

        _, outcome = _run(_Reader())

        assert outcome.produced == 6
        assert sorted(item.item_id for item in outcome.quarantined) == ["r0", "r7"]

    def test_the_client_is_closed_with_the_chunk(self, inference: _Inference) -> None:
        """A client holds a connection pool, and one was left per chunk: two now, both closed — the
        call's, and the question of which weights answered."""
        _run(_Reader())

        assert inference.opened == inference.closed == 2

    def test_a_healthy_batch_costs_a_single_call(self, inference: _Inference) -> None:
        """The search for the culprit costs nothing on the day there is none."""
        _run(_Reader())

        assert len(inference.calls) == 1

    def test_a_lost_image_is_quarantined_without_calling_inference(self, inference: _Inference) -> None:
        _, outcome = _run(_Reader(lost={"r2"}))

        assert outcome.produced == 7
        assert [(item.item_id, item.reason) for item in outcome.quarantined] == [("r2", "media not found")]
        assert "/medias/r2.jpg" not in inference.calls[0]


class TestMissingMedia:
    def test_a_medium_gone_from_its_table_is_quarantined(self, inference: _Inference) -> None:
        """Planned, then deleted before its chunk ran: nothing is skipped any more, planning lists existing media."""
        _, outcome = _run(_Reader(missing={"r1", "r3"}))

        assert (outcome.produced, outcome.skipped) == (6, 0)
        assert sorted((item.item_id, item.reason) for item in outcome.quarantined) == [
            ("r1", "media not found"),
            ("r3", "media not found"),
        ]

    def test_a_chunk_whose_media_are_all_gone_calls_nothing(self, inference: _Inference) -> None:
        _, outcome = _run(_Reader(missing=set(RECORDS)))

        assert (outcome.produced, len(outcome.quarantined)) == (0, 8)
        assert inference.calls == []


class TestEarlierPayloads:
    def test_a_chunk_planned_by_record_says_so(self, inference: _Inference) -> None:
        """A chunk queued before the upgrade failed with the reason "'table'"."""
        with pytest.raises(ValueError, match="planned by an earlier version"):
            KIND.process(_Reader(), {"record_ids": RECORDS}, PARAMS)  # type: ignore[arg-type]


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
        """A batch of one corrupt image used to fail the whole job.

        The last chunk of a dataset often has only one image, and on a lidar dataset most chunks
        do too. "No image passed" was true there from the first damaged image: the chunk was
        replayed until failure, and the job ended in error.
        """
        inference.bad = {"/medias/r0.jpg"}

        _, outcome = _run(_Reader(), records=["r0"])

        assert (outcome.produced, [item.item_id for item in outcome.quarantined]) == (0, ["r0"])

    def test_a_single_image_among_missing_media_is_quarantined_too(self, inference: _Inference) -> None:
        inference.bad = {"/medias/r5.jpg"}

        _, outcome = _run(_Reader(missing=set(RECORDS) - {"r5"}))

        assert (outcome.produced, outcome.skipped, len(outcome.quarantined)) == (0, 0, 8)


class TestWitness:
    """On an entirely refused batch, the server is what decides.

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

    def test_an_answer_the_worker_cannot_read_is_fatal(self, inference: _Inference) -> None:
        """What the client raises for a successful answer that does not match its schema — a client
        and a server of different versions: no medium is at fault, so none goes to quarantine."""
        inference.status_for_everything, inference.code_for_everything = 200, "invalid_response"

        with pytest.raises(PixanoInferenceError, match="invalid_response"):
            _run(_Reader())

        assert len(inference.calls) == 1, "no search for a culprit on an error that depends on no image"


class _PlanningReader:
    """A nuScenes-like dataset: images in one table, point clouds in another."""

    TABLES = {"image": ["images"], "point_cloud": ["point_clouds"], "video": [], "text": []}

    def __init__(
        self,
        space: dict[str, Any] | None = None,
        images: int = 8,
        point_clouds: int = 3,
        fully_read: bool = True,
        spaces: list[dict[str, Any]] | None = None,
    ) -> None:
        held = spaces if spaces is not None else ([space] if space is not None else [])
        self.dataset = SimpleNamespace(
            record_embedding_space=lambda model=None: space,
            record_embeddings_fully_read=lambda: fully_read,
            record_embedding_spaces=lambda: held,
        )
        self._ids = {
            "images": [f"img-{n}" for n in range(images)],
            "point_clouds": [f"pc-{n}" for n in range(point_clouds)],
        }

    def media_tables(self, media_type: str) -> list[str]:
        return self.TABLES[media_type]

    def ids(self, table_name: str) -> list[str]:
        return self._ids[table_name]


def _plan(reader: _PlanningReader, kind: EmbeddingsKind | None = None, **params: Any) -> list[Any]:
    planner = kind or KIND
    return list(planner.plan(reader, planner.validate_params({"model": "clip", **params})))  # type: ignore[arg-type]


class TestTheEmbeddingsAlreadyThere:
    """Each model has a table of its own: another model's vectors refuse nothing."""

    def test_a_dataset_without_embeddings_accepts_any_model(self, inference: _Inference) -> None:
        chunks = _plan(_PlanningReader(None))

        assert sum(chunk.task_count for chunk in chunks) == 8

    def test_the_same_model_is_planned(self, inference: _Inference) -> None:
        assert _plan(_PlanningReader({"model_id": "clip", "dim": 512}))

    def test_another_model_is_planned_beside_them(self, inference: _Inference) -> None:
        assert _plan(_PlanningReader({"model_id": "dinov2", "dim": 768}))

    def test_a_server_that_names_no_weights_for_a_model_held_twice_fails_the_planning(
        self, inference: _Inference
    ) -> None:
        """It never will: each chunk would run its inference for vectors with no space to go to."""
        inference.model_path = None
        spaces = [{"model_id": "clip", "checkpoint": "a"}, {"model_id": "clip", "checkpoint": "b"}]

        with pytest.raises(ValueError, match="holds the embeddings of 2 of its checkpoints"):
            _plan(_PlanningReader(spaces=spaces), kind=EmbeddingsKind("http://inference", ""))

    def test_a_server_that_cannot_be_asked_for_a_model_held_twice_still_plans(self, inference: _Inference) -> None:
        """It may be restarting: the chunks ask again, and are handed back while it does not answer."""
        inference.models_unreachable = True
        spaces = [{"model_id": "clip", "checkpoint": "a"}, {"model_id": "clip", "checkpoint": "b"}]

        assert _plan(_PlanningReader(spaces=spaces), kind=EmbeddingsKind("http://inference", ""))

    def test_a_description_that_cannot_be_read_entirely_fails_the_planning(self, inference: _Inference) -> None:
        """Refused before the inference runs over the whole dataset: no chunk could write its vectors."""
        with pytest.raises(ValueError, match="cannot be read entirely"):
            _plan(_PlanningReader(fully_read=False))


class TestPlanningByMedium:
    """A task is a medium, and the user chooses which media types a job covers."""

    def test_a_task_is_a_medium_and_a_chunk_names_its_table(self, inference: _Inference) -> None:
        chunks = _plan(_PlanningReader(images=10), chunk_size=4)

        assert [chunk.task_count for chunk in chunks] == [4, 4, 2]
        assert {chunk.payload["table"] for chunk in chunks} == {"images"}
        assert [view for chunk in chunks for view in chunk.payload["view_ids"]] == [f"img-{n}" for n in range(10)]

    def test_images_by_default_and_nothing_else(self, inference: _Inference) -> None:
        chunks = _plan(_PlanningReader())

        assert all(view.startswith("img-") for chunk in chunks for view in chunk.payload["view_ids"])

    def test_a_type_this_kind_cannot_send_refuses_the_whole_job(self, inference: _Inference) -> None:
        """Whole, not partly: the user serves what the type needs, or narrows the selection."""
        with pytest.raises(ValueError, match="cannot process point_cloud"):
            _plan(_PlanningReader(), media=["image", "point_cloud"])

    def test_an_unknown_type_is_refused_by_the_parameters(self) -> None:
        with pytest.raises(ValueError):
            KIND.validate_params({"model": "clip", "media": ["hologram"]})

    def test_a_model_the_inference_does_not_serve_refuses_the_job(self, inference: _Inference) -> None:
        with pytest.raises(ValueError, match="serves no embedding model named 'siglip' — it serves clip"):
            _plan(_PlanningReader(), model="siglip")

    def test_a_model_served_for_another_task_refuses_the_job(self, inference: _Inference) -> None:
        """A detector of the same name is no embedding model: the chunks would all fail on it."""
        inference.models = [SimpleNamespace(name="clip", model_path="yolo26n.pt", capability="detection")]

        with pytest.raises(ValueError, match="serves no embedding model named 'clip' — it serves none"):
            _plan(_PlanningReader())

    def test_an_unreachable_inference_does_not_refuse_the_job(self, inference: _Inference) -> None:
        """It may be restarting: the chunks will wait for it like after any outage."""
        inference.unreachable = True

        assert _plan(_PlanningReader())

    def test_a_dataset_without_the_chosen_media_plans_nothing(self, inference: _Inference) -> None:
        assert _plan(_PlanningReader(images=0)) == []

    def test_the_form_starts_with_images_ticked(self) -> None:
        """With a default factory, pydantic published no default,
        the form started with nothing ticked, and Run was refused with a bare 422."""
        media = KIND.params_model.model_json_schema()["properties"]["media"]

        assert media["default"] == ["image"]
        assert (
            KIND.validate_params({"model": "clip"}).media == ["image"]
            and KIND.validate_params({"model": "clip"}).media is not KIND.validate_params({"model": "clip"}).media
        )

    def test_names_no_model_and_asks_the_form_for_a_served_one(self) -> None:
        """A model name in a kind is a guess about a deployment: the form offers the models the
        inference serves for embeddings instead."""
        from pixano_worker.kinds import MODEL_TASK_MARKER

        schema = KIND.params_model.model_json_schema()

        assert "model" in schema["required"]
        assert "default" not in schema["properties"]["model"]
        assert schema["properties"]["model"][MODEL_TASK_MARKER] == "embedding"


class TestReplaceExistingEmbeddings:
    """The explicit way to compute a model's embeddings again from nothing."""

    class _Writer:
        """A writer whose model the runner asked the inference for, outside the dataset's lock."""

        def __init__(self, checkpoint: str | None = "MobileCLIP2-S2", ambiguous: bool = False) -> None:
            self.model = ModelIdentity("clip", checkpoint)
            self.drops: list[tuple[str, str]] = []
            self._ambiguous = ambiguous

        def empty_embeddings(self, model: str, checkpoint: str = "") -> None:
            if self._ambiguous:
                raise AmbiguousModelError(f"model '{model}' names 2 embedding spaces, of the checkpoints a, b")
            self.drops.append((model, checkpoint))

    def test_without_the_parameter_nothing_is_dropped(self, inference: _Inference) -> None:
        writer = self._Writer()

        KIND.prepare(writer, KIND.validate_params({"model": "clip"}))  # type: ignore[arg-type]

        assert writer.drops == []

    def test_with_the_parameter_only_the_jobs_model_is_dropped(self, inference: _Inference) -> None:
        """This checkpoint of this model: the other models' vectors are kept."""
        writer = self._Writer()

        KIND.prepare(writer, KIND.validate_params({"model": "clip", "replace_existing_embeddings": True}))  # type: ignore[arg-type]

        assert writer.drops == [("clip", "MobileCLIP2-S2")]

    def test_a_checkpoint_left_untold_refuses_the_job_rather_than_guess(self) -> None:
        """Planned while the inference could not say which weights it serves: no space is emptied by guess."""
        writer = self._Writer(checkpoint=None, ambiguous=True)

        with pytest.raises(ValueError, match="does not say which weights it serves: submit the job again"):
            KIND.prepare(writer, KIND.validate_params({"model": "clip", "replace_existing_embeddings": True}))  # type: ignore[arg-type]

    def test_a_checkpoint_told_that_matches_several_spaces_asks_for_the_others_to_go(self) -> None:
        writer = self._Writer(checkpoint="MobileCLIP2-S2", ambiguous=True)

        with pytest.raises(ValueError, match="delete those of its embeddings that are not this checkpoint's first"):
            KIND.prepare(writer, KIND.validate_params({"model": "clip", "replace_existing_embeddings": True}))  # type: ignore[arg-type]

    def test_the_form_is_asked_to_confirm_it(self) -> None:
        field = KIND.params_model.model_json_schema()["properties"]["replace_existing_embeddings"]

        assert "deletes every vector this model already computed" in field[CONFIRM_MARKER]
        assert "other models' vectors are kept" in field[CONFIRM_MARKER]

    def test_it_is_not_part_of_the_provenance(self) -> None:
        """What the job did to the dataset before computing, not how a vector was computed."""
        params = KIND.validate_params({"model": "clip", "replace_existing_embeddings": True})

        assert "replace_existing_embeddings" not in KIND.provenance_params(params)


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

    def test_the_question_is_bounded_and_its_client_closed(
        self, inference: _Inference, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A slow server must not hold a chunk for the client's default minute, nor leak its pool."""
        asked: list[dict[str, Any]] = []

        def client(*args: Any, **kwargs: Any) -> _Inference:
            asked.append(kwargs)
            return inference.client(*args, **kwargs)

        monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", client)
        kind = EmbeddingsKind("http://inference", "")

        kind.model_identity(PARAMS)

        assert asked == [{"api_key": None, "max_retries": 0, "timeout": QUERY_TIMEOUT_S}]
        assert inference.closed == 1

    def test_engine_parameters_stay_out_of_the_provenance(self) -> None:
        recorded = KIND.provenance_params(KIND.validate_params({"model": "clip", "chunk_size": 3}))

        assert recorded == {"model": "clip", "normalize": True, "media": ["image"]}


class TestWhichWeightsAnswered:
    """The checkpoint is asked when it matters, never taken from what this worker remembers of another job."""

    @staticmethod
    def _kind() -> EmbeddingsKind:
        return EmbeddingsKind("http://inference", "")

    def test_each_planning_reads_it_again(self, inference: _Inference) -> None:
        """Weights redeployed under the name since the last job are this job's."""
        kind = self._kind()
        assert kind.model_identity(PARAMS).version == "MobileCLIP2-S2"
        inference.model_path = "ViT-L-14"

        chunks = _plan(_PlanningReader(), kind=kind)

        assert {chunk.payload["checkpoint"] for chunk in chunks} == {"ViT-L-14"}

    def test_a_server_that_cannot_be_asked_at_planning_leaves_nothing_remembered(self, inference: _Inference) -> None:
        kind = self._kind()
        kind.model_identity(PARAMS)
        inference.models_unreachable = True

        chunks = _plan(_PlanningReader(), kind=kind)

        assert {chunk.payload["checkpoint"] for chunk in chunks} == {""}
        assert kind.model_identity(PARAMS).version is None

    def test_a_chunk_tells_the_weights_that_answered_it(self, inference: _Inference) -> None:
        kind = self._kind()
        kind.model_identity(PARAMS)
        inference.model_path = "ViT-L-14"

        result = kind.process(_Reader(), {"table": "images", "view_ids": RECORDS}, PARAMS)  # type: ignore[arg-type]

        assert result["checkpoint"] == "ViT-L-14"

    def test_the_weights_that_answered_come_before_those_planning_read(self) -> None:
        """Redeployed during the job: the vectors go to the space of the weights that made them."""
        written = EmbeddingsKind._checkpoint_written({"checkpoint": "ViT-L-14"}, {"checkpoint": "MobileCLIP2-S2"})
        planned = EmbeddingsKind._checkpoint_written({"checkpoint": ""}, {"checkpoint": "MobileCLIP2-S2"})

        assert (written, planned) == ("ViT-L-14", "MobileCLIP2-S2")
