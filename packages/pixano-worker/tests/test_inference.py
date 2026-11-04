# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""What a kind that calls the inference does on the real path: the model check that refuses a job
before `prepare` destroys anything, and the witness that tells the inference's fault from the
media's when every medium of a chunk is refused.

The dataset is a real one, its images files on disk designated by path, read and written through
the runner's own reader and writer. The inference is the official client talking to a server simulated at its
HTTP edge, which reads an image the way the real one does — a path under its own media root, or
the bytes of a data URI — and answers what the real one answers when it cannot: 500
`internal_error`, for a corrupt image, a missing path or an unreachable URL alike.
"""

import base64
import io
import json
import logging
import os
import threading
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import httpx
import numpy as np
import pytest
from PIL import Image as PILImage
from PIL import UnidentifiedImageError
from pixano_inference.client import PixanoInferenceError, SyncPixanoInferenceClient
from pixano_worker import runner
from pixano_worker.kinds import Chunk, EmbeddingsKind, JobKind, TransientError
from pixano_worker.kinds.embeddings import EMBEDDING_CAPABILITY
from pixano_worker.kinds.inference import REFUSED_BY_THE_SERVER, Failure, chunk_media, classify, witness_image
from pixano_worker.media import MediaResolver
from pixano_worker.writer import JobWriter

from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.inference.media import bytes_to_data_uri
from pixano.schemas import Image, Record


DATASET_ID = "street"
IMAGES_TABLE = "images"
INFERENCE_URL = "http://inference"
# The key the simulated server guards its routes with, as a deployed one does.
API_KEY = "the-key"
# The same media storage, mounted elsewhere by the inference: the worker sends it this path.
INFERENCE_MEDIA_ROOT = "/inference-media"
# Wider than tall, as the images of a street scene are.
WIDTH, HEIGHT = 200, 100
# Each view, its record and its file.
VIEWS = {"v1": ("r1", "a.png"), "v2": ("r2", "b.png")}
# The width of the simulated embedding model's vectors.
DIM = 4
# The model the simulated server serves for embeddings, which the embeddings kind asks for.
CLIP = "clip"
# Where a URL designation points: a host the simulated inference cannot reach.
UNREACHABLE_HOST = "https://media.example"


def _png(width: int = WIDTH, height: int = HEIGHT) -> bytes:
    buffer = io.BytesIO()
    PILImage.new("RGB", (width, height), (90, 120, 150)).save(buffer, format="PNG")
    return buffer.getvalue()


def _refusal(status: int, code: str, message: str) -> httpx.Response:
    """An error as the real server words it."""
    return httpx.Response(status, json={"error": {"code": code, "message": message}})


def _answer(data: dict[str, Any]) -> httpx.Response:
    """A successful inference, in the real server's envelope."""
    return httpx.Response(
        200,
        json={
            "id": "simulated",
            "status": "SUCCESS",
            "timestamp": "2026-10-13T00:00:00Z",
            "metadata": {},
            "data": data,
        },
    )


def _array(values: np.ndarray) -> dict[str, Any]:
    """An array as the server sends one: its shape, its type, its raw bytes in base64."""
    contiguous = np.ascontiguousarray(values, dtype=np.float32)
    return {"shape": list(values.shape), "dtype": "float32", "data": base64.b64encode(contiguous.tobytes()).decode()}


class _Server:
    """The inference at its HTTP edge, serving an embedding model.

    Attributes:
        models_answer: What `GET /v1/models` answers instead of the models: a response, or an
            exception the transport raises — the server cannot be reached.
        reads_paths: False for a server that does not read its media mount: it refuses every
            path it is sent, as the real one does, with a 500.
        bytes_answer: What the server does when a medium is sent as bytes: an exception the
            transport raises — it stops answering right then — or an answer it gives instead.
        images: Each image the server was asked about, in order.
    """

    MODELS = [
        {"name": CLIP, "capability": EMBEDDING_CAPABILITY, "modelPath": "MobileCLIP2-S2", "status": "RUNNING"},
    ]

    def __init__(self, media_root: Path) -> None:
        self.media_root = media_root
        self.models_answer: httpx.Response | Exception | None = None
        self.reads_paths = True
        self.bytes_answer: Exception | httpx.Response | None = None
        self.images: list[str] = []

    def handle(self, request: httpx.Request) -> httpx.Response:
        # Every route but health is behind the key: none sent is a 401, a wrong one a 403.
        key = request.headers.get("X-API-Key")
        if key is None:
            return _refusal(httpx.codes.UNAUTHORIZED, "unauthorized", "Missing API key.")
        if key != API_KEY:
            return _refusal(httpx.codes.FORBIDDEN, "forbidden", "Invalid API key.")
        if request.url.path == "/v1/models":
            if isinstance(self.models_answer, Exception):
                raise self.models_answer
            return self.models_answer or httpx.Response(200, json=self.MODELS)
        body = json.loads(request.content)
        images = body["image"] if isinstance(body["image"], list) else [body["image"]]
        self.images.extend(images)
        if self.bytes_answer is not None and any(self._is_a_mediums_bytes(image) for image in images):
            if isinstance(self.bytes_answer, httpx.Response):
                return self.bytes_answer
            raise self.bytes_answer
        sizes = [self._size(image) for image in images]
        if any(size is None for size in sizes):
            # The whole batch, as the real server refuses it for one image it cannot open.
            return _refusal(httpx.codes.INTERNAL_SERVER_ERROR, "internal_error", "Inference error.")
        assert request.url.path == "/v1/inference/embedding", request.url.path
        return _answer({"embeddings": _array(np.ones((len(images), DIM))), "dim": DIM})

    @staticmethod
    def _is_a_mediums_bytes(image: str) -> bool:
        return image.startswith("data:") and image != witness_image()

    def _size(self, image: str) -> tuple[int, int] | None:
        """The image's size if this server can open it — None, and it refuses it, otherwise."""
        if image.startswith("data:"):
            source: Any = io.BytesIO(base64.b64decode(image.split(",", 1)[1]))
        elif self.reads_paths and image.startswith(f"{INFERENCE_MEDIA_ROOT}/"):
            source = self.media_root / image.removeprefix(f"{INFERENCE_MEDIA_ROOT}/")
        else:
            return None
        try:
            with PILImage.open(source) as opened:
                return opened.size
        except (OSError, UnidentifiedImageError):
            return None


@dataclass(frozen=True)
class _Kind:
    """One inference kind, as these tests drive it.

    Attributes:
        make: The kind, bound to the simulated server with an API key.
        model: The model it asks for, among those the server serves.
        replace: The parameter that makes its `prepare` destroy what it wrote before.
        written: How many of the rows it wrote a dataset holds — what `prepare` would destroy.
    """

    make: Callable[[str], JobKind]
    model: str
    replace: str
    written: Callable[[Dataset], int]


def _vectors(dataset: Dataset) -> int:
    return dataset.count_rows_where(JobWriter.EMBEDDING_TABLE) if dataset.has_record_embeddings() else 0


KINDS = {
    "embeddings": _Kind(lambda key: EmbeddingsKind(INFERENCE_URL, key), CLIP, "replace_existing_embeddings", _vectors),
}


@dataclass
class _Scene:
    """A library holding one dataset of images, its media root, and the inference that serves it."""

    library: Path
    media_root: Path
    server: _Server

    @property
    def resolver(self) -> MediaResolver:
        return MediaResolver(str(self.media_root), INFERENCE_MEDIA_ROOT)

    def dataset(self) -> Dataset:
        """The dataset as the application opens it: an instance of its own."""
        return Dataset.find(DATASET_ID, self.library)

    def plan(self, kind: JobKind, params: Any, job_id: str = "job-1") -> list[Chunk]:
        """Plan a job as the runner does: split on the dataset reopened, then prepared under its write lock.

        The loop waits for it all along, so it never abandons it.
        """
        return runner._plan_and_prepare(
            kind, self.library, DATASET_ID, self.resolver, job_id, params, abandoned=threading.Event()
        )

    def process(self, kind: JobKind, params: Any) -> dict[str, Any]:
        """Process one chunk of every view, through the reader the runner gives a chunk."""
        reader = runner._reader_for(self.library, DATASET_ID, self.resolver)
        return kind.process(reader, {"table": IMAGES_TABLE, "view_ids": list(VIEWS)}, params)

    def run(self, kind: JobKind, params: Any, job_id: str) -> None:
        """One job, planned, processed and written as the runner does it, without the queue."""
        for chunk in self.plan(kind, params, job_id):
            result = kind.process(runner._reader_for(self.library, DATASET_ID, self.resolver), chunk.payload, params)
            writer = runner._writer_for(self.library, DATASET_ID, kind, job_id, params)
            kind.write(writer, result, chunk.payload, params)


def _make_scene(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, uri_of: Callable[[Path, str], str]) -> _Scene:
    """A dataset of two images on disk, served by a simulated inference.

    Args:
        tmp_path: Where the library and the media live.
        monkeypatch: To empty the runner's dataset cache and plug the simulated server in.
        uri_of: How a view designates its file, from the media root and the file's name.
    """
    # The runner keeps the datasets it opened in a module-level cache: empty, the tests stay apart.
    monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
    media_root = tmp_path / "media"
    media_root.mkdir()
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID,
        DatasetInfo(id=DATASET_ID, name="Street", record=Record, views={"image": Image}),
    )
    dataset.add_records({"records": [Record(id=record_id) for record_id, _ in VIEWS.values()]})
    for _, file_name in VIEWS.values():
        (media_root / file_name).write_bytes(_png())
    dataset.add_data(
        IMAGES_TABLE,
        [
            Image(
                id=view_id,
                record_id=record_id,
                logical_name="image",
                uri=uri_of(media_root, file_name),
                width=WIDTH,
                height=HEIGHT,
            )
            for view_id, (record_id, file_name) in VIEWS.items()
        ],
        raise_or_warn="none",
    )

    server = _Server(media_root)
    transport = httpx.MockTransport(server.handle)
    monkeypatch.setattr(
        "pixano_worker.kinds.inference.SyncPixanoInferenceClient",
        lambda url, **kwargs: SyncPixanoInferenceClient(url, transport=transport, **kwargs),
    )
    return _Scene(library, media_root, server)


@pytest.fixture
def scene(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Scene:
    """Images designated by path, under the media root the worker and the inference share."""
    return _make_scene(tmp_path, monkeypatch, lambda root, name: str(root / name))


def _params(kind: JobKind, case: _Kind, **params: Any) -> Any:
    # No retry inside the client: a test of what the kind does with an answer, not of the client's backoff.
    return kind.validate_params({"model": case.model, "max_retries": 0, **params})


@pytest.fixture(params=list(KINDS))
def case(request: pytest.FixtureRequest) -> _Kind:
    return KINDS[request.param]


class TestAModelCheckTheServerRefuses:
    """Planning did not ask the inference whether it serves the job's model. A job naming a model it
    cannot have passed planning, `prepare` destroyed what the job was to replace, then every chunk
    failed on the same answer."""

    @pytest.fixture
    def written(self, scene: _Scene, case: _Kind) -> int:
        """A first job of the kind ran: the dataset holds what a replacing job's `prepare` clears."""
        kind = case.make(API_KEY)
        scene.run(kind, _params(kind, case), "job-1")
        written = case.written(scene.dataset())
        assert written > 0, "the first job wrote nothing a replacing job could destroy"
        return written

    def test_a_served_model_lets_prepare_clear_what_the_job_replaces(
        self, scene: _Scene, case: _Kind, written: int
    ) -> None:
        """What the refusals below keep from happening, on the same dataset."""
        kind = case.make(API_KEY)

        assert scene.plan(kind, _params(kind, case, **{case.replace: True}), "job-2")

        assert case.written(scene.dataset()) == 0

    def test_a_model_the_server_does_not_serve_refuses_the_job(self, scene: _Scene, case: _Kind, written: int) -> None:
        kind = case.make(API_KEY)

        with pytest.raises(ValueError, match="serves no .* model named 'not-served'"):
            scene.plan(kind, _params(kind, case, model="not-served", **{case.replace: True}), "job-2")

        assert case.written(scene.dataset()) == written

    @pytest.mark.parametrize(
        ("key", "answer", "status"),
        [
            pytest.param("", None, 401, id="no key"),
            pytest.param("a-wrong-key", None, 403, id="wrong key"),
            pytest.param(API_KEY, _refusal(404, "not_found", "Not Found."), 404, id="no such route"),
            pytest.param(API_KEY, _refusal(405, "method_not_allowed", "Method Not Allowed."), 405, id="wrong method"),
        ],
    )
    def test_refuses_the_job_before_prepare_destroys_anything(
        self,
        scene: _Scene,
        case: _Kind,
        written: int,
        key: str,
        answer: httpx.Response | None,
        status: int,
    ) -> None:
        scene.server.models_answer = answer
        kind = case.make(key)

        with pytest.raises(ValueError, match=rf"inference at {INFERENCE_URL} refuses .*\[{status} "):
            scene.plan(kind, _params(kind, case, **{case.replace: True}), "job-2")

        assert case.written(scene.dataset()) == written

    @pytest.mark.parametrize(
        "answer",
        [
            pytest.param(httpx.ConnectError("[Errno 111] Connection refused"), id="connection refused"),
            pytest.param(httpx.RemoteProtocolError("Server disconnected"), id="connection cut"),
            pytest.param(_refusal(503, "unavailable", "Restarting."), id="come back later"),
            pytest.param(_refusal(500, "internal_error", "Inference error."), id="unwell"),
        ],
    )
    def test_a_server_that_cannot_say_does_not_refuse_the_job(
        self, scene: _Scene, case: _Kind, answer: httpx.Response | Exception
    ) -> None:
        """It may be restarting: the chunks will wait for it like after any outage."""
        scene.server.models_answer = answer
        kind = case.make(API_KEY)

        assert scene.plan(kind, _params(kind, case))

    def test_an_answer_it_cannot_read_fails_the_planning_with_its_detail(
        self, scene: _Scene, case: _Kind, written: int
    ) -> None:
        """Not a state of the server — a client and a server of different versions, say: said as it
        is, rather than taken for an outage while `prepare` clears the dataset."""
        kind = case.make(API_KEY)
        scene.server.models_answer = httpx.Response(200, json=[{"model": case.model}])

        with pytest.raises(ValueError, match="in a form this worker cannot read.*invalid_response"):
            scene.plan(kind, _params(kind, case, **{case.replace: True}), "job-2")

        assert case.written(scene.dataset()) == written


class TestTheWitness:
    """The media of a chunk were resent as the dataset's bytes, which
    a view designated by path does not have. On a real dataset the mount was never diagnosed, and
    every sound image of a chunk went to quarantine when the inference could not read its storage."""

    def test_an_inference_that_does_not_read_its_mount_has_the_chunk_replayed(
        self, scene: _Scene, case: _Kind
    ) -> None:
        scene.server.reads_paths = False
        kind = case.make(API_KEY)

        with pytest.raises(TransientError, match=f"{INFERENCE_MEDIA_ROOT} — check PIXANO_INFERENCE_MEDIA_ROOT"):
            scene.process(kind, _params(kind, case))

        assert scene.server.images[-1] == bytes_to_data_uri(
            (scene.media_root / "a.png").read_bytes()
        ), "the medium resent is the file as this worker reads it"

    def test_corrupt_images_are_quarantined_when_their_bytes_are_refused_too(self, scene: _Scene, case: _Kind) -> None:
        for _, file_name in VIEWS.values():
            (scene.media_root / file_name).write_bytes(b"not an image")
        kind = case.make(API_KEY)

        result = scene.process(kind, _params(kind, case))

        assert sorted(item["item_id"] for item in result["quarantined"]) == sorted(VIEWS)
        assert {item["reason"] for item in result["quarantined"]} == {REFUSED_BY_THE_SERVER}

    def test_media_gone_from_the_storage_are_quarantined(self, scene: _Scene, case: _Kind) -> None:
        """Neither the inference nor this worker reads them: nothing to resend, nothing to blame but them."""
        for _, file_name in VIEWS.values():
            (scene.media_root / file_name).unlink()
        kind = case.make(API_KEY)

        result = scene.process(kind, _params(kind, case))

        assert sorted(item["item_id"] for item in result["quarantined"]) == sorted(VIEWS)
        assert [image for image in scene.server.images if image.startswith("data:")] == [witness_image()]

    def test_a_medium_gone_from_the_storage_leaves_the_next_to_be_resent(self, scene: _Scene, case: _Kind) -> None:
        """Only the first medium sent by path was tried: gone, it stopped the check, and the sound
        media after it went to quarantine with it although the inference's mount was at fault."""
        scene.server.reads_paths = False
        (scene.media_root / "a.png").unlink()
        kind = case.make(API_KEY)

        with pytest.raises(TransientError, match=f"{INFERENCE_MEDIA_ROOT} — check PIXANO_INFERENCE_MEDIA_ROOT"):
            scene.process(kind, _params(kind, case))

        assert scene.server.images[-1] == bytes_to_data_uri((scene.media_root / "b.png").read_bytes())

    @pytest.mark.skipif(hasattr(os, "geteuid") and os.geteuid() == 0, reason="root reads any file")
    def test_files_this_worker_sees_but_cannot_read_decide_nothing(
        self, scene: _Scene, case: _Kind, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Like files that are gone, they leave the media to quarantine, and the log says why."""
        files = [scene.media_root / file_name for _, file_name in VIEWS.values()]
        for file in files:
            file.chmod(0)
        kind = case.make(API_KEY)

        try:
            with caplog.at_level(logging.WARNING, logger="pixano-worker"):
                result = scene.process(kind, _params(kind, case))
        finally:
            for file in files:
                file.chmod(0o644)

        assert sorted(item["item_id"] for item in result["quarantined"]) == sorted(VIEWS)
        assert [image for image in scene.server.images if image.startswith("data:")] == [witness_image()]
        assert "cannot read it to resend it as bytes" in caplog.text

    def test_a_link_out_of_the_media_root_is_quarantined_not_replayed(
        self, scene: _Scene, case: _Kind, tmp_path: Path
    ) -> None:
        """The containment check read the path's text, and opening the file follows links. A link
        under the root to a file outside it was resent as bytes, accepted, and the chunk replayed as
        if the inference's mount were at fault — when the inference only refused a path that leaves
        its root, as the worker must."""
        outside = tmp_path / "outside"
        outside.mkdir()
        for _, file_name in VIEWS.values():
            (scene.media_root / file_name).rename(outside / file_name)
            (scene.media_root / file_name).symlink_to(outside / file_name)
        # The real inference refuses a path whose file is outside its root; this one, every path.
        scene.server.reads_paths = False
        kind = case.make(API_KEY)

        result = scene.process(kind, _params(kind, case))

        assert sorted(item["item_id"] for item in result["quarantined"]) == sorted(VIEWS)
        assert [image for image in scene.server.images if image.startswith("data:")] == [witness_image()]

    def test_an_inference_that_stops_answering_when_asked_again_blames_no_image(
        self, scene: _Scene, case: _Kind
    ) -> None:
        """A medium is only blamed on an answer: silence on the resent bytes is an outage."""
        scene.server.reads_paths = False
        scene.server.bytes_answer = httpx.RemoteProtocolError("Server disconnected without sending a response.")
        kind = case.make(API_KEY)

        with pytest.raises(TransientError, match="stopped answering"):
            scene.process(kind, _params(kind, case))

    @pytest.mark.parametrize(
        ("status", "body"),
        [
            (httpx.codes.FORBIDDEN, {"error": {"code": "forbidden", "message": "Invalid API key."}}),
            (httpx.codes.OK, {"unexpected": "envelope"}),
        ],
        ids=["denied", "unreadable"],
    )
    def test_an_error_no_medium_causes_on_the_resend_fails_the_chunk(
        self, scene: _Scene, case: _Kind, status: int, body: dict[str, Any]
    ) -> None:
        """Such an error was taken for a refusal of the resent medium, and every sound image of the
        chunk went to quarantine. It fails the chunk, as it does on the kind's own call."""
        scene.server.reads_paths = False
        scene.server.bytes_answer = httpx.Response(status, json=body)
        kind = case.make(API_KEY)

        with pytest.raises(PixanoInferenceError) as raised:
            scene.process(kind, _params(kind, case))

        assert classify(raised.value) == "request"


class TestClassify:
    """Whose fault a failed call is, the one rule every inference kind applies."""

    @pytest.mark.parametrize(
        ("error", "failure"),
        [
            (httpx.ConnectError("refused"), "transient"),
            (PixanoInferenceError(0, "connection_error", "no answer"), "transient"),
            (PixanoInferenceError(503, "unavailable", "restarting"), "transient"),
            (PixanoInferenceError(403, "forbidden", "Invalid API key."), "request"),
            (PixanoInferenceError(500, "internal_error", "Inference error."), "medium"),
        ],
        ids=["no-transport", "no-response", "come-back-later", "denied", "refused"],
    )
    def test_each_family(self, error: Exception, failure: Failure) -> None:
        assert classify(error) == failure

    def test_an_answer_this_worker_cannot_read_is_the_requests_fault(self) -> None:
        """A successful answer that does not match the client's schema — a client and a server of
        different versions — was a medium's fault: the chunk was split down to each image, then
        replayed until its attempts ran out. No medium causes it."""
        error = PixanoInferenceError(httpx.codes.OK, "invalid_response", "not the expected envelope")

        assert classify(error) == "request"

    def test_what_is_not_a_failed_call_is_raised_again(self) -> None:
        with pytest.raises(ValueError, match="a bug"):
            classify(ValueError("a bug"))


class TestMediaDesignatedByUrl:
    """Bytes this worker sends say nothing of whether the inference reaches a URL's source: a URL is
    not resent, and its refusal goes to quarantine. Diagnosing a source per designation is step 3's."""

    @pytest.fixture
    def by_url(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Scene:
        return _make_scene(tmp_path, monkeypatch, lambda _root, name: f"{UNREACHABLE_HOST}/{name}")

    def test_a_refused_url_is_quarantined_without_being_resent(self, by_url: _Scene, case: _Kind) -> None:
        kind = case.make(API_KEY)

        result = by_url.process(kind, _params(kind, case))

        assert sorted(item["item_id"] for item in result["quarantined"]) == sorted(VIEWS)
        assert [image for image in by_url.server.images if image.startswith("data:")] == [witness_image()]

    @pytest.fixture
    def url_then_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> _Scene:
        """The first view designated by URL, the second by path."""
        url_file = VIEWS["v1"][1]
        return _make_scene(
            tmp_path,
            monkeypatch,
            lambda root, name: f"{UNREACHABLE_HOST}/{name}" if name == url_file else str(root / name),
        )

    def test_a_url_refused_ahead_of_a_path_leaves_the_path_to_be_resent(
        self, url_then_path: _Scene, case: _Kind
    ) -> None:
        """A URL was counted with the paths: refused first, it was the medium picked for the resend,
        this worker had no bytes for it, and the probe stopped before the path — the whole chunk
        went to quarantine."""
        url_then_path.server.reads_paths = False
        kind = case.make(API_KEY)

        with pytest.raises(TransientError, match=f"{INFERENCE_MEDIA_ROOT} — check PIXANO_INFERENCE_MEDIA_ROOT"):
            url_then_path.process(kind, _params(kind, case))

    def test_a_chunk_groups_its_media_by_designation(self, scene: _Scene) -> None:
        """Only a path is kept for resending: a URL is not one, whatever this worker could read."""
        dataset = Dataset.find(DATASET_ID, scene.library)
        dataset.add_records({"records": [Record(id="r3"), Record(id="r4")]})
        dataset.add_data(
            IMAGES_TABLE,
            [
                Image(id="by-url", record_id="r3", logical_name="image", uri=f"{UNREACHABLE_HOST}/c.png"),
                Image(id="embedded", record_id="r4", logical_name="image", raw_bytes=_png()),
            ],
            raise_or_warn="none",
        )
        reader = runner._reader_for(scene.library, DATASET_ID, scene.resolver, fresh=True)

        found = chunk_media(reader, IMAGES_TABLE, ["v1", "by-url", "embedded"])

        assert list(found.by_path) == ["v1"]
        assert found.carried_bytes == 1
        assert [reference for _, reference in found.media][:2] == [
            f"{INFERENCE_MEDIA_ROOT}/a.png",
            f"{UNREACHABLE_HOST}/c.png",
        ]
