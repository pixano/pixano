# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import multiprocessing
from pathlib import Path

from pixano.datasets import Dataset, DatasetInfo
from pixano.schemas import Record, Video


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

        assert dataset.info.spec_version == 2
        schema_names = dataset.open_table("videos").schema.names
        assert "from_timestamp" in schema_names
        assert "to_timestamp" in schema_names

        info_json = json.loads((dataset_path / Dataset._INFO_FILE).read_text(encoding="utf-8"))
        assert info_json["spec_version"] == 2

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
        assert dataset.info.spec_version == 2
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
        assert dataset.info.spec_version == 2
        assert "from_timestamp" in dataset.open_table("videos").schema.names
