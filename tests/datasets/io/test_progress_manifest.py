# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

from pixano.datasets.io import ImportManifest, ProgressEvent, ProgressSink, ThrottledSink


class _CollectingSink(ProgressSink):
    def __init__(self) -> None:
        self.events: list[ProgressEvent] = []

    def emit(self, event: ProgressEvent) -> None:
        self.events.append(event)


class TestThrottledSink:
    def test_throttles_but_always_forwards_terminal(self):
        inner = _CollectingSink()
        sink = ThrottledSink(inner, min_interval=3600.0)  # effectively "once"

        for done in range(10):
            sink.emit(ProgressEvent(phase="ingest", done=done, total=10))
        sink.emit(ProgressEvent(phase="ingest", done=10, total=10, final=True))

        assert len(inner.events) == 2  # the first event + the terminal one
        assert inner.events[0].done == 0
        assert inner.events[-1].final is True

    def test_zero_interval_forwards_everything(self):
        inner = _CollectingSink()
        sink = ThrottledSink(inner, min_interval=0.0)
        for done in range(3):
            sink.emit(ProgressEvent(phase="analyze", done=done))
        assert len(inner.events) == 3


class TestImportManifest:
    def test_atomic_save_and_load(self, tmp_path: Path):
        manifest = ImportManifest(
            job_id="job1",
            dataset_id="ds1",
            id_namespace="voc2007",
            ns8_prefix="AbCdEf12",
            importer_version="1.0.0",
            pre_import_versions={"records": 4, "bboxes": 7},
        )
        path = tmp_path / "imports" / "job1.manifest.json"
        manifest.save(path)

        loaded = ImportManifest.load(path)
        assert loaded == manifest
        assert not path.with_name(path.name + ".tmp").exists()

        manifest.post_import_versions = {"records": 5, "bboxes": 9}
        manifest.save(path)
        assert ImportManifest.load(path).post_import_versions == {"records": 5, "bboxes": 9}
