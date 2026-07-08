# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import time
from pathlib import Path

import PIL.Image
import pytest
import yaml
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings


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
