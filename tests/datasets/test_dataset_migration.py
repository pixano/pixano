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
from pixano.schemas import BBox, Entity, Image, Record, Video


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
    """Every entity annotation gains a review status, empty for what a human made."""

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
        """The migrated column sits at the end of the Lance schema.

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


def _open_with_a_failed_migration(path: Path, monkeypatch: pytest.MonkeyPatch) -> Dataset:
    """Open a version 2 dataset whose migration fails, as the opener then leaves it.

    The migration fails in the field when its lock wait runs out or ``add_columns`` raises; the
    opener logs it and keeps the dataset readable at the old layout.
    """

    def interrupted(dataset: Dataset) -> None:
        raise RuntimeError("migration interrupted")

    with monkeypatch.context() as patch:
        patch.setattr(Dataset, "_migrate_storage", interrupted)
        dataset = Dataset(path)
    assert dataset.info.spec_version == 2
    assert "review_status" not in dataset.open_table("bboxes").schema.names
    return dataset


def _accepted_box() -> BBox:
    """The box the dataset holds, with a review status and new coordinates that show whether it was written."""
    return BBox(
        id="box1",
        record_id="rec1",
        view_id="img1",
        coords=[0, 0, 0.5, 0.5],
        format="xyxy",
        is_normalized=True,
        source_type="model",
        review_status="accepted",
    )


class TestWritesNamingAColumnTheTableLacks:
    """A write is refused, not trimmed, when the table lacks a column.

    The opener keeps a dataset whose migration failed readable on the promise that writes
    surface the missing column. Rebuilding the rows against the table's schema would drop it
    instead: a review status sent would be answered as stored, and lost.
    """

    def test_update_data_refuses_a_status_the_table_cannot_store(self, tmp_path: Path, monkeypatch):
        dataset_path = tmp_path / "bbox_ds"
        _make_bbox_dataset(dataset_path)
        _downgrade_to_spec_version_2(dataset_path)
        dataset = _open_with_a_failed_migration(dataset_path, monkeypatch)

        with pytest.raises(ValueError, match="Field 'review_status' not found in target schema"):
            dataset.update_data("bboxes", [_accepted_box()])

        assert dataset.get_data("bboxes", ids=["box1"])[0].coords == [0, 0, 1, 1]

    def test_an_upsert_refuses_a_status_the_table_cannot_store(self, tmp_path: Path, monkeypatch):
        """The import engine's upsert path, `merge_records`, shares the reordering."""
        dataset_path = tmp_path / "bbox_ds"
        _make_bbox_dataset(dataset_path)
        _downgrade_to_spec_version_2(dataset_path)
        dataset = _open_with_a_failed_migration(dataset_path, monkeypatch)

        with pytest.raises(ValueError, match="Field 'review_status' not found in target schema"):
            dataset.merge_records({"bboxes": [_accepted_box()]})

        assert dataset.get_data("bboxes", ids=["box1"])[0].coords == [0, 0, 1, 1]

    def test_an_upsert_leaves_a_column_its_rows_lack_as_stored(self, tmp_path: Path):
        """A handle that read the entities before another process gave their table a column does not erase it."""
        dataset_path = tmp_path / "entity_ds"
        stale = Dataset.create(dataset_path, DatasetInfo(name="entity_ds", record=Record, entity=Entity))
        stale.add_records(
            {
                "records": Record(id="rec1"),
                "entities": [Entity(id="ent0", record_id="rec1"), Entity(id="ent1", record_id="rec1")],
            }
        )
        Dataset(dataset_path).open_table("entities").add_columns({"category": "'car'"})

        stale.merge_records({"entities": [Entity(id="ent1", record_id="rec1", parent_id="ent0")]})

        stored = Dataset(dataset_path).open_table("entities").to_arrow().to_pylist()
        assert {(row["id"], row["parent_id"], row["category"]) for row in stored} == {
            ("ent0", "", "car"),
            ("ent1", "ent0", "car"),
        }
