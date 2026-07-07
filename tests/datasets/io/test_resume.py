# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from pixano.datasets import Dataset
from pixano.datasets.io import ImportSpec, import_dataset
from pixano.datasets.io.engine import ImportEngine, state_dir
from pixano.datasets.io.errors import ResumeError
from pixano.datasets.io.jobs import JobRunner, JobStore
from tests.datasets.io._toy_importer import ToyImporter


REPO_ROOT = Path(__file__).parents[2]


def _spec(name: str, mode: str = "create") -> ImportSpec:
    return ImportSpec.model_validate({"dataset": {"name": name, "workspace": "image"}, "format": "auto", "mode": mode})


def _sorted_ids(dataset: Dataset) -> dict[str, list[str]]:
    return {
        name: sorted(r["id"] for r in dataset.open_table(name).search().select(["id"]).limit(None).to_list())
        for name in dataset.info.tables
    }


class TestEngineResume:
    def test_resume_completes_a_failed_build_exactly(self, tmp_path: Path):
        # Control: uninterrupted import of the same source.
        control = ToyImporter(num_records=60, batch_size=5)
        result = import_dataset(tmp_path / "src", tmp_path / "control", _spec("ds"), importer=control)
        control_ids = _sorted_ids(Dataset(result.dataset_path))

        # Failing run: importer dies mid-stream after some flushes committed.
        class DiesAt(ToyImporter):
            def iter_batches(self, source, spec, plan, cursor=None):
                for bundle in super().iter_batches(source, spec, plan, cursor=cursor):
                    if bundle.cursor and int(bundle.cursor.get("ordinal", 0)) == 40 and cursor is None:
                        raise RuntimeError("simulated crash")
                    yield bundle

        cursors: list[dict] = []
        engine = ImportEngine(tmp_path / "data", flush_rows=16, checkpoint=lambda c, n: cursors.append(dict(c)))
        with pytest.raises(RuntimeError, match="simulated crash"):
            import_dataset(
                tmp_path / "src",
                tmp_path / "data",
                _spec("ds"),
                importer=DiesAt(num_records=60, batch_size=5),
                engine=engine,
                job_id="job1",
            )
        # Staging preserved with committed flushes.
        staging = state_dir(tmp_path / "data") / "staging" / "ds-job1"
        assert staging.exists() and cursors, "staging must survive a crash after committed flushes"

        # Resume from the last committed cursor; boundary bundles replay as upserts.
        engine2 = ImportEngine(tmp_path / "data", flush_rows=16)
        resumed = import_dataset(
            tmp_path / "src",
            tmp_path / "data",
            _spec("ds"),
            importer=ToyImporter(num_records=60, batch_size=5),
            engine=engine2,
            job_id="job1",
            resume_cursor=cursors[-1],
        )
        assert not staging.exists()  # promoted
        resumed_ids = _sorted_ids(Dataset(resumed.dataset_path))
        assert resumed_ids == control_ids  # zero duplicates, zero gaps

    def test_resume_without_staging_is_a_typed_error(self, tmp_path: Path):
        with pytest.raises(ResumeError, match="staging"):
            import_dataset(
                tmp_path / "src",
                tmp_path / "data",
                _spec("ds2"),
                importer=ToyImporter(num_records=4),
                job_id="ghost",
                resume_cursor={"ordinal": 2},
            )

    def test_non_resumable_importer_is_refused(self, tmp_path: Path):
        class NoResume(ToyImporter):
            supports_resume = False

        with pytest.raises(ResumeError, match="does not support resume"):
            import_dataset(
                tmp_path / "src",
                tmp_path / "data",
                _spec("ds3"),
                importer=NoResume(num_records=4),
                job_id="j",
                resume_cursor={"ordinal": 1},
            )

    def test_add_mode_resume_preserves_manifest_anchor(self, tmp_path: Path):
        base = ToyImporter(num_records=10, batch_size=5)
        first = import_dataset(tmp_path / "src", tmp_path / "data", _spec("ds4"), importer=base)
        dataset = Dataset(first.dataset_path)
        pre_versions = {n: dataset.open_table(n).version for n in dataset.info.tables}

        # Interrupted add: manifest written, some rows in.
        class DiesAt(ToyImporter):
            def iter_batches(self, source, spec, plan, cursor=None):
                for bundle in super().iter_batches(source, spec, plan, cursor=cursor):
                    if bundle.cursor and int(bundle.cursor.get("ordinal", 0)) == 30 and cursor is None:
                        raise RuntimeError("boom")
                    yield bundle

        cursors: list[dict] = []
        engine = ImportEngine(tmp_path / "data", flush_rows=8, checkpoint=lambda c, n: cursors.append(dict(c)))
        with pytest.raises(RuntimeError):
            import_dataset(
                tmp_path / "src",
                tmp_path / "data",
                _spec("ds4", mode="add"),
                importer=DiesAt(num_records=40, batch_size=5),
                engine=engine,
                job_id="addjob",
            )
        assert cursors

        resumed = import_dataset(
            tmp_path / "src",
            tmp_path / "data",
            _spec("ds4", mode="add"),
            importer=ToyImporter(num_records=40, batch_size=5),
            engine=ImportEngine(tmp_path / "data", flush_rows=8),
            job_id="addjob",
            resume_cursor=cursors[-1],
        )
        from pixano.datasets.io.manifest import ImportManifest

        manifest = ImportManifest.load(Path(resumed.manifest_path))
        assert manifest.pre_import_versions == pre_versions  # rollback anchor survives the resume
        assert Dataset(resumed.dataset_path).open_table("records").count_rows() == 40


class TestKill9Resume:
    def test_sigkill_mid_import_then_resume_matches_control(self, tmp_path: Path):
        # Control run in-process.
        control = import_dataset(
            tmp_path / "src", tmp_path / "control", _spec("k9"), importer=ToyImporter(num_records=80, batch_size=4)
        )
        control_ids = _sorted_ids(Dataset(control.dataset_path))

        # Victim run in a subprocess through the JOB RUNNER (cursor persisted in the store).
        data_dir = tmp_path / "data"
        (data_dir / "library").mkdir(parents=True)
        script = f"""
import sys
sys.path.insert(0, {str(REPO_ROOT)!r})
from pathlib import Path
from pixano.datasets.io import ImportSpec, import_dataset
from pixano.datasets.io.engine import ImportEngine
from pixano.datasets.io.jobs import JobStore
from tests.datasets.io._toy_importer import ToyImporter
import time

data_dir = Path({str(data_dir)!r})
store = JobStore.for_data_dir(data_dir)
job = store.create_job("import", dataset="k9")
store.update_job(job.id, status="running")
print(job.id, flush=True)

class Slow(ToyImporter):
    def iter_batches(self, source, spec, plan, cursor=None):
        for bundle in super().iter_batches(source, spec, plan, cursor=cursor):
            time.sleep(0.02)
            yield bundle

engine = ImportEngine(data_dir, flush_rows=8,
                      checkpoint=lambda c, n: store.update_job(job.id, cursor=dict(c)))
import_dataset({str(tmp_path / "src")!r}, data_dir,
               ImportSpec.model_validate({{"dataset": {{"name": "k9", "workspace": "image"}}, "mode": "create"}}),
               importer=Slow(num_records=80, batch_size=4), engine=engine, job_id=job.id)
"""
        proc = subprocess.Popen(
            [sys.executable, "-c", script],
            stdout=subprocess.PIPE,
            text=True,
            env={**os.environ, "PYTHONPATH": str(REPO_ROOT)},
        )
        assert proc.stdout is not None
        job_id = proc.stdout.readline().strip()
        deadline = time.monotonic() + 30
        store = JobStore.for_data_dir(data_dir)
        while time.monotonic() < deadline:
            job = store.get_job(job_id)
            if job and job.cursor and int(job.cursor.get("ordinal", 0)) >= 24:
                break
            time.sleep(0.05)
        os.kill(proc.pid, signal.SIGKILL)
        proc.wait(timeout=10)

        job = store.get_job(job_id)
        assert job is not None and job.cursor, "a checkpoint must have been persisted before the kill"
        flipped = store.mark_interrupted_on_boot(pid_check=lambda pid: False)
        assert job_id in flipped

        # Resume in-process from the persisted cursor.
        resumed = import_dataset(
            tmp_path / "src",
            data_dir,
            _spec("k9"),
            importer=ToyImporter(num_records=80, batch_size=4),
            engine=ImportEngine(data_dir, flush_rows=8),
            job_id=job_id,
            resume_cursor=dict(job.cursor),
        )
        assert _sorted_ids(Dataset(resumed.dataset_path)) == control_ids
