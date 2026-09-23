# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from pathlib import Path

import pyarrow as pa
import pytest

from pixano.datasets import Dataset
from pixano.datasets.io import BatchBundle, ImportSpec, import_dataset
from pixano.datasets.io.engine import ImportEngine, state_dir
from pixano.datasets.io.errors import JobStateError
from tests.datasets.io._toy_importer import ToyImporter


class ArrowImporter(ToyImporter):
    """Toy records in Arrow, optionally retaining child tables as row payloads."""

    def __init__(self, mixed: bool = False):
        super().__init__(num_records=3, batch_size=1)
        self.mixed = mixed

    def iter_batches(self, source, spec, plan, cursor=None):
        for bundle in super().iter_batches(source, spec, plan, cursor):
            for name, rows in list(bundle.tables.items()):
                if not self.mixed or name == "records":
                    bundle.tables[name] = pa.Table.from_pylist(
                        [row.model_dump() for row in rows], schema=type(rows[0]).to_arrow_schema()
                    )
            yield bundle


def _spec() -> ImportSpec:
    return ImportSpec.model_validate({"dataset": {"name": "ds", "workspace": "image"}})


def _ids(dataset_path: Path) -> dict[str, list[str]]:
    dataset = Dataset(dataset_path)
    return {
        name: sorted(row["id"] for row in dataset.open_table(name).search().select(["id"]).limit(None).to_list())
        for name in dataset.info.tables
    }


@pytest.mark.parametrize("mixed", [False, True])
def test_arrow_checkpoints_cover_every_table_in_each_bundle(tmp_path: Path, mixed: bool):
    checkpoints = []
    staging = state_dir(tmp_path) / "staging" / "ds-arrowjob"

    def checkpoint(cursor, counts):
        dataset = Dataset(staging)
        ordinal = cursor["ordinal"]
        assert all(dataset.open_table(name).count_rows() == ordinal for name in ("records", "images", "entities"))
        checkpoints.append(dict(cursor))

    import_dataset(
        "unused-source",
        tmp_path,
        _spec(),
        importer=ArrowImporter(mixed),
        engine=ImportEngine(tmp_path, checkpoint=checkpoint),
        job_id="arrowjob",
    )
    assert checkpoints == [{"ordinal": 1}, {"ordinal": 2}, {"ordinal": 3}]


def test_failure_inside_mixed_bundle_replays_from_last_complete_bundle(tmp_path: Path):
    class FailsOnSecondRows(ImportEngine):
        flushes = 0

        def _flush_rows(self, *args, **kwargs):
            self.flushes += 1
            if self.flushes == 2:
                raise RuntimeError("second bundle failed after its Arrow records")
            return super()._flush_rows(*args, **kwargs)

    checkpoints = []
    data_dir = tmp_path / "failed"
    with pytest.raises(RuntimeError, match="second bundle"):
        import_dataset(
            "unused-source",
            data_dir,
            _spec(),
            importer=ArrowImporter(mixed=True),
            job_id="mixedjob",
            engine=FailsOnSecondRows(data_dir, checkpoint=lambda cursor, counts: checkpoints.append(dict(cursor))),
        )
    assert checkpoints == [{"ordinal": 1}]
    staged = Dataset(state_dir(data_dir) / "staging" / "ds-mixedjob")
    assert staged.open_table("records").count_rows() == 2
    assert staged.open_table("images").count_rows() == 1

    resumed = import_dataset(
        "unused-source",
        data_dir,
        _spec(),
        importer=ArrowImporter(mixed=True),
        job_id="mixedjob",
        resume_cursor=checkpoints[-1],
    )
    control = import_dataset("unused-source", tmp_path / "control", _spec(), importer=ArrowImporter(mixed=True))
    assert _ids(resumed.dataset_path) == _ids(control.dataset_path)


def test_small_row_import_checkpoints_its_final_bundle(tmp_path: Path):
    checkpoints = []
    import_dataset(
        "unused-source",
        tmp_path,
        _spec(),
        importer=ToyImporter(num_records=3, batch_size=1),
        engine=ImportEngine(tmp_path, checkpoint=lambda cursor, counts: checkpoints.append(dict(cursor))),
    )
    assert checkpoints == [{"ordinal": 3}]


def test_resume_at_eof_does_not_clear_the_committed_cursor(tmp_path: Path):
    class FailsAtFinalize(ImportEngine):
        def _finalize(self, *args, **kwargs):
            raise RuntimeError("finalization failed")

    checkpoints = []
    with pytest.raises(RuntimeError, match="finalization"):
        import_dataset(
            "unused-source",
            tmp_path,
            _spec(),
            importer=ToyImporter(num_records=3),
            job_id="tailjob",
            engine=FailsAtFinalize(tmp_path, checkpoint=lambda cursor, counts: checkpoints.append(dict(cursor))),
        )
    assert checkpoints == [{"ordinal": 3}]
    resumed = import_dataset(
        "unused-source",
        tmp_path,
        _spec(),
        importer=ToyImporter(num_records=3),
        job_id="tailjob",
        resume_cursor=checkpoints[-1],
        engine=ImportEngine(tmp_path, checkpoint=lambda cursor, counts: checkpoints.append(dict(cursor))),
    )
    assert checkpoints == [{"ordinal": 3}]
    assert Dataset(resumed.dataset_path).open_table("records").count_rows() == 3


def test_arrow_cancellation_stops_after_a_committed_bundle(tmp_path: Path):
    checkpoints = []
    with pytest.raises(JobStateError, match="cancelled"):
        import_dataset(
            "unused-source",
            tmp_path,
            _spec(),
            importer=ArrowImporter(),
            job_id="canceljob",
            engine=ImportEngine(
                tmp_path,
                checkpoint=lambda cursor, counts: checkpoints.append(dict(cursor)),
                cancel_check=lambda: bool(checkpoints),
            ),
        )
    assert checkpoints == [{"ordinal": 1}]
    assert not (tmp_path / "library" / "ds").exists()
    assert not (state_dir(tmp_path) / "staging" / "ds-canceljob").exists()


def test_resumed_arrow_children_resolve_previously_committed_parents(tmp_path: Path):
    class SplitTablesImporter(ArrowImporter):
        def iter_batches(self, source, spec, plan, cursor=None):
            start = cursor.get("table_ordinal", 0) if cursor else 0
            first = next(super().iter_batches(source, spec, plan))
            for ordinal, (name, payload) in enumerate(first.tables.items(), start=1):
                if ordinal > start:
                    yield BatchBundle(tables={name: payload}, cursor={"table_ordinal": ordinal})

    checkpoints = []

    def fail_after_record(cursor, counts):
        checkpoints.append(dict(cursor))
        raise RuntimeError("record checkpoint saved before interruption")

    with pytest.raises(RuntimeError, match="checkpoint saved"):
        import_dataset(
            "unused-source",
            tmp_path,
            _spec(),
            importer=SplitTablesImporter(),
            job_id="splitjob",
            engine=ImportEngine(tmp_path, checkpoint=fail_after_record),
        )
    resumed = import_dataset(
        "unused-source",
        tmp_path,
        _spec(),
        importer=SplitTablesImporter(),
        job_id="splitjob",
        resume_cursor=checkpoints[-1],
    )
    dataset = Dataset(resumed.dataset_path)
    assert all(dataset.open_table(name).count_rows() == 1 for name in ("records", "images", "entities"))
