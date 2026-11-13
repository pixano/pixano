# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import asyncio
import json
import time
from pathlib import Path

import PIL.Image
import psycopg
import pytest
import yaml
from fastapi.testclient import TestClient
from httpx import Response
from s3path import S3Path

from pixano.api.jobs.follow_ups import (
    EMBEDDINGS_KIND,
    NO_MODEL,
    NO_MODEL_SERVED,
    NO_WORKER_FOR_KIND,
    NOTHING_TO_COUNT,
    QUEUE_UNREADABLE,
    STATISTICS_KIND,
)
from pixano.api.main import create_app
from pixano.api.routers import data_io as data_io_router
from pixano.api.settings import Settings, get_settings
from pixano.datasets import Dataset
from pixano.datasets.io.jobs import JobStore
from pixano.inference.types import InferenceTask, ModelInfo
from tests.datasets.io._review_fixture import (
    DROPPED_ENTITIES,
    KEPT_ENTITIES,
    REVIEW_DATASET_NAME,
    build_review_dataset,
)
from tests.datasets.io.formats.test_jsonl_importer import SPECS, materialize_corpus
from tests.datasets.io.formats.test_lerobot_importer import make_v21_dataset, needs_ffmpeg
from tests.fixtures.job_queue import queued_jobs


@pytest.fixture()
def client_and_dirs(tmp_path: Path) -> tuple[TestClient, Path, Path]:
    data_dir = tmp_path / "data"
    (data_dir / "library").mkdir(parents=True)
    source = tmp_path / "src"
    (source / "train").mkdir(parents=True)
    for stem in ("a", "b", "c"):
        PIL.Image.new("RGB", (16, 16), (200, 30, 40)).save(source / "train" / f"{stem}.jpg")
    (source / "dataset.yaml").write_text(
        yaml.safe_dump({"pixano": 2, "format": "pixano_jsonl", "dataset": {"name": "io_ds", "workspace": "image"}})
    )
    settings = Settings(library_dir=str(data_dir / "library"))
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app), data_dir, source


def _wait_done(client: TestClient, job_id: str, timeout: float = 60.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        payload = client.get(f"/io/jobs/{job_id}").json()
        if payload["status"] in ("done", "error", "cancelled", "interrupted"):
            return payload
        time.sleep(0.05)
    raise AssertionError(f"job {job_id} did not finish: {payload}")


class _ServesEmbeddings:
    """An inference serving embeddings models, as the app's provider lists them; it counts the asks."""

    def __init__(self, *names: str, hangs: bool = False):
        self.names = names
        self.hangs = hangs
        self.asked = 0

    async def list_models(self, task: InferenceTask | None = None) -> list[ModelInfo]:
        self.asked += 1
        if self.hangs:
            await asyncio.sleep(HANGING_S)
        if task not in (None, InferenceTask.EMBEDDING):
            return []
        return [ModelInfo(name=name, task=InferenceTask.EMBEDDING.value) for name in self.names]


# An inference that hangs: far longer than the lookup is given, short enough that a regression fails
# the test rather than hold it.
HANGING_S = 10.0


def _embeddings_client(
    tmp_path: Path, served: tuple[str, ...] = ("clip",), providers: dict | None = None, **deployment: object
) -> TestClient:
    """A client of an app connected to an inference serving `served`, as deployed with `deployment`.

    `deployment` holds the environment variables of a deployment: PIXANO_DATABASE_URL,
    PIXANO_EMBEDDINGS_MODEL, ...
    """
    (tmp_path / "data" / "library").mkdir(parents=True, exist_ok=True)
    settings = Settings(
        library_dir=str(tmp_path / "data" / "library"),
        inference_providers=providers if providers is not None else {"inference": _ServesEmbeddings(*served)},
        default_inference_provider="inference",
        **deployment,
    )
    app = create_app(settings)
    app.dependency_overrides[get_settings] = lambda: settings
    return TestClient(app)


def _image_source(tmp_path: Path) -> Path:
    """A folder of images with its dataset.yaml, as the wizard uploads it."""
    source = tmp_path / "embeddings_src"
    (source / "train").mkdir(parents=True)
    for stem in ("a", "b"):
        PIL.Image.new("RGB", (16, 16), (20, 30, 200)).save(source / "train" / f"{stem}.jpg")
    (source / "dataset.yaml").write_text(
        yaml.safe_dump({"pixano": 2, "format": "pixano_jsonl", "dataset": {"name": "photos", "workspace": "image"}})
    )
    return source


class TestEmbeddingsAfterAnImport:
    def test_the_offer_says_why_the_job_cannot_run(self, tmp_path: Path):
        offer = _embeddings_client(tmp_path).get("/io/imports/embeddings").json()

        assert (offer["queue_configured"], offer["available"]) == (False, False)
        assert "PIXANO_DATABASE_URL" in offer["reason"]
        assert (offer["enabled_by_default"], offer["models"], offer["default_model"]) == (True, ["clip"], "clip")

    def test_the_offer_lists_a_model_two_inferences_serve_once(self, tmp_path: Path):
        providers = {"one": _ServesEmbeddings("clip", "siglip"), "two": _ServesEmbeddings("clip")}

        offer = _embeddings_client(tmp_path, providers=providers).get("/io/imports/embeddings").json()

        assert offer["models"] == ["clip", "siglip"]

    def test_the_offer_does_not_wait_for_an_inference_that_hangs(
        self, tmp_path: Path, embeddings_declared: str, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(data_io_router, "EMBEDDINGS_MODELS_LOOKUP_TIMEOUT_S", 0.05)
        client = _embeddings_client(
            tmp_path,
            providers={"inference": _ServesEmbeddings("clip", hangs=True)},
            PIXANO_DATABASE_URL=embeddings_declared,
        )

        offer = client.get("/io/imports/embeddings").json()

        assert (offer["available"], offer["reason"], offer["models"]) == (False, NO_MODEL_SERVED, [])

    def test_the_offer_proposes_the_deployments_model_first(self, tmp_path: Path):
        """Named by the deployment, it may be served only by the worker's inference."""
        client = _embeddings_client(tmp_path, PIXANO_EMBEDDINGS_MODEL="siglip", PIXANO_EMBEDDINGS_AFTER_IMPORT=False)

        offer = client.get("/io/imports/embeddings").json()

        assert (offer["enabled_by_default"], offer["models"], offer["default_model"]) == (
            False,
            ["siglip", "clip"],
            "siglip",
        )

    def test_the_offer_where_the_job_can_run(self, tmp_path: Path, embeddings_declared: str):
        offer = (
            _embeddings_client(tmp_path, PIXANO_DATABASE_URL=embeddings_declared).get("/io/imports/embeddings").json()
        )

        assert (offer["queue_configured"], offer["available"], offer["reason"]) == (True, True, None)

    def test_the_offer_without_a_model_to_name(self, tmp_path: Path, embeddings_declared: str):
        client = _embeddings_client(tmp_path, served=(), PIXANO_DATABASE_URL=embeddings_declared)

        offer = client.get("/io/imports/embeddings").json()

        assert (offer["available"], offer["reason"], offer["models"]) == (False, NO_MODEL_SERVED, [])

    def test_by_default_an_import_queues_the_embeddings_of_what_it_imported(
        self, tmp_path: Path, embeddings_declared: str
    ):
        """Through the queue a worker declared the job on, with the model the inference serves."""
        client = _embeddings_client(tmp_path, PIXANO_DATABASE_URL=embeddings_declared)

        started = client.post("/io/imports", json={"source": str(_image_source(tmp_path))})
        final = _wait_done(client, started.json()["job_id"])

        assert final["status"] == "done", final["error"]
        (follow_up,) = final["follow_ups"]
        assert follow_up["job_id"] and not follow_up["error"], follow_up
        assert queued_jobs(embeddings_declared) == [(EMBEDDINGS_KIND, final["dataset"], {"model": "clip"})]

    def test_by_default_an_import_where_the_job_cannot_run_asks_nothing(self, tmp_path: Path):
        """No queue: the import ends as it did before the embeddings could follow it."""
        client = _embeddings_client(tmp_path)

        started = client.post("/io/imports", json={"source": str(_image_source(tmp_path))})

        assert started.json()["follow_ups"] == []
        assert _wait_done(client, started.json()["job_id"])["follow_ups"] == []

    def test_asked_off_none(self, tmp_path: Path, embeddings_declared: str):
        client = _embeddings_client(tmp_path, PIXANO_DATABASE_URL=embeddings_declared)

        started = client.post(
            "/io/imports", json={"source": str(_image_source(tmp_path)), "compute_embeddings": False}
        )
        _wait_done(client, started.json()["job_id"])

        assert queued_jobs(embeddings_declared) == []

    def test_asked_for_the_import_says_why_it_was_not_queued(self, tmp_path: Path):
        client = _embeddings_client(tmp_path)

        started = client.post(
            "/io/imports",
            json={"source": str(_image_source(tmp_path)), "compute_embeddings": True, "embeddings_model": "siglip"},
        )
        final = _wait_done(client, started.json()["job_id"])

        assert final["status"] == "done", final["error"]
        (follow_up,) = final["follow_ups"]
        assert follow_up["params"] == {"model": "siglip"} and not follow_up["job_id"]
        assert follow_up["error"].startswith("not queued: no job queue is configured")

    def test_asked_for_without_a_model_the_answer_says_so(self, tmp_path: Path):
        client = _embeddings_client(tmp_path, served=())

        started = client.post("/io/imports", json={"source": str(_image_source(tmp_path)), "compute_embeddings": True})
        final = _wait_done(client, started.json()["job_id"])

        assert started.status_code == 202
        assert started.json()["follow_ups"] == [
            {"kind": EMBEDDINGS_KIND, "params": {}, "job_id": "", "error": f"not queued: {NO_MODEL}", "skipped": ""}
        ]
        assert final["follow_ups"] == started.json()["follow_ups"]

    def test_the_statistics_offer_says_why_their_job_cannot_run(self, tmp_path: Path):
        offer = _embeddings_client(tmp_path).get("/io/imports/statistics").json()

        assert (offer["queue_configured"], offer["available"], offer["enabled_by_default"]) == (False, False, True)
        assert "PIXANO_DATABASE_URL" in offer["reason"]

    def test_the_statistics_offer_follows_the_deployments_default(self, tmp_path: Path):
        client = _embeddings_client(tmp_path, PIXANO_STATISTICS_AFTER_IMPORT=False)

        assert client.get("/io/imports/statistics").json()["enabled_by_default"] is False

    def test_the_statistics_offer_where_their_job_can_run(self, tmp_path: Path, statistics_declared: str):
        client = _embeddings_client(tmp_path, PIXANO_DATABASE_URL=statistics_declared)

        offer = client.get("/io/imports/statistics").json()

        assert (offer["queue_configured"], offer["available"], offer["reason"]) == (True, True, None)

    def test_the_statistics_offer_where_no_worker_runs_their_job(self, tmp_path: Path, embeddings_declared: str):
        client = _embeddings_client(tmp_path, PIXANO_DATABASE_URL=embeddings_declared)

        offer = client.get("/io/imports/statistics").json()

        assert (offer["available"], offer["reason"]) == (False, NO_WORKER_FOR_KIND.format(kind=STATISTICS_KIND))

    def test_asked_for_the_default_statistics_the_import_says_they_were_not_needed(self, tmp_path: Path):
        """Fitted to the dataset first: images and no object, nothing to count, whatever the queue."""
        client = _embeddings_client(tmp_path)

        started = client.post("/io/imports", json={"source": str(_image_source(tmp_path)), "compute_statistics": True})
        final = _wait_done(client, started.json()["job_id"])

        (follow_up,) = final["follow_ups"]
        assert (follow_up["kind"], follow_up["skipped"], follow_up["error"]) == (STATISTICS_KIND, NOTHING_TO_COUNT, "")

    def test_by_default_the_statistics_follow_where_their_job_can_run_and_say_when_nothing_counts(
        self, tmp_path: Path, statistics_declared: str
    ):
        """Images and no object: the embeddings are queued, the statistics have nothing to count."""
        client = _embeddings_client(tmp_path, PIXANO_DATABASE_URL=statistics_declared)

        started = client.post("/io/imports", json={"source": str(_image_source(tmp_path))})
        final = _wait_done(client, started.json()["job_id"])

        embeddings, statistics = final["follow_ups"]
        assert (embeddings["kind"], bool(embeddings["job_id"])) == (EMBEDDINGS_KIND, True)
        assert (statistics["kind"], statistics["skipped"], statistics["error"]) == (
            STATISTICS_KIND,
            NOTHING_TO_COUNT,
            "",
        )

    def test_a_model_named_asks_for_the_job(self, tmp_path: Path):
        """Without saying whether to compute them: naming the model is asking."""
        client = _embeddings_client(tmp_path)

        started = client.post(
            "/io/imports", json={"source": str(_image_source(tmp_path)), "embeddings_model": "siglip"}
        )
        final = _wait_done(client, started.json()["job_id"])

        (follow_up,) = final["follow_ups"]
        assert follow_up["params"] == {"model": "siglip"}
        assert follow_up["error"].startswith("not queued: no job queue is configured")

    def test_by_default_an_import_where_the_job_cannot_run_never_asks_the_inference(self, tmp_path: Path):
        """An installation without a queue never waits for the inference to start an import."""
        inference = _ServesEmbeddings("clip")
        client = _embeddings_client(tmp_path, providers={"inference": inference})

        started = client.post("/io/imports", json={"source": str(_image_source(tmp_path))})
        _wait_done(client, started.json()["job_id"])

        assert inference.asked == 0

    def test_by_default_a_saved_plan_without_a_still_image_asks_nothing(
        self, tmp_path: Path, embeddings_declared: str
    ):
        """A video's frames are not still images: its import reads no refusal."""
        source = materialize_corpus("frames_masks", tmp_path / "frames_src")
        (source / "dataset.yaml").write_text(
            yaml.safe_dump({"pixano": 2, "format": "pixano_jsonl", **SPECS["frames_masks"]}, sort_keys=False)
        )
        client = _embeddings_client(tmp_path, PIXANO_DATABASE_URL=embeddings_declared)

        plan = client.post("/io/analyze", json={"source": str(source), "spec": {}}).json()
        started = client.post("/io/imports", json={"plan_id": plan["plan_id"], "source": str(source)})
        final = _wait_done(client, started.json()["job_id"])

        assert final["status"] == "done", final["error"]
        assert final["follow_ups"] == [] and queued_jobs(embeddings_declared) == []

    def test_a_queue_that_fails_once_connected_never_fails_the_import(
        self, tmp_path: Path, embeddings_declared: str, monkeypatch: pytest.MonkeyPatch
    ):
        """A role without the rights, a server restarting: the import starts all the same."""

        def failing(conn: object) -> None:
            raise psycopg.errors.InsufficientPrivilege("permission denied for schema pixano_jobs")

        monkeypatch.setattr("pixano.api.jobs.follow_ups.available_kinds", failing)
        client = _embeddings_client(tmp_path, PIXANO_DATABASE_URL=embeddings_declared)

        offer = client.get("/io/imports/embeddings")
        started = client.post("/io/imports", json={"source": str(_image_source(tmp_path))})

        assert offer.status_code == 200 and offer.json()["reason"] == QUEUE_UNREADABLE
        assert started.status_code == 202
        assert _wait_done(client, started.json()["job_id"])["status"] == "done"


class TestS3LibraryGuards:
    @staticmethod
    def settings(tmp_path: Path) -> Settings:
        # Bypass credential registration: these checks never access S3.
        return Settings.model_construct(
            library_dir=S3Path.from_uri("s3://test-bucket/data/library"),
            models_dir=tmp_path / "models",
        )

    def test_server_skips_local_boot_recovery_for_s3(self, tmp_path: Path, monkeypatch):
        recovered = []
        monkeypatch.setattr("pixano.datasets.io.jobs.boot_recover", lambda path: recovered.append(path))
        app = create_app(self.settings(tmp_path))
        assert recovered == []
        assert TestClient(app).get("/health").json() == {"status": "ok"}

    def test_server_still_recovers_local_library(self, tmp_path: Path, monkeypatch):
        recovered = []
        monkeypatch.setattr("pixano.datasets.io.jobs.boot_recover", lambda path: recovered.append(path))
        create_app(Settings(data_dir=tmp_path))
        assert recovered == [tmp_path]

    @pytest.mark.parametrize(
        "method,path,payload",
        [
            ("GET", "/io/jobs", None),
            ("POST", "/io/uploads", None),
            ("POST", "/io/analyze", {"source": "/unused/source"}),
            ("POST", "/io/imports", {"source": "/unused/source"}),
        ],
    )
    def test_data_io_rejects_s3_before_creating_local_state(self, tmp_path: Path, monkeypatch, method, path, payload):
        settings = self.settings(tmp_path)
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings

        def unexpected_store(*args, **kwargs):
            raise AssertionError("An S3 library must never create a local job store")

        monkeypatch.setattr("pixano.datasets.io.jobs.JobStore.for_data_dir", unexpected_store)
        response = TestClient(app).request(method, path, json=payload)
        assert response.status_code == 400, response.text
        assert "requires local storage" in response.json()["detail"]
        assert not (tmp_path / ".pixano").exists()


class TestIoRoutes:
    def test_formats_lists_builtins(self, client_and_dirs):
        client, _, _ = client_and_dirs
        names = {f["name"] for f in client.get("/io/formats").json()}
        assert {"pixano_jsonl", "coco", "lerobot"} <= names

    def test_analyze_import_poll_done(self, client_and_dirs):
        client, data_dir, source = client_and_dirs

        analyzed = client.post("/io/analyze", json={"source": str(source), "spec": {}}).json()
        assert analyzed["totals"]["records"] == 3
        assert analyzed["plan_id"]
        assert analyzed["inferred_schema"]["record"]["base"] == "Record"
        assert analyzed["inferred_schema"]["views"]["image"]["base"] == "Image"

        started = client.post("/io/imports", json={"plan_id": analyzed["plan_id"], "source": str(source)})
        assert started.status_code == 202
        final = _wait_done(client, started.json()["job_id"])
        assert final["status"] == "done", final["error"]
        assert final["progress"]["table_counts"]["records"] == 3
        assert (data_dir / "library" / "io_ds").is_dir()

    def test_analyze_raw_folder_with_custom_entity_attrs(self, client_and_dirs, tmp_path: Path):
        """The wizard's raw-media flow: bare view folders + a UI-built schema."""
        client, data_dir, _ = client_and_dirs
        raw = tmp_path / "raw_views"
        for view in ("left", "right"):
            (raw / view).mkdir(parents=True)
            for stem in ("a", "b"):
                PIL.Image.new("RGB", (16, 16), (10, 120, 200)).save(raw / view / f"{stem}.jpg")
        spec = {
            "format": "pixano_jsonl",
            "dataset": {"name": "raw_ds", "workspace": "image"},
            "schema": {"entity": {"attrs": {"category": "str"}}, "annotations": ["bbox", "classification"]},
        }

        analyzed = client.post("/io/analyze", json={"source": str(raw), "spec": spec}).json()
        assert analyzed["totals"]["records"] == 2
        schema = analyzed["inferred_schema"]
        assert set(schema["views"]) == {"left", "right"}
        assert schema["entity"]["fields"]["category"]["type"] == "str"
        assert "classification" in schema and "keypoint" not in schema

        started = client.post("/io/imports", json={"plan_id": analyzed["plan_id"], "source": str(raw), "spec": spec})
        assert started.status_code == 202
        final = _wait_done(client, started.json()["job_id"])
        assert final["status"] == "done", final["error"]
        assert final["progress"]["table_counts"] == {"records": 2, "images": 4}
        assert (data_dir / "library" / "raw_ds").is_dir()

    @needs_ffmpeg
    @pytest.mark.parametrize("frames", ["extract", "reference"])
    def test_lerobot_custom_schema_survives_analyze_import_and_annotation(
        self, client_and_dirs, tmp_path: Path, frames: str
    ):
        """The wizard's schema remains usable after executing the reviewed plan."""
        client, data_dir, _ = client_and_dirs
        source = make_v21_dataset(tmp_path / "robot_source", episodes=1)
        spec = {
            "format": "lerobot",
            "dataset": {"name": "robot_schema"},
            "options": {"frames": frames, "max_frames_per_episode": 2},
            "schema": {
                "record": {"attrs": {"reviewed": {"type": "bool", "default": False}}},
                "entity": {
                    "attrs": {
                        "category": {"type": "str", "required": True},
                        "occluded": {"type": "bool", "default": True},
                        "tags": {"type": "str", "collection": True, "default": ["wood"]},
                    }
                },
                "annotations": ["bbox", "tracklet", "classification"],
            },
        }
        response = client.post("/io/analyze", json={"source": str(source), "spec": spec})
        assert response.status_code == 200, response.text
        plan = response.json()
        assert plan["totals"]["records"] == 1
        assert not plan["report"]["findings"], plan["report"]
        schema = plan["inferred_schema"]
        assert set(schema["views"]) == {"top"}
        assert {"episode_index", "tasks", "length", "reviewed"} <= set(schema["record"]["fields"])
        assert schema["entity"]["fields"]["category"]["required"] is True
        assert "classification" in schema and "mask" not in schema
        assert ("timeseries" in schema) == (frames == "extract")

        started = client.post("/io/imports", json={"plan_id": plan["plan_id"], "source": str(source), "spec": spec})
        assert started.status_code == 202, started.text
        final = _wait_done(client, started.json()["job_id"])
        assert final["status"] == "done", final["error"]
        dataset = Dataset(data_dir / "library" / "robot_schema")
        assert dataset.info.workspace.value == "video"
        record = dataset.get_data("records")[0]
        assert record.episode_index == 0
        assert record.tasks == ["task 0"]
        assert record.reviewed is False
        assert set(dataset.info.views) == {"top"}
        if frames == "extract":
            assert dataset.open_table("sequence_frames").count_rows() == 2
            assert dataset.open_table("timeseries").count_rows() == 2

        details = client.get(f"/datasets/{dataset.info.id}")
        assert details.status_code == 200, details.text
        entity_fields = details.json()["info"]["entity"]["fields"]
        assert entity_fields["category"]["required"] is True
        assert entity_fields["occluded"]["default"] is True
        assert entity_fields["tags"]["collection"] is True
        assert entity_fields["tags"]["default"] == ["wood"]

        entity_url = f"/datasets/{dataset.info.id}/entities"
        created = client.post(entity_url, json={"id": "block", "record_id": record.id, "category": "block"})
        assert created.status_code == 201, created.text
        assert created.json()["occluded"] is True
        assert created.json()["tags"] == ["wood"]
        updated = client.put(f"{entity_url}/block", json={"occluded": False, "tags": ["wood", "red"]})
        assert updated.status_code == 200, updated.text
        saved = client.get(f"{entity_url}/block")
        assert saved.status_code == 200, saved.text
        assert saved.json()["category"] == "block"
        assert saved.json()["occluded"] is False
        assert saved.json()["tags"] == ["wood", "red"]

    def test_upload_analyze_import_and_eager_gc(self, client_and_dirs):
        """The wizard's client-upload flow: stage files, import, session removed."""
        import io

        client, data_dir, _ = client_and_dirs
        session = client.post("/io/uploads").json()
        source = Path(session["source"])
        assert source.is_dir() and source.parent.name == "uploads"

        jpeg = io.BytesIO()
        PIL.Image.new("RGB", (16, 16), (10, 120, 200)).save(jpeg, format="JPEG")
        for rel in ("left/a.jpg", "left/b.jpg", "right/a.jpg", "right/b.jpg"):
            put = client.put(f"/io/uploads/{session['upload_id']}/files/{rel}", content=jpeg.getvalue())
            assert put.status_code == 200
            assert put.json() == {"path": rel, "bytes": len(jpeg.getvalue())}

        spec = {"format": "pixano_jsonl", "dataset": {"name": "uploaded_ds", "workspace": "image"}}
        analyzed = client.post("/io/analyze", json={"source": str(source), "spec": spec}).json()
        assert analyzed["totals"]["records"] == 2
        assert set(analyzed["inferred_schema"]["views"]) == {"left", "right"}

        started = client.post(
            "/io/imports", json={"plan_id": analyzed["plan_id"], "source": str(source), "spec": spec}
        )
        final = _wait_done(client, started.json()["job_id"])
        assert final["status"] == "done", final["error"]
        assert (data_dir / "library" / "uploaded_ds").is_dir()
        # Eager GC: the staged upload is disposable after import. The job thread
        # removes it just after recording "done", so wait for it rather than race it.
        deadline = time.monotonic() + 10.0
        while source.exists() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not source.exists()

    def test_upload_import_without_dataset_name_is_rejected(self, client_and_dirs):
        """A staged upload's folder name is an opaque id — never a dataset name."""
        import io

        client, _, _ = client_and_dirs
        session = client.post("/io/uploads").json()
        jpeg = io.BytesIO()
        PIL.Image.new("RGB", (16, 16), (10, 120, 200)).save(jpeg, format="JPEG")
        client.put(f"/io/uploads/{session['upload_id']}/files/a.jpg", content=jpeg.getvalue())

        spec = {"format": "pixano_jsonl", "dataset": {"workspace": "image"}}
        started = client.post("/io/imports", json={"source": session["source"], "spec": spec})
        assert started.status_code == 422
        assert "dataset.name" in started.json()["detail"]

    def test_upload_session_validation(self, client_and_dirs):
        client, _, _ = client_and_dirs
        session = client.post("/io/uploads").json()
        upload_id = session["upload_id"]
        # Traversal must be encoded to reach the route (the HTTP layer already
        # normalizes literal ".." away); the validator rejects what gets through.
        for bad in ("%2E%2E%2Fevil.txt", "a%2F..%2F..%2Fevil.txt", "a%2F%2Fb.txt", "a%5C..%5Cb.txt"):
            assert client.put(f"/io/uploads/{upload_id}/files/{bad}", content=b"x").status_code == 400
        assert client.put("/io/uploads/ghost/files/ok.txt", content=b"x").status_code == 404
        assert client.delete(f"/io/uploads/{upload_id}").status_code == 204
        assert not Path(session["source"]).exists()
        assert client.delete(f"/io/uploads/{upload_id}").status_code == 404

    def test_upload_boot_gc_removes_stale_orphans(self, client_and_dirs):
        import os

        from pixano.datasets.io.jobs import boot_recover

        client, data_dir, _ = client_and_dirs
        stale = Path(client.post("/io/uploads").json()["source"])
        fresh = Path(client.post("/io/uploads").json()["source"])
        (stale / "old.jpg").write_bytes(b"x")
        two_days_ago = time.time() - 48 * 3600
        os.utime(stale, (two_days_ago, two_days_ago))

        boot_recover(data_dir)
        assert not stale.exists()
        assert fresh.exists()

    def test_analyze_refuses_user_python(self, client_and_dirs):
        client, _, source = client_and_dirs
        response = client.post("/io/analyze", json={"source": str(source), "spec": {"importer": "evil.py:Cls"}})
        assert response.status_code == 400

    def test_import_with_unknown_plan_conflicts(self, client_and_dirs):
        client, _, source = client_and_dirs
        response = client.post("/io/imports", json={"plan_id": "ghost", "source": str(source)})
        assert response.status_code == 409

    def test_export_job(self, client_and_dirs, tmp_path: Path):
        client, _, source = client_and_dirs
        started = client.post("/io/imports", json={"source": str(source), "spec": {}})
        assert _wait_done(client, started.json()["job_id"])["status"] == "done"

        exported = client.post(
            "/io/exports",
            json={"dataset": "io_ds", "destination": str(tmp_path / "out"), "format": "pixano_jsonl"},
        )
        assert exported.status_code == 202
        final = _wait_done(client, exported.json()["job_id"])
        assert final["status"] == "done", final["error"]
        assert (tmp_path / "out" / "dataset.yaml").is_file()

    def test_jobs_listing_and_cancel_conflicts(self, client_and_dirs):
        client, _, source = client_and_dirs
        started = client.post("/io/imports", json={"source": str(source), "spec": {}})
        job_id = started.json()["job_id"]
        _wait_done(client, job_id)
        assert any(job["job_id"] == job_id for job in client.get("/io/jobs").json())
        assert client.post(f"/io/jobs/{job_id}/cancel").status_code == 409  # already terminal
        assert client.get("/io/jobs/ghost").status_code == 404

    def test_interrupted_after_restart(self, client_and_dirs, tmp_path: Path):
        client, data_dir, _ = client_and_dirs
        from pixano.datasets.io.jobs import JobStore

        store = JobStore.for_data_dir(data_dir)
        orphan = store.create_job("import")
        store.update_job(orphan.id, status="running", pid=999_999_999)

        settings = Settings(library_dir=str(data_dir / "library"))
        app2 = create_app(settings)  # boot hook runs recovery
        app2.dependency_overrides[get_settings] = lambda: settings
        restarted = TestClient(app2)
        assert restarted.get(f"/io/jobs/{orphan.id}").json()["status"] == "interrupted"

    def test_resume_and_rollback_conflict_on_unknown_jobs(self, client_and_dirs):
        client, _, _ = client_and_dirs
        assert client.post("/io/jobs/x/resume").status_code == 409  # unknown job
        assert client.delete("/io/jobs/x").status_code == 409  # unknown job


class TestLegacyAliasParity:
    def test_exact_legacy_client_sequence(self, client_and_dirs, tmp_path: Path):
        client, data_dir, _ = client_and_dirs
        photos = tmp_path / "photos"
        photos.mkdir()
        for stem in ("x", "y"):
            PIL.Image.new("RGB", (8, 8), (1, 2, 3)).save(photos / f"{stem}.jpg")

        response = client.post(
            "/datasets/import",
            json={"source_dir": str(photos), "import_type": "unlabeled_images", "dataset_name": "My Photos"},
        )
        assert response.status_code == 200
        body = response.json()
        assert set(body) == {"job_id", "status", "message", "dataset_id"}  # legacy shape

        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            body = client.get(f"/datasets/import/{body['job_id']}").json()
            assert set(body) == {"job_id", "status", "message", "dataset_id"}
            if body["status"] in ("done", "error"):
                break
            time.sleep(0.05)
        assert body["status"] == "done", body["message"]
        assert "2 item(s)" in body["message"]
        assert (data_dir / "library" / "my_photos").is_dir()

    def test_alias_and_io_share_the_store(self, client_and_dirs, tmp_path: Path):
        client, _, _ = client_and_dirs
        photos = tmp_path / "photos2"
        photos.mkdir()
        PIL.Image.new("RGB", (8, 8), (9, 9, 9)).save(photos / "only.jpg")
        job_id = client.post(
            "/datasets/import", json={"source_dir": str(photos), "import_type": "unlabeled_images"}
        ).json()["job_id"]
        _wait_done(client, job_id)
        assert client.get(f"/io/jobs/{job_id}").json()["kind"] == "import"

    def test_unknown_type_and_missing_dir(self, client_and_dirs):
        client, _, _ = client_and_dirs
        assert client.post("/datasets/import", json={"source_dir": "/tmp", "import_type": "bogus"}).status_code == 400
        assert client.post("/datasets/import", json={"source_dir": "/nope/missing"}).status_code == 400


class TestExportByReviewStatus:
    """POST /io/exports takes the review selection of the shared ExportSpec (spec amendment 2026-10-05)."""

    @staticmethod
    def _start(client: TestClient, destination: Path, **fields) -> Response:
        payload = {"dataset": REVIEW_DATASET_NAME, "destination": str(destination), **fields}
        return client.post("/io/exports", json=payload)

    @staticmethod
    def _exported_entities(destination: Path) -> set[str]:
        lines = (destination / "train" / "metadata.jsonl").read_text(encoding="utf-8").splitlines()
        return {entity["id"] for entity in json.loads(lines[1])["entities"]}

    @pytest.mark.parametrize(
        ("requested", "recorded", "exported"),
        [
            pytest.param(["accepted", "accepted"], ["accepted"], KEPT_ENTITIES, id="accepted-without-repeats"),
            pytest.param(
                ["accepted", "pending"],
                ["pending", "accepted"],
                KEPT_ENTITIES | DROPPED_ENTITIES,
                id="both-in-declaration-order",
            ),
        ],
    )
    def test_the_export_job_applies_and_records_the_selection(
        self, client_and_dirs, tmp_path: Path, requested: list[str], recorded: list[str], exported: set[str]
    ):
        client, data_dir, _ = client_and_dirs
        build_review_dataset(data_dir / "library" / REVIEW_DATASET_NAME)

        started = self._start(client, tmp_path / "out", review_statuses=requested)

        assert started.status_code == 202
        final = _wait_done(client, started.json()["job_id"])
        assert final["status"] == "done", final["error"]
        assert self._exported_entities(tmp_path / "out") == exported
        job = JobStore.for_data_dir(data_dir).get_job(started.json()["job_id"])
        assert job.spec["review_statuses"] == recorded

    def test_an_export_job_without_selection_exports_everything(self, client_and_dirs, tmp_path: Path):
        client, data_dir, _ = client_and_dirs
        build_review_dataset(data_dir / "library" / REVIEW_DATASET_NAME)

        started = self._start(client, tmp_path / "out")

        final = _wait_done(client, started.json()["job_id"])
        assert final["status"] == "done", final["error"]
        assert self._exported_entities(tmp_path / "out") == KEPT_ENTITIES | DROPPED_ENTITIES
        assert "review_statuses" not in JobStore.for_data_dir(data_dir).get_job(started.json()["job_id"]).spec

    @pytest.mark.parametrize(
        "fields",
        [
            pytest.param({"review_statuses": ["bogus"]}, id="unknown-status"),
            # A reject deletes the row, and a saved edit accepts it: neither is a status.
            pytest.param({"review_statuses": ["rejected"]}, id="rejected-status"),
            pytest.param({"review_statuses": ["corrected"]}, id="corrected-status"),
            pytest.param({"review_statuses": [""]}, id="empty-status"),
            pytest.param({"options": {"review_statuses": ["accepted"]}}, id="selection-as-format-option"),
        ],
    )
    def test_an_invalid_selection_is_refused_without_a_job(self, client_and_dirs, tmp_path: Path, fields: dict):
        client, data_dir, _ = client_and_dirs
        build_review_dataset(data_dir / "library" / REVIEW_DATASET_NAME)

        response = self._start(client, tmp_path / "out", **fields)

        assert response.status_code == 422
        assert JobStore.for_data_dir(data_dir).list_jobs() == []
        assert not (tmp_path / "out").exists()


class TestTimeSeriesDatasetSerialization:
    def test_datasets_listing_survives_a_timeseries_slot(self, tmp_path: Path):
        # Regression: the timeseries slot class leaked into JSON serialization
        # and 500'd GET /datasets for the whole library.
        from pixano.datasets import Dataset, DatasetInfo
        from pixano.schemas import Record, SequenceFrame, create_timeseries_schema

        library = tmp_path / "lib" / "library"
        library.mkdir(parents=True)
        info = DatasetInfo(
            name="robo",
            record=Record,
            timeseries=create_timeseries_schema({"action": 3, "observation_state": 3}),
            views={"top": SequenceFrame},
        )
        Dataset.create(library / "robo", info)

        settings = Settings(library_dir=str(library))
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        client = TestClient(app)

        listing = client.get("/datasets")
        assert listing.status_code == 200
        payload = listing.json()[0]
        assert payload["timeseries"]["fields"]["action"]["type"] == "FixedSizeList"
        assert payload["timeseries"]["fields"]["action"]["dim"] == 3

        detail = client.get(f"/datasets/{payload['id']}/info")
        assert detail.status_code == 200
        assert detail.json()["timeseries"]["fields"]["observation_state"]["dim"] == 3


class TestSframeBatchPagination:
    def test_all_chunks_of_a_long_episode_are_served(self, tmp_path: Path):
        # Regression: lancedb plain scans apply `limit` pre-filter, so batches
        # past the first (and any record whose rows aren't at the table head)
        # returned 404 — playback appeared truncated at 128 frames.
        import io

        from pixano.datasets import Dataset, DatasetInfo
        from pixano.schemas import Record, SequenceFrame

        library = tmp_path / "lib" / "library"
        library.mkdir(parents=True)
        info = DatasetInfo(name="clips", record=Record, views={"cam": SequenceFrame})
        dataset = Dataset.create(library / "clips", info)

        jpeg = PIL.Image.new("RGB", (4, 4), (5, 6, 7))
        buffer = io.BytesIO()
        jpeg.save(buffer, "JPEG")
        blob = buffer.getvalue()
        for record_index in range(2):
            record = Record(id=f"rec{record_index}", split="train")
            frames = [
                SequenceFrame(
                    id=f"r{record_index}f{i}",
                    record_id=record.id,
                    logical_name="cam",
                    uri="",
                    raw_bytes=blob,
                    width=4,
                    height=4,
                    format="JPEG",
                    frame_index=i,
                    timestamp=i / 10,
                )
                for i in range(150)
            ]
            dataset.add_records({"records": record, "sequence_frames": frames}, check_integrity="none")

        settings = Settings(library_dir=str(library))
        app = create_app(settings)
        app.dependency_overrides[get_settings] = lambda: settings
        client = TestClient(app)
        dataset_id = dataset.info.id

        # rec1's rows live past the first 150 table rows — the old code 404'd
        # for every one of its batches beyond the scan head.
        for record_id, starts in (("rec0", (0, 128)), ("rec1", (0, 128))):
            served = 0
            for start in starts:
                response = client.get(
                    f"/datasets/{dataset_id}/records/{record_id}/sframes/batch",
                    params={"view_name": "cam", "start_frame": start, "batch_size": 128},
                )
                assert response.status_code == 200, (record_id, start)
                served += response.content.count(b"X-Frame-Index") + response.content.count(b"x-frame-index")
            assert served == 150, record_id

    def test_filtered_list_of_a_non_head_record_is_complete(self, tmp_path: Path):
        from pixano.datasets import Dataset, DatasetInfo
        from pixano.datasets.queries import TableQueryBuilder
        from pixano.schemas import Entity, Record

        library = tmp_path / "lib2" / "library"
        library.mkdir(parents=True)
        info = DatasetInfo(name="ents", record=Record, entity=Entity)
        dataset = Dataset.create(library / "ents", info)
        for record_index in range(3):
            record = Record(id=f"rec{record_index}", split="train")
            entities = [Entity(id=f"r{record_index}e{i}", record_id=record.id) for i in range(120)]
            dataset.add_records({"records": record, "entities": entities}, check_integrity="none")

        table = dataset.open_table("entities")
        rows = TableQueryBuilder(table).select(["id"]).where("record_id = 'rec2'").limit(100).to_list()
        assert len(rows) == 100  # previously 0: rec2's rows sit past the first 100 scanned
