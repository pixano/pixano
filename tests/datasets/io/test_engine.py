# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import json
from pathlib import Path

import pytest

from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.io import ImportEngine, ImportSpec, JobStateError, SpecValidationError, import_dataset
from pixano.datasets.io.engine import replay_journals, state_dir
from pixano.datasets.utils.errors import DatasetIntegrityError
from pixano.datasets.workspaces import WorkspaceType
from tests.datasets.io._toy_importer import ToyImporter


def _spec(name: str = "toy_ds", mode: str = "create", namespace: str = "toy") -> ImportSpec:
    return ImportSpec.model_validate(
        {
            "dataset": {"name": name, "workspace": "image"},
            "format": "toy",
            "mode": mode,
            "ids": {"namespace": namespace},
        }
    )


def _import(data_dir: Path, importer: ToyImporter, spec: ImportSpec, **engine_kwargs):
    engine = ImportEngine(data_dir, **engine_kwargs) if engine_kwargs else None
    return import_dataset("unused-source", data_dir, spec, importer=importer, engine=engine)


class TestFreshBuild:
    def test_create_end_to_end(self, tmp_path: Path):
        result = _import(tmp_path, ToyImporter(num_records=10, batch_size=4), _spec())

        assert result.table_counts == {"records": 10, "images": 10, "entities": 10}
        assert result.storage_mode == "embedded"
        assert result.manifest_path is None

        dataset = Dataset(result.dataset_path)
        assert dataset.open_table("records").count_rows() == 10
        assert dataset.info.storage_mode == "embedded"
        record_indices = {c for index in dataset.open_table("records").list_indices() for c in index.columns}
        assert "id" in record_indices

        provenance = json.loads((result.dataset_path / "imports" / f"{result.job_id}.json").read_text())
        assert provenance["format"] == "toy"
        assert provenance["table_counts"]["records"] == 10

        # No staging/ledger leftovers.
        assert not any((state_dir(tmp_path) / "staging").glob("*")), "staging must be empty after promotion"

    def test_create_refuses_existing(self, tmp_path: Path):
        _import(tmp_path, ToyImporter(num_records=2), _spec())
        with pytest.raises(SpecValidationError, match="already exists"):
            _import(tmp_path, ToyImporter(num_records=2), _spec())

    def test_multi_flush_and_checkpoints(self, tmp_path: Path):
        checkpoints: list[dict] = []
        result = _import(
            tmp_path,
            ToyImporter(num_records=20, batch_size=4),
            _spec(),
            flush_rows=9,
            checkpoint=lambda cursor, counts: checkpoints.append(dict(cursor)),
        )
        assert result.table_counts["records"] == 20
        assert len(checkpoints) >= 2  # several committed flush boundaries

    def test_cross_flush_duplicate_id_detected(self, tmp_path: Path):
        importer = ToyImporter(num_records=12, batch_size=3, duplicate_record_ordinal=0)
        with pytest.raises(DatasetIntegrityError, match="Duplicate id"):
            _import(tmp_path, importer, _spec(), flush_rows=6)
        assert not (tmp_path / "library" / "toy_ds").exists(), "failed build must not reach the library"

    def test_uri_media_census(self, tmp_path: Path):
        result = _import(tmp_path, ToyImporter(num_records=4, media="uri"), _spec())
        assert result.storage_mode == "filesystem"

    def test_cancel_cleans_staging(self, tmp_path: Path):
        with pytest.raises(JobStateError, match="cancelled"):
            _import(
                tmp_path,
                ToyImporter(num_records=32, batch_size=4),
                _spec(),
                flush_rows=4,
                cancel_check=lambda: True,
            )
        assert not (tmp_path / "library" / "toy_ds").exists()
        assert not any((state_dir(tmp_path) / "staging").glob("*"))


class TestOverwrite:
    def test_overwrite_replaces_dataset(self, tmp_path: Path):
        _import(tmp_path, ToyImporter(num_records=5), _spec())
        result = _import(tmp_path, ToyImporter(num_records=3), _spec(mode="overwrite"))

        dataset = Dataset(result.dataset_path)
        assert dataset.open_table("records").count_rows() == 3
        assert not any((state_dir(tmp_path) / "trash").glob("*")), "trash must be emptied after the swap"
        assert not any((state_dir(tmp_path) / "journal").glob("*.json")), "journal must be cleared"

    def test_replay_completes_interrupted_swap(self, tmp_path: Path):
        # Build a dataset, then simulate a crash between old->trash and staging->target.
        result = _import(tmp_path, ToyImporter(num_records=4), _spec())
        target = result.dataset_path

        staging = state_dir(tmp_path) / "staging" / "toy_ds-crashjob"
        trash = state_dir(tmp_path) / "trash" / "toy_ds-crashjob"
        journal_dir = state_dir(tmp_path) / "journal"
        journal_dir.mkdir(parents=True, exist_ok=True)
        target.rename(trash.parent.mkdir(parents=True, exist_ok=True) or trash)  # old -> trash
        # The "new" dataset sits fully built in staging.
        _import(tmp_path, ToyImporter(num_records=2), _spec())  # rebuild directly into library
        (tmp_path / "library" / "toy_ds").rename(staging.parent.mkdir(parents=True, exist_ok=True) or staging)
        (journal_dir / "crashjob.json").write_text(
            json.dumps({"target": str(target), "staging": str(staging), "trash": str(trash)})
        )

        replay_journals(tmp_path)

        assert target.exists(), "swap must be completed from the journal"
        assert Dataset(target).open_table("records").count_rows() == 2
        assert not trash.exists()
        assert not (journal_dir / "crashjob.json").exists()


class TestAddMode:
    def test_add_is_idempotent_and_journaled(self, tmp_path: Path):
        _import(tmp_path, ToyImporter(num_records=6), _spec())

        first = _import(tmp_path, ToyImporter(num_records=6), _spec(mode="add"))
        second = _import(tmp_path, ToyImporter(num_records=6), _spec(mode="add"))

        dataset = Dataset(first.dataset_path)
        assert dataset.open_table("records").count_rows() == 6  # re-running converges, never duplicates
        assert first.manifest_path is not None and first.manifest_path.exists()

        manifest = json.loads(second.manifest_path.read_text())
        assert manifest["pre_import_versions"]["records"] >= 1
        assert manifest["post_import_versions"] is not None

    def test_add_requires_existing_dataset(self, tmp_path: Path):
        with pytest.raises(SpecValidationError, match="does not exist"):
            _import(tmp_path, ToyImporter(num_records=2), _spec(mode="add"))


class TestLibraryGlobHardening:
    def test_dot_dirs_are_not_datasets(self, tmp_path: Path):
        result = _import(tmp_path, ToyImporter(num_records=2), _spec())

        # Plant a trashed copy inside a dot-dir of the library and engine trash.
        junk = tmp_path / "library" / ".staging-junk"
        junk.mkdir()
        (junk / "info.json").write_text((result.dataset_path / "info.json").read_text())

        infos = DatasetInfo.load_directory(tmp_path / "library")
        assert len(infos) == 1

    def test_workspace_flows_through(self, tmp_path: Path):
        result = _import(tmp_path, ToyImporter(num_records=2), _spec())
        assert Dataset(result.dataset_path).info.workspace == WorkspaceType.IMAGE


class TestConcurrencyOptimizations:
    def test_import_creates_filter_indexes(self, tmp_path):
        from pixano.datasets import Dataset
        from pixano.datasets.io import ImportSpec, import_dataset
        from tests.datasets.io._toy_importer import ToyImporter

        spec = ImportSpec.model_validate({"dataset": {"name": "idx", "workspace": "image"}})
        result = import_dataset(tmp_path / "src", tmp_path / "data", spec, importer=ToyImporter(num_records=3))
        dataset = Dataset(result.dataset_path)
        table = dataset.open_table("images")
        indexed = {c for i in table.list_indices() for c in (getattr(i, "columns", None) or [])}
        assert {"id", "record_id"} <= indexed
        # standard filter columns present in the schema are indexed too
        assert "record_id" in indexed

    def test_sequence_frames_only_first_frame_gets_a_preview(self, tmp_path):
        import io as io_module

        import PIL.Image

        from pixano.datasets import Dataset, DatasetInfo
        from pixano.datasets.io.engine import _stamp_image_previews
        from pixano.schemas import Record, SequenceFrame

        library = tmp_path / "lib"
        info = DatasetInfo(name="seq", record=Record, views={"cam": SequenceFrame})
        dataset = Dataset.create(library / "seq", info)

        buffer = io_module.BytesIO()
        PIL.Image.new("RGB", (32, 32), (1, 2, 3)).save(buffer, "JPEG")
        blob = buffer.getvalue()
        rows = [
            SequenceFrame(
                id=f"f{i}",
                record_id="r",
                logical_name="cam",
                uri="",
                raw_bytes=blob,
                width=32,
                height=32,
                format="JPEG",
                frame_index=i,
                timestamp=i / 10,
            )
            for i in range(5)
        ]
        _stamp_image_previews(dataset, "sequence_frames", rows)
        assert rows[0].preview  # the grid's poster frame
        assert all(not row.preview for row in rows[1:])  # no per-frame GIL burn
