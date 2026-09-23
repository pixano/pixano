# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests of the idempotent writing of job results."""

import hashlib
import json
import re
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from pixano_worker.reader import JobReader
from pixano_worker.writer import JobWriter, ModelIdentity, derive_id


class _Vector:
    """An embedding row, for the stand-in."""

    def __init__(self, id: str, record_id: str, vector: Any) -> None:
        self.id, self.record_id, self.vector = id, record_id, vector


class _FakeRow:
    """Any row, with the identifier the writer sets on it."""

    def __init__(self, payload: str) -> None:
        self.id = ""
        self.payload = payload


def _matching(rows: dict[str, Any], ids: list[str] | None, where: str | None) -> list[Any]:
    """The two reads the writer makes: by identifiers, or by the prefix filter of a cleanup."""
    if ids is not None:
        return [rows[i] for i in ids if i in rows]
    prefix = re.fullmatch(r"id LIKE '([^']*)%'", where or "")
    assert prefix is not None, f"unexpected filter in a test double: {where!r}"
    return [row for row_id, row in rows.items() if row_id.startswith(prefix.group(1))]


class _FakeDataset:
    """An in-memory dataset, which behaves like LanceDB on the only two operations the writer
    uses: upsert by identifier and deletion by identifiers."""

    def __init__(self) -> None:
        self.compactions: list[str] = []
        self.tables: dict[str, dict[str, Any]] = {}
        self.info = SimpleNamespace(tables={})

    def update_data(self, table_name: str, data: list[Any]) -> None:
        table = self.tables.setdefault(table_name, {})
        for row in data:
            table[row.id] = row

    def delete_data(self, table_name: str, ids: list[str]) -> None:
        table = self.tables.setdefault(table_name, {})
        for row_id in ids:
            table.pop(row_id, None)

    def get_data(self, table_name: str, ids: list[str] | None = None, *, where: str | None = None) -> list[Any]:
        return _matching(self.tables.get(table_name, {}), ids, where)

    def open_table(self, table_name: str) -> Any:
        self.compactions.append(table_name)
        return SimpleNamespace(optimize=lambda **_kwargs: None)

    def has_record_embeddings(self) -> bool:
        return "embeddings" in self.tables

    def create_record_embedding_table(self, dim: int, model_id: str) -> None:
        self.tables.setdefault("embeddings", {})
        self.info.tables["embeddings"] = _Vector
        self.space = {"model_id": model_id, "dim": dim}

    def record_embedding_space(self) -> dict[str, Any] | None:
        return getattr(self, "space", None)

    def checksum(self, table_name: str) -> str:
        """A fingerprint of the content, insensitive to the write order."""
        table = self.tables.get(table_name, {})
        material = json.dumps(sorted((row_id, row.payload) for row_id, row in table.items()))
        return hashlib.sha256(material.encode()).hexdigest()


@pytest.fixture
def dataset() -> _FakeDataset:
    return _FakeDataset()


class _EmptySource:
    """An empty dataset: the fake kind reads nothing from it, but the contract wants a reader."""

    def count_rows_where(self, table_name: str, where: str | None = None) -> int:
        return 0

    def record_embedding_space(self) -> dict[str, Any] | None:
        return None

    def get_data(
        self,
        table_name: str,
        ids: list[str] | None = None,
        limit: int | None = None,
        skip: int = 0,
        where: str | None = None,
        record_ids: list[str] | None = None,
    ) -> list[Any]:
        return []

    def get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str] | None:
        return None


def _reader() -> JobReader:
    from pixano_worker.media import MediaResolver

    return JobReader(lambda: _EmptySource(), MediaResolver("/medias", "/medias"))


def _writer(dataset: _FakeDataset, job_id: str = "job-1") -> JobWriter:
    return JobWriter(lambda: dataset, kind="fake", job_id=job_id)


class TestDeriveId:
    """Identity comes from the work, not from the execution that produced it."""

    def test_is_stable_across_calls(self) -> None:
        assert derive_id("fake", "item-1", 0) == derive_id("fake", "item-1", 0)

    def test_separates_outputs_of_one_key(self) -> None:
        assert derive_id("fake", "item-1", 0) != derive_id("fake", "item-1", 1)

    def test_separates_keys(self) -> None:
        assert derive_id("fake", "item-1", 0) != derive_id("fake", "item-2", 0)

    def test_separates_kinds(self) -> None:
        """Two processings on the same item must not overwrite each other."""
        assert derive_id("fake", "item-1", 0) != derive_id("embeddings", "item-1", 0)

    def test_does_not_depend_on_the_job(self) -> None:
        """The lot's central property: resubmitting replaces instead of duplicating.

        An identifier that carried the job would produce new rows on every submission, and
        the same processing rerun would double the dataset's content.
        """
        first = _writer(_FakeDataset(), job_id="job-1").ids_for("item-1", 3)
        second = _writer(_FakeDataset(), job_id="job-2").ids_for("item-1", 3)

        assert first == second


class TestReplay:
    """'The same job run twice' — the lot's definition of done."""

    def test_a_second_run_changes_nothing(self, dataset: _FakeDataset) -> None:
        rows = lambda: [_FakeRow("a"), _FakeRow("b"), _FakeRow("c")]  # noqa: E731

        _writer(dataset).replace("toy", "item-1", rows())
        first = (len(dataset.tables["toy"]), dataset.checksum("toy"))
        _writer(dataset).replace("toy", "item-1", rows())

        assert (len(dataset.tables["toy"]), dataset.checksum("toy")) == first

    def test_a_different_job_does_not_duplicate(self, dataset: _FakeDataset) -> None:
        """A resubmission is a different job, and must not double the content."""
        _writer(dataset, "job-1").replace("toy", "item-1", [_FakeRow("a"), _FakeRow("b")])
        before = dataset.checksum("toy")

        _writer(dataset, "job-2").replace("toy", "item-1", [_FakeRow("a"), _FakeRow("b")])

        assert len(dataset.tables["toy"]) == 2
        assert dataset.checksum("toy") == before

    def test_a_changed_result_replaces_the_old_one(self, dataset: _FakeDataset) -> None:
        _writer(dataset).replace("toy", "item-1", [_FakeRow("before")])

        _writer(dataset).replace("toy", "item-1", [_FakeRow("after")])

        assert [row.payload for row in dataset.tables["toy"].values()] == ["after"]

    def test_a_shorter_result_leaves_nothing_behind(self, dataset: _FakeDataset) -> None:
        """The case that plain replacement does not cover.

        A model that detected five objects and now sees only two would leave three orphan
        rows that nothing would ever clean up.
        """
        _writer(dataset).replace("toy", "item-1", [_FakeRow(str(n)) for n in range(5)])

        _writer(dataset).replace("toy", "item-1", [_FakeRow("0"), _FakeRow("1")])

        assert len(dataset.tables["toy"]) == 2

    def test_a_result_that_shrinks_by_more_than_a_window_leaves_nothing_behind(self, dataset: _FakeDataset) -> None:
        """Independent review, C6: the cleanup probed 32 ranks; a hundred boxes going to twenty kept 48."""
        _writer(dataset).replace("toy", "item-1", [_FakeRow(str(n)) for n in range(100)])

        _writer(dataset).replace("toy", "item-1", [_FakeRow(str(n)) for n in range(20)])

        assert len(dataset.tables["toy"]) == 20

    def test_another_model_adds_and_the_same_model_replaces(self, dataset: _FakeDataset) -> None:
        """Step 2 design: the replacement is scoped by (kind, model, key)."""
        yolo = JobWriter(lambda: dataset, "detection", "job-1", model=ModelIdentity("yolo"))
        detr = JobWriter(lambda: dataset, "detection", "job-2", model=ModelIdentity("detr"))
        yolo.replace("toy", "item-1", [_FakeRow(str(n)) for n in range(5)])
        detr.replace("toy", "item-1", [_FakeRow(str(n)) for n in range(3)])
        assert len(dataset.tables["toy"]) == 8, "two models, two sets of rows"

        JobWriter(lambda: dataset, "detection", "job-3", model=ModelIdentity("yolo")).replace(
            "toy", "item-1", [_FakeRow("0"), _FakeRow("1")]
        )

        assert len(dataset.tables["toy"]) == 5, "yolo replaced its five by two, detr's three are untouched"

    def test_an_empty_result_clears_the_key(self, dataset: _FakeDataset) -> None:
        _writer(dataset).replace("toy", "item-1", [_FakeRow("a"), _FakeRow("b")])

        _writer(dataset).replace("toy", "item-1", [])

        assert dataset.tables["toy"] == {}

    def test_other_keys_are_untouched(self, dataset: _FakeDataset) -> None:
        """Cleanup is scoped to the key: erasing one item's outputs must not touch those of
        another, nor those of another chunk of the same job."""
        _writer(dataset).replace("toy", "item-1", [_FakeRow("a"), _FakeRow("b")])
        _writer(dataset).replace("toy", "item-2", [_FakeRow("c")])

        _writer(dataset).replace("toy", "item-1", [])

        assert [row.payload for row in dataset.tables["toy"].values()] == ["c"]


class TestProvenance:
    """No job output must land in a dataset without knowing where it came from."""

    def test_names_the_kind_and_the_job(self, dataset: _FakeDataset) -> None:
        provenance = JobWriter(lambda: dataset, "fake", "job-42", "other").provenance()

        assert provenance["source_type"] == "other"
        assert provenance["source_name"] == "fake"
        assert json.loads(provenance["source_metadata"])["job_id"] == "job-42"

    def test_is_self_contained(self, dataset: _FakeDataset) -> None:
        """Step 2 design: jobs are cleaned by truncation, so the row must say by itself how it was made."""
        writer = JobWriter(
            lambda: dataset,
            "detection",
            "job-42",
            "model",
            params={"model": "yolo", "threshold": 0.4},
            model=ModelIdentity("yolo", "yolov8n.pt"),
        )

        metadata = json.loads(writer.provenance()["source_metadata"])

        assert metadata == {
            "job_id": "job-42",
            "kind": "detection",
            "model": "yolo",
            "model_version": "yolov8n.pt",
            "params": {"model": "yolo", "threshold": 0.4},
        }

    def test_only_a_model_output_is_to_be_reviewed(self, dataset: _FakeDataset) -> None:
        """A demonstration kind's rows, like a human's, carry no review status."""
        assert JobWriter(lambda: dataset, "detection", "j", "model").provenance()["review_status"] == "pending"
        assert "review_status" not in JobWriter(lambda: dataset, "label", "j", "other").provenance()

    def test_a_row_without_a_rank_under_the_prefix_is_left_alone(self, dataset: _FakeDataset) -> None:
        """Written by hand under a derived prefix: skipped, never a failure of every attempt."""
        writer = JobWriter(lambda: dataset, "fake", "j")
        stray_id = writer.ids_for("item-1", 1)[0].rsplit("-", 1)[0] + "-by-hand"
        dataset.tables.setdefault("toy", {})[stray_id] = _FakeRow("stray")
        dataset.tables["toy"][stray_id].id = stray_id

        writer.replace("toy", "item-1", [_FakeRow("a")])

        assert stray_id in dataset.tables["toy"]

    def test_says_nothing_about_a_model_it_does_not_know(self, dataset: _FakeDataset) -> None:
        """A kind without a model, or a server that gives no version: the keys are absent, not null."""
        without_version = JobWriter(lambda: dataset, "k", "j", model=ModelIdentity("clip")).provenance()
        without_model = JobWriter(lambda: dataset, "k", "j").provenance()

        assert json.loads(without_version["source_metadata"]) == {"job_id": "j", "kind": "k", "model": "clip"}
        assert "model" not in json.loads(without_model["source_metadata"])


class TestAgainstRealLance:
    """The previous tests go through a stand-in; these write into a real LanceDB.

    The stand-in reproduces the two operations the writer uses, but not Pixano's integrity
    checks — and those are what revealed that a job output cannot invent the records it
    attaches to.
    """

    @pytest.fixture
    def toy(self, tmp_path):
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas.annotations.classification import Classification
        from pixano.schemas.records import Record

        dataset = Dataset.create(
            tmp_path / "jouet",
            DatasetInfo(id="jouet", name="Jouet", record=Record, classification=Classification),
        )
        dataset.add_data("records", [Record(id=f"task-{n}") for n in range(60)])
        return dataset

    @staticmethod
    def _run(toy, job_id: str, task_count: int) -> None:
        from pixano_worker.kinds import FakeKind, FakeParams

        kind = FakeKind()
        params = FakeParams(task_count=task_count, chunk_size=20, seconds_per_task=0.0, write_to="classifications")
        for chunk in kind.plan(_reader(), params):
            writer = JobWriter(lambda: toy, kind.name, job_id, kind.source_type)
            kind.write(writer, kind.process(_reader(), chunk.payload, params), chunk.payload, params)

    @staticmethod
    def _fingerprint(toy) -> tuple[int, str]:
        rows = toy.get_data("classifications", limit=10_000)
        material = sorted((r.id, r.record_id, tuple(r.labels), r.source_name) for r in rows)
        return len(rows), hashlib.sha256(repr(material).encode()).hexdigest()

    def test_the_same_job_run_twice_writes_the_same_content(self, toy) -> None:
        """The lot's definition of done, against the real store."""
        self._run(toy, "job-1", 60)
        first = self._fingerprint(toy)

        self._run(toy, "job-1", 60)

        assert self._fingerprint(toy) == first

    def test_a_shrinking_output_is_cleaned_exactly_by_the_real_store(self, toy) -> None:
        """The prefix filter must be one LanceDB understands: `id LIKE 'prefix-%'`."""
        from pixano.schemas.annotations.classification import Classification

        writer = JobWriter(lambda: toy, "detection", "job-1", "model", model=ModelIdentity("yolo"))

        def boxes(count: int) -> list[Classification]:
            return [
                Classification(id="", record_id="task-0", labels=["x"], confidences=[1.0], **writer.provenance())
                for _ in range(count)
            ]

        writer.replace("classifications", "task-0", boxes(100))
        assert len(toy.get_data("classifications", limit=None)) == 100

        writer.replace("classifications", "task-0", boxes(20))

        assert len(toy.get_data("classifications", limit=None)) == 20

    def test_a_model_output_arrives_pending_and_a_reviewed_row_survives_a_rerun(self, toy) -> None:
        """Step 2 design: a rerun replaces what is still pending, never what someone looked at."""
        from pixano.schemas.annotations.classification import Classification

        writer = JobWriter(lambda: toy, "detection", "job-1", "model", model=ModelIdentity("yolo"))

        def boxes(labels: list[str]) -> list[Classification]:
            return [
                Classification(id="", record_id="task-0", labels=[label], confidences=[1.0], **writer.provenance())
                for label in labels
            ]

        first = writer.replace("classifications", "task-0", boxes(["cat", "dog", "cow"]))
        assert {row.review_status for row in toy.get_data("classifications", limit=None)} == {"pending"}

        # A human accepts the second box; the two others stay pending.
        accepted = toy.get_data("classifications", ids=[first[1]])[0]
        accepted.review_status = "accepted"
        toy.update_data("classifications", [accepted])

        writer.replace("classifications", "task-0", boxes(["horse"]))

        rows = {row.labels[0]: row.review_status for row in toy.get_data("classifications", limit=None)}
        assert rows == {"dog": "accepted", "horse": "pending"}

    @staticmethod
    def _review(toy, row_id: str, status: str) -> None:
        row = toy.get_data("classifications", ids=[row_id])[0]
        row.review_status = status
        toy.update_data("classifications", [row])

    def _detections(self, toy):
        from pixano.schemas.annotations.classification import Classification

        writer = JobWriter(lambda: toy, "detection", "job-1", "model", model=ModelIdentity("yolo"))

        def run(labels: list[str]) -> list[str]:
            rows = [
                Classification(id="", record_id="task-0", labels=[label], confidences=[1.0], **writer.provenance())
                for label in labels
            ]
            return writer.replace("classifications", "task-0", rows)

        return run

    def _statuses(self, toy) -> dict[str, tuple[str, str]]:
        return {row.id: (row.labels[0], row.review_status) for row in toy.get_data("classifications", limit=None)}

    @pytest.mark.parametrize("status", ["accepted", "corrected", "rejected"])
    def test_every_reviewed_status_is_frozen(self, toy, status: str) -> None:
        run = self._detections(toy)
        first = run(["cat", "dog"])
        self._review(toy, first[0], status)

        run([])

        assert self._statuses(toy) == {first[0]: ("cat", status)}

    def test_new_rows_skip_the_ranks_reviewed_rows_hold(self, toy) -> None:
        """A frozen rank 0 and more new rows than frozen ones: the new rows go around it."""
        run = self._detections(toy)
        first = run(["cat"])
        self._review(toy, first[0], "accepted")

        written = run(["a", "b", "c"])

        assert first[0] not in written
        assert sorted(label for label, _ in self._statuses(toy).values()) == ["a", "b", "c", "cat"]

    def test_rerunning_with_frozen_rows_is_idempotent(self, toy) -> None:
        run = self._detections(toy)
        first = run(["cat", "dog", "cow"])
        self._review(toy, first[1], "corrected")
        run(["x", "y"])
        once = self._statuses(toy)

        run(["x", "y"])

        assert self._statuses(toy) == once

    def test_resubmitting_does_not_duplicate(self, toy) -> None:
        self._run(toy, "job-1", 60)
        first = self._fingerprint(toy)

        self._run(toy, "job-2", 60)

        assert self._fingerprint(toy) == first

    def test_every_row_says_where_it_came_from(self, toy) -> None:
        self._run(toy, "job-1", 20)

        rows = toy.get_data("classifications", limit=100)
        assert rows
        for row in rows:
            assert row.source_name == "fake"
            assert json.loads(row.source_metadata)["job_id"] == "job-1"

    def test_a_kind_that_runs_no_model_does_not_claim_to(self, toy) -> None:
        """`model` would designate a prediction; this one is not one."""
        self._run(toy, "job-1", 20)

        assert toy.get_data("classifications", limit=1)[0].source_type == "other"

    def test_it_cannot_write_into_a_dataset_it_was_not_built_for(self, toy, tmp_path) -> None:
        """The guard is structural, and is worth more than a naming convention.

        Table names are canonical in Pixano, so "a toy table" does not exist. But a real
        dataset does not have the records this kind invents, and the integrity check refuses
        the output rather than letting it settle in.
        """
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas.annotations.classification import Classification
        from pixano.schemas.records import Record

        autre = Dataset.create(
            tmp_path / "autre",
            DatasetInfo(id="autre", name="Autre", record=Record, classification=Classification),
        )
        autre.add_data("records", [Record(id="une-vraie-image")])

        with pytest.raises(Exception):
            self._run(autre, "job-1", 20)

    def test_a_kind_declares_what_it_produces(self, dataset: _FakeDataset) -> None:
        """The vocabulary is that of the schemas: model, human, ground_truth, other.

        Writing "job" there would be refused, and so much the better — what matters to a
        reviewer is knowing whether an annotation comes from a model, not which cog wrote it.
        """
        assert JobWriter(lambda: dataset, "embeddings", "j", "model").provenance()["source_type"] == "model"


class TestRecordEmbeddings:
    """An embeddings table accepts only one model."""

    def test_the_first_write_creates_the_table_for_its_model(self, dataset: _FakeDataset) -> None:
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")

        writer.write_record_embeddings(["r1", "r2"], [[0.1, 0.2], [0.3, 0.4]], model="clip")

        assert dataset.record_embedding_space() == {"model_id": "clip", "dim": 2}
        assert len(dataset.tables["embeddings"]) == 2

    def test_the_same_model_replaces_its_vectors(self, dataset: _FakeDataset) -> None:
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_record_embeddings(["r1"], [[0.1, 0.2]], model="clip")

        writer.write_record_embeddings(["r1"], [[0.5, 0.6]], model="clip")

        assert len(dataset.tables["embeddings"]) == 1

    def test_another_model_is_refused_rather_than_mixed_in(self, dataset: _FakeDataset) -> None:
        """Same dimension, other model: nothing would break on write, the search would be wrong."""
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_record_embeddings(["r1"], [[0.1, 0.2]], model="clip")

        with pytest.raises(ValueError, match="dinov2"):
            writer.write_record_embeddings(["r2"], [[0.3, 0.4]], model="dinov2")

        assert list(dataset.tables["embeddings"]) == [derive_id("embeddings", "r1", 0)]

    def test_another_dimension_is_refused(self, dataset: _FakeDataset) -> None:
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_record_embeddings(["r1"], [[0.1, 0.2]], model="clip")

        with pytest.raises(ValueError, match="dimension 3"):
            writer.write_record_embeddings(["r2"], [[0.3, 0.4, 0.5]], model="clip")


class TestCompaction:
    """Independent review, C5: every write creates a Lance version, nothing reclaimed them."""

    def test_compacts_after_enough_writes(self, dataset: _FakeDataset, monkeypatch: pytest.MonkeyPatch) -> None:
        from pixano_worker import writer as writer_module

        monkeypatch.setattr(writer_module, "COMPACT_EVERY_WRITES", 3)
        writer = JobWriter(lambda: dataset, "label", "job-1", "other")

        for n in range(7):
            writer.replace("classifications", key=f"task-{n}", rows=[_FakeRow(f"r{n}")])

        assert dataset.compactions == ["classifications", "classifications"]

    def test_a_failed_compaction_does_not_fail_the_write(
        self, dataset: _FakeDataset, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pixano_worker import writer as writer_module

        monkeypatch.setattr(writer_module, "COMPACT_EVERY_WRITES", 1)
        dataset.open_table = lambda name: (_ for _ in ()).throw(RuntimeError("lance unavailable"))  # type: ignore[assignment]
        writer = JobWriter(lambda: dataset, "label", "job-1", "other")

        written = writer.replace("classifications", key="task-0", rows=[_FakeRow("r0")])

        assert written and dataset.tables["classifications"]

    def test_against_real_lance_keeps_the_version_count_bounded(
        self, tmp_path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from pixano_worker import writer as writer_module

        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas.annotations.classification import Classification
        from pixano.schemas.records import Record

        monkeypatch.setattr(writer_module, "COMPACT_EVERY_WRITES", 10)
        monkeypatch.setattr(writer_module, "KEEP_OLD_VERSIONS_FOR", timedelta(0))
        toy = Dataset.create(
            tmp_path / "jouet", DatasetInfo(id="jouet", name="Jouet", record=Record, classification=Classification)
        )
        toy.add_data("records", [Record(id=f"task-{n}") for n in range(40)])
        writer = JobWriter(lambda: toy, "label", "job-1", "other")

        for n in range(40):
            row = Classification(id="", record_id=f"task-{n}", labels=["x"], confidences=[1.0], **writer.provenance())
            writer.replace("classifications", key=f"task-{n}", rows=[row])

        versions = len(toy.open_table("classifications").list_versions())
        assert versions < 40, f"{versions} versions for 40 writes: nothing was compacted"


class TestEmbeddingTableCreatedElsewhere:
    """Independent review, step 4: a cached dataset did not see the table created by another worker."""

    def test_rereads_the_dataset_before_creating(self, dataset: _FakeDataset) -> None:
        fresh = _FakeDataset()
        fresh.create_record_embedding_table(dim=2, model_id="clip")
        created_on_stale = []
        dataset.create_record_embedding_table = lambda dim, model_id: created_on_stale.append(model_id)  # type: ignore[assignment]
        writer = JobWriter(lambda: dataset, "embeddings", "job-1", reopen_dataset=lambda: fresh)

        writer.write_record_embeddings(["r1"], [[0.1, 0.2]], model="clip")

        assert created_on_stale == [], "the existing table would have been overwritten"
        assert len(fresh.tables["embeddings"]) == 1
