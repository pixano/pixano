# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
import os
from pathlib import Path

import pytest

from pixano.datasets import Dataset
from pixano.datasets.io import ImportSpec, PlanMismatchError, SpecValidationError, analyze, import_dataset
from pixano.datasets.io.engine import ImportEngine, state_dir
from pixano.datasets.io.formats.lerobot import LeRobotImporter
from pixano.datasets.io.formats.pixano_jsonl import PixanoJsonlImporter
from pixano.datasets.io.source_fingerprint import local_source_fingerprint
from pixano.schemas import Video
from tests.datasets.io.formats.test_lerobot_importer import make_v21_dataset


class _InterruptedJsonl(PixanoJsonlImporter):
    def iter_batches(self, source, spec, plan, cursor=None):
        for ordinal, bundle in enumerate(super().iter_batches(source, spec, plan, cursor)):
            if ordinal == 1:
                raise RuntimeError("interrupted after first record")
            yield bundle


def _write_records(source: Path, ids: list[str], uri: str = "https://example.com/a.jpg") -> None:
    split = source / "train"
    split.mkdir(parents=True, exist_ok=True)
    (split / "metadata.jsonl").write_text(
        "".join(
            json.dumps({"id": record_id, "views": {"image": {"uri": uri, "width": 100, "height": 200}}}) + "\n"
            for record_id in ids
        ),
        encoding="utf-8",
    )


def _spec() -> ImportSpec:
    return ImportSpec.model_validate({"format": "pixano_jsonl", "dataset": {"name": "ds", "workspace": "image"}})


def _interrupt(source: str | Path, data_dir: Path, spec: ImportSpec, importer=None) -> dict:
    cursors = []
    with pytest.raises(RuntimeError, match="interrupted"):
        import_dataset(
            source,
            data_dir,
            spec,
            importer=importer or _InterruptedJsonl(),
            job_id="sourcejob",
            engine=ImportEngine(
                data_dir, flush_rows=1, checkpoint=lambda cursor, counts: cursors.append(dict(cursor))
            ),
        )
    assert cursors
    return cursors[-1]


def _files(path: Path) -> dict[str, bytes]:
    return {str(file.relative_to(path)): file.read_bytes() for file in path.rglob("*") if file.is_file()}


def test_insert_before_checkpoint_is_rejected_before_any_dataset_write(tmp_path: Path):
    source, data_dir = tmp_path / "source", tmp_path / "data"
    _write_records(source, ["one", "two", "three"])
    cursor = _interrupt(source, data_dir, _spec())
    assert cursor == {"split": "train", "line": 1}
    staging = state_dir(data_dir) / "staging" / "ds-sourcejob"
    before = _files(staging)
    _write_records(source, ["inserted", "one", "two", "three"])

    # Re-analysis produces a fresh plan, so the original durable job identity
    # (not just the caller's plan) must detect the inserted record.
    with pytest.raises(PlanMismatchError, match="changed.*restart"):
        import_dataset(source, data_dir, _spec(), job_id="sourcejob", resume_cursor=cursor)

    assert _files(staging) == before
    assert not (data_dir / "library" / "ds").exists()


def test_unchanged_source_resumes_without_gaps_or_duplicates(tmp_path: Path):
    source, data_dir = tmp_path / "source", tmp_path / "data"
    _write_records(source, ["one", "two", "three"])
    cursor = _interrupt(source, data_dir, _spec())
    result = import_dataset(source, data_dir, _spec(), job_id="sourcejob", resume_cursor=cursor)

    dataset = Dataset(result.dataset_path)
    assert sorted(row.id for row in dataset.get_data("records")) == ["one", "three", "two"]
    assert dataset.open_table("images").count_rows() == 3


@pytest.mark.parametrize("legacy_guard", ["missing", "unverifiable", "damaged"])
def test_legacy_or_unverifiable_checkpoint_refuses_resume(tmp_path: Path, legacy_guard: str):
    source, data_dir = tmp_path / "source", tmp_path / "data"
    _write_records(source, ["one", "two"])
    cursor = _interrupt(source, data_dir, _spec())
    guard = state_dir(data_dir) / "sources" / "sourcejob.json"
    if legacy_guard == "missing":
        guard.unlink()
    elif legacy_guard == "damaged":
        guard.write_text("{", encoding="utf-8")
    else:
        payload = json.loads(guard.read_text())
        payload["source_fingerprint"] = ""
        guard.write_text(json.dumps(payload), encoding="utf-8")
    staging = state_dir(data_dir) / "staging" / "ds-sourcejob"
    before = _files(staging)

    with pytest.raises(PlanMismatchError, match="restart"):
        import_dataset(source, data_dir, _spec(), job_id="sourcejob", resume_cursor=cursor)
    assert _files(staging) == before


def test_saved_plan_rejects_source_change_before_creating_target(tmp_path: Path):
    source = tmp_path / "source"
    _write_records(source, ["one"])
    plan = analyze(source, _spec())
    assert plan.source_fingerprint
    _write_records(source, ["one", "two"])

    with pytest.raises(PlanMismatchError, match="source changed after analysis"):
        import_dataset(source, tmp_path / "data", _spec(), plan=plan)
    assert not (tmp_path / "data").exists()


@pytest.mark.parametrize("external", [False, True])
def test_media_edits_invalidate_the_plan_even_when_size_and_mtime_are_preserved(tmp_path: Path, external: bool):
    from PIL import Image

    source = tmp_path / "source"
    source.mkdir()
    media = (tmp_path if external else source) / "media.png"
    Image.new("RGB", (10, 10), "red").save(media)
    _write_records(source, ["one"], str(media))
    plan = analyze(source, _spec())
    assert plan.source_fingerprint
    original_stat = media.stat()
    content = media.read_bytes()
    media.write_bytes(content[:-1] + bytes([content[-1] ^ 1]))
    os.utime(media, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))

    with pytest.raises(PlanMismatchError, match="source changed after analysis"):
        import_dataset(source, tmp_path / "data", _spec(), plan=plan)
    assert not (tmp_path / "data").exists()


def test_reading_files_does_not_change_local_fingerprint(tmp_path: Path):
    path = tmp_path / "metadata.jsonl"
    path.write_text("record", encoding="utf-8")
    before = local_source_fingerprint(tmp_path)
    path.read_bytes()
    assert before and local_source_fingerprint(tmp_path) == before


def test_output_inside_source_is_refused_before_self_invalidating_the_inventory(tmp_path: Path):
    source = tmp_path / "source"
    _write_records(source, ["one"])
    output = source / "pixano-data"
    with pytest.raises(SpecValidationError, match="outside the import source"):
        import_dataset(source, output, _spec())
    assert not output.exists()


@pytest.mark.parametrize("changed_revision", [False, True])
def test_hub_resume_uses_verified_snapshot_revision(tmp_path: Path, monkeypatch, changed_revision: bool):
    import pixano.datasets.io.formats.lerobot.importer as importer_module

    commit_a, commit_b = "a" * 40, "b" * 40
    roots = {commit: make_v21_dataset(tmp_path / "snapshots" / commit) for commit in (commit_a, commit_b)}
    current = [commit_a]
    downloaded = []
    monkeypatch.setattr(importer_module, "materialize_meta", lambda repo, revision=None: roots[revision or current[0]])
    monkeypatch.setattr(importer_module, "ffprobe_available", lambda: False)

    def materialize_files(repo, paths, revision=None):
        downloaded.append(revision)
        return roots[revision]

    monkeypatch.setattr(importer_module, "materialize_files", materialize_files)
    monkeypatch.setattr(
        LeRobotImporter,
        "_video_row",
        lambda self, info, layout, resolver, record_id, view_name, camera, shard, root: Video(
            id=f"{record_id}-video",
            record_id=record_id,
            logical_name=view_name,
            uri="https://example.com/video.mp4",
            num_frames=1,
            fps=1.0,
            width=10,
            height=10,
            format="mp4",
            duration=1.0,
        ),
    )

    class InterruptedLeRobot(LeRobotImporter):
        def iter_batches(self, source, spec, plan, cursor=None):
            for ordinal, bundle in enumerate(super().iter_batches(source, spec, plan, cursor)):
                if ordinal == 1:
                    raise RuntimeError("interrupted after first episode")
                yield bundle

    spec = ImportSpec.model_validate(
        {"format": "lerobot", "dataset": {"name": "ds"}, "options": {"frames": "reference"}}
    )
    data_dir = tmp_path / "data"
    cursor = _interrupt("hub://acme/robot", data_dir, spec, InterruptedLeRobot())
    assert downloaded == [commit_a]
    if changed_revision:
        current[0] = commit_b
        before = _files(state_dir(data_dir) / "staging" / "ds-sourcejob")
        with pytest.raises(PlanMismatchError, match="changed.*restart"):
            import_dataset("hub://acme/robot", data_dir, spec, job_id="sourcejob", resume_cursor=cursor)
        assert _files(state_dir(data_dir) / "staging" / "ds-sourcejob") == before
        assert downloaded == [commit_a]  # rejected before downloading media or opening the staging dataset
    else:
        result = import_dataset("hub://acme/robot", data_dir, spec, job_id="sourcejob", resume_cursor=cursor)
        assert Dataset(result.dataset_path).open_table("records").count_rows() == 2
        assert downloaded == [commit_a, commit_a]
