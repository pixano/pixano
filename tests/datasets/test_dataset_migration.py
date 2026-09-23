# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.locking import dataset_mutation_lock, mutation_token
from pixano.schemas import BBox, Image, Record, Video


def _make_video_dataset(path: Path) -> Dataset:
    info = DatasetInfo(name="video_ds", record=Record, views={"video": Video})
    dataset = Dataset.create(path, info)
    dataset.add_records(
        {
            "records": Record(id="rec1"),
            "videos": Video(
                id="vid1",
                record_id="rec1",
                logical_name="video",
                uri="videos/clip.mp4",
                num_frames=10,
                fps=25.0,
                width=64,
                height=48,
                format="mp4",
                duration=0.4,
            ),
        },
        check_integrity="none",
    )
    return dataset


def _downgrade_to_spec_version_1(path: Path) -> None:
    """Rewrite a freshly built dataset into the pre-window, pre-spec_version layout."""
    dataset = Dataset(path)
    dataset.open_table("videos").drop_columns(["from_timestamp", "to_timestamp"])
    info_file = path / Dataset._INFO_FILE
    info_json = json.loads(info_file.read_text(encoding="utf-8"))
    info_json.pop("spec_version", None)
    info_file.write_text(json.dumps(info_json, indent=4), encoding="utf-8")


def _open_dataset(path_str: str) -> None:
    import os

    from pixano.datasets import Dataset  # noqa: PLC0415 (spawned process)

    dataset = Dataset(Path(path_str))
    assert "from_timestamp" in dataset.open_table("videos").schema.names
    # Skip interpreter finalization: lance's native background threads can crash
    # CPython teardown (PyGILState_Release) in short-lived spawned workers.
    os._exit(0)


class TestSpecVersion2Migration:
    def test_backfill_on_open(self, tmp_path: Path):
        dataset_path = tmp_path / "video_ds"
        _make_video_dataset(dataset_path)
        _downgrade_to_spec_version_1(dataset_path)

        dataset = Dataset(dataset_path)

        assert dataset.info.spec_version == Dataset._CURRENT_SPEC_VERSION
        schema_names = dataset.open_table("videos").schema.names
        assert "from_timestamp" in schema_names
        assert "to_timestamp" in schema_names

        info_json = json.loads((dataset_path / Dataset._INFO_FILE).read_text(encoding="utf-8"))
        assert info_json["spec_version"] == Dataset._CURRENT_SPEC_VERSION

        videos = dataset.get_data("videos")
        assert len(videos) == 1
        assert videos[0].from_timestamp == 0.0
        assert videos[0].to_timestamp == -1.0

    def test_migration_is_idempotent(self, tmp_path: Path):
        dataset_path = tmp_path / "video_ds"
        _make_video_dataset(dataset_path)
        _downgrade_to_spec_version_1(dataset_path)

        Dataset(dataset_path)
        first_pass = (dataset_path / Dataset._INFO_FILE).read_text(encoding="utf-8")
        Dataset(dataset_path)
        second_pass = (dataset_path / Dataset._INFO_FILE).read_text(encoding="utf-8")

        assert first_pass == second_pass

    def test_writes_succeed_after_migration(self, tmp_path: Path):
        dataset_path = tmp_path / "video_ds"
        _make_video_dataset(dataset_path)
        _downgrade_to_spec_version_1(dataset_path)

        dataset = Dataset(dataset_path)
        dataset.add_data(
            "videos",
            [
                Video(
                    id="vid2",
                    record_id="rec1",
                    logical_name="video",
                    uri="videos/clip.mp4",
                    num_frames=5,
                    fps=25.0,
                    width=64,
                    height=48,
                    format="mp4",
                    duration=0.2,
                    from_timestamp=1.0,
                    to_timestamp=1.2,
                )
            ],
            raise_or_warn="none",
        )
        windows = {video.id: (video.from_timestamp, video.to_timestamp) for video in dataset.get_data("videos")}
        assert windows == {"vid1": (0.0, -1.0), "vid2": (1.0, 1.2)}

    def test_fresh_dataset_needs_no_migration(self, tmp_path: Path):
        dataset_path = tmp_path / "video_ds"
        _make_video_dataset(dataset_path)

        dataset = Dataset(dataset_path)
        assert dataset.info.spec_version == Dataset._CURRENT_SPEC_VERSION
        assert not (dataset_path / (Dataset._INFO_FILE + ".tmp")).exists()

    def test_concurrent_opens_converge(self, tmp_path: Path):
        dataset_path = tmp_path / "video_ds"
        _make_video_dataset(dataset_path)
        _downgrade_to_spec_version_1(dataset_path)

        ctx = multiprocessing.get_context("spawn")
        workers = [ctx.Process(target=_open_dataset, args=(str(dataset_path),)) for _ in range(2)]
        for worker in workers:
            worker.start()
        for worker in workers:
            worker.join(timeout=120)

        assert all(worker.exitcode == 0 for worker in workers)
        dataset = Dataset(dataset_path)
        assert dataset.info.spec_version == Dataset._CURRENT_SPEC_VERSION
        assert "from_timestamp" in dataset.open_table("videos").schema.names

    def test_waiting_opener_refreshes_completed_upgrade(self, tmp_path: Path, monkeypatch):
        dataset_path = tmp_path / "video_ds"
        _make_video_dataset(dataset_path)
        _downgrade_to_spec_version_1(dataset_path)
        connected = Event()
        original_connect = Dataset._connect

        def signal_connect(dataset):
            connection = original_connect(dataset)
            connected.set()
            return connection

        monkeypatch.setattr(Dataset, "_connect", signal_connect)
        with ThreadPoolExecutor(max_workers=1) as pool:
            with dataset_mutation_lock(dataset_path):
                waiting = pool.submit(Dataset, dataset_path)
                assert connected.wait(timeout=5)
                assert not waiting.done()
                Dataset(dataset_path)
                completed_token = mutation_token(dataset_path)
            dataset = waiting.result(timeout=10)

        assert dataset.info.spec_version == Dataset._CURRENT_SPEC_VERSION
        assert "from_timestamp" in dataset.open_table("videos").schema.names
        assert mutation_token(dataset_path) == completed_token


def _make_bbox_dataset(path: Path) -> Dataset:
    info = DatasetInfo(name="bbox_ds", record=Record, views={"image": Image}, bbox=BBox)
    dataset = Dataset.create(path, info)
    dataset.add_records(
        {
            "records": Record(id="rec1"),
            "images": Image(id="img1", record_id="rec1", logical_name="image", uri="a.jpg", width=8, height=8),
            "bboxes": BBox(
                id="box1", record_id="rec1", view_id="img1", coords=[0, 0, 1, 1], format="xyxy", is_normalized=True
            ),
        },
        check_integrity="none",
    )
    return dataset


def _downgrade_to_spec_version_2(path: Path) -> None:
    """Rewrite a fresh dataset into the layout before review_status existed."""
    dataset = Dataset(path)
    dataset.open_table("bboxes").drop_columns(["review_status"])
    info_file = path / Dataset._INFO_FILE
    info_json = json.loads(info_file.read_text(encoding="utf-8"))
    info_json["spec_version"] = 2
    info_file.write_text(json.dumps(info_json, indent=4), encoding="utf-8")


class TestSpecVersion3Migration:
    """Step 2, lot 0: every entity annotation gains a review status, empty for what a human made."""

    def test_backfills_review_status_on_open(self, tmp_path: Path):
        dataset_path = tmp_path / "bbox_ds"
        _make_bbox_dataset(dataset_path)
        _downgrade_to_spec_version_2(dataset_path)

        dataset = Dataset(dataset_path)

        assert dataset.info.spec_version == 3
        assert "review_status" in dataset.open_table("bboxes").schema.names
        assert [box.review_status for box in dataset.get_data("bboxes")] == [""]

    def test_a_version_1_dataset_goes_through_both_steps(self, tmp_path: Path):
        dataset_path = tmp_path / "video_ds"
        _make_video_dataset(dataset_path)
        _downgrade_to_spec_version_1(dataset_path)

        dataset = Dataset(dataset_path)

        assert dataset.info.spec_version == 3
        assert "from_timestamp" in dataset.open_table("videos").schema.names

    def test_a_reviewed_box_can_be_written_after_migration(self, tmp_path: Path):
        dataset_path = tmp_path / "bbox_ds"
        _make_bbox_dataset(dataset_path)
        _downgrade_to_spec_version_2(dataset_path)

        dataset = Dataset(dataset_path)
        dataset.add_data(
            "bboxes",
            [
                BBox(
                    id="box2",
                    record_id="rec1",
                    view_id="img1",
                    coords=[0, 0, 1, 1],
                    format="xyxy",
                    is_normalized=True,
                    review_status="pending",
                )
            ],
            raise_or_warn="none",
        )

        assert {box.id: box.review_status for box in dataset.get_data("bboxes")} == {"box1": "", "box2": "pending"}

    def test_upserts_survive_an_index_rebuilt_after_migration(self, tmp_path: Path):
        """Review of step 2, lot 0: the migrated column sits at the end of the Lance schema.

        The pydantic schema declares ``review_status`` after ``view_id``; once the ``id`` index
        covers fragments written in pydantic order, ``merge_insert`` failed with "fragment id
        does not exist". Seen on a dataset imported at version 2 (imports build the index),
        opened, edited, then compacted — which the worker's writer does every 64 writes.
        """
        dataset_path = tmp_path / "bbox_ds"
        _make_bbox_dataset(dataset_path)
        _downgrade_to_spec_version_2(dataset_path)
        dataset = Dataset(dataset_path)
        dataset.create_scalar_indexes()

        def edit(box_id: str, size: float) -> None:
            box = dataset.get_data("bboxes", ids=[box_id])[0]
            box.coords = [0, 0, size, size]
            dataset.update_data("bboxes", [box], raise_or_warn="none")

        edit("box1", 0.5)
        dataset.update_data(
            "bboxes",
            [
                BBox(
                    id="box2", record_id="rec1", view_id="img1", coords=[0, 0, 1, 1], format="xyxy", is_normalized=True
                )
            ],
            raise_or_warn="none",
        )
        dataset.open_table("bboxes").optimize()
        edit("box1", 0.6)
        edit("box2", 0.7)

        sizes = {box.id: box.coords[2] for box in dataset.get_data("bboxes")}
        assert sizes == pytest.approx({"box1": 0.6, "box2": 0.7})
