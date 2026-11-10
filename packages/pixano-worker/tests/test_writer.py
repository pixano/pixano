# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests of the idempotent writing of job results."""

import hashlib
import json
import re
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from typing import Any

import pytest
from pixano_worker.reader import JobReader
from pixano_worker.writer import JobWriter, ModelIdentity, derive_id

from pixano.datasets.embedding_spaces import AmbiguousModelError, EmbeddingSpaces
from pixano.datasets.utils.errors import DatasetAccessError


class _Vector:
    """An embedding row, for the stand-in."""

    def __init__(self, id: str, record_id: str, vector: Any, view_id: str = "") -> None:
        self.id, self.record_id, self.view_id, self.vector = id, record_id, view_id, vector


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
        # The embeddings spaces, kept by the real description: the stand-in decides nothing of its own.
        self.spaces = EmbeddingSpaces()

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

    def open_table(self, name: str) -> Any:
        self.compactions.append(name)
        return SimpleNamespace(optimize=lambda **_kwargs: None)

    def record_embedding_spaces(self) -> list[dict[str, Any]]:
        return [space.as_document() for space in self.spaces.spaces]

    def upsert_record_embeddings(
        self, model_id: str, checkpoint: str, rows: list[dict[str, Any]], *, index_type: str = "IVF_PQ"
    ) -> dict[str, Any]:
        dim = len(rows[0]["vector"])
        space = self.spaces.matching(model_id, checkpoint, dim, strict=True)
        if space is not None and space.dim != dim:
            raise DatasetAccessError(f"embeddings of model '{model_id}' of dimension {space.dim}, not {dim}")
        if space is None:
            space = self.spaces.new_space(model_id, checkpoint, dim, index_type=index_type)
            self.spaces = self.spaces.with_space(space)
            self.tables.setdefault(space.table, {})
            self.info.tables[space.table] = _Vector
        elif checkpoint and not space.checkpoint:
            self.spaces = self.spaces.with_checkpoint(space, checkpoint)
            space = self.spaces.get(space.id) or space
        self.update_data(space.table, [_Vector(**row) for row in rows])
        return space.as_document()

    def empty_model_record_embeddings(
        self, model_id: str, checkpoint: str = "", index_type: str | None = None
    ) -> dict[str, Any] | None:
        if not checkpoint and any(space.model_id == model_id and space.checkpoint for space in self.spaces.spaces):
            raise AmbiguousModelError(f"model '{model_id}' holds the embeddings of a checkpoint told")
        space = self.spaces.matching(model_id, checkpoint or "", strict=True)
        if space is None:
            return None
        emptied = replace(space, checkpoint=checkpoint or space.checkpoint, index_type=index_type or space.index_type)
        self.spaces = self.spaces.replacing(emptied)
        # The vectors go with their table, as in LanceDB.
        self.tables.pop(space.table, None)
        return emptied.as_document()

    def record_embedding_space(self, model: str | None = None) -> dict[str, Any] | None:
        space = self.spaces.find(model)
        return space.as_document() if space is not None else None

    def checksum(self, table_name: str) -> str:
        """A fingerprint of the content, insensitive to the write order."""
        table = self.tables.get(table_name, {})
        material = json.dumps(sorted((row_id, row.payload) for row_id, row in table.items()))
        return hashlib.sha256(material.encode()).hexdigest()


def _space(dataset: Any, model: str) -> dict[str, Any]:
    """The space of a model the test wrote the vectors of."""
    space = dataset.record_embedding_space(model)
    assert space is not None, f"no embeddings of {model}"
    return space


@pytest.fixture
def dataset() -> _FakeDataset:
    return _FakeDataset()


class _EmptySource:
    """An empty dataset: the fake kind reads nothing from it, but the contract wants a reader."""

    info = SimpleNamespace(tables={})

    def count_rows_where(self, table_name: str, where: str | None = None) -> int:
        return 0

    def record_embedding_space(self, model: str | None = None) -> dict[str, Any] | None:
        return None

    def record_embeddings_fully_read(self) -> bool:
        return True

    def read_record_vectors(self, model: str | None = None) -> None:
        return None

    def record_embedding_spaces(self) -> list[dict[str, Any]]:
        return []

    def get_all_ids(self, table_name: str = "records") -> list[str]:
        return []

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
        """The central property: resubmitting replaces instead of duplicating.

        An identifier that carried the job would produce new rows on every submission, and
        the same processing rerun would double the dataset's content.
        """
        first = _writer(_FakeDataset(), job_id="job-1").ids_for("item-1", 3)
        second = _writer(_FakeDataset(), job_id="job-2").ids_for("item-1", 3)

        assert first == second


class TestReplay:
    """The same job run twice."""

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
        """The cleanup probed 32 ranks; a hundred boxes going to twenty kept 48."""
        _writer(dataset).replace("toy", "item-1", [_FakeRow(str(n)) for n in range(100)])

        _writer(dataset).replace("toy", "item-1", [_FakeRow(str(n)) for n in range(20)])

        assert len(dataset.tables["toy"]) == 20

    def test_another_model_adds_and_the_same_model_replaces(self, dataset: _FakeDataset) -> None:
        """The replacement is scoped by (kind, model, key)."""
        yolo = JobWriter(lambda: dataset, "detection", "job-1", model=ModelIdentity("yolo"))
        detr = JobWriter(lambda: dataset, "detection", "job-2", model=ModelIdentity("detr"))
        yolo.replace("toy", "item-1", [_FakeRow(str(n)) for n in range(5)])
        detr.replace("toy", "item-1", [_FakeRow(str(n)) for n in range(3)])
        assert len(dataset.tables["toy"]) == 8, "two models, two sets of rows"

        JobWriter(lambda: dataset, "detection", "job-3", model=ModelIdentity("yolo")).replace(
            "toy", "item-1", [_FakeRow("0"), _FakeRow("1")]
        )

        assert len(dataset.tables["toy"]) == 5, "yolo replaced its five by two, detr's three are untouched"

    def test_a_row_without_a_rank_under_the_prefix_is_left_alone(self, dataset: _FakeDataset) -> None:
        """Written by hand under a derived prefix: skipped, never a failure of every attempt."""
        writer = JobWriter(lambda: dataset, "fake", "j")
        stray_id = writer.ids_for("item-1", 1)[0].rsplit("-", 1)[0] + "-by-hand"
        dataset.tables.setdefault("toy", {})[stray_id] = _FakeRow("stray")
        dataset.tables["toy"][stray_id].id = stray_id

        writer.replace("toy", "item-1", [_FakeRow("a")])

        assert stray_id in dataset.tables["toy"]

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
        """Jobs are cleaned by truncation, so the row must say by itself how it was made."""
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
            tmp_path / "toy",
            DatasetInfo(id="toy", name="Toy", record=Record, classification=Classification),
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
        """The same job run twice, against the real store."""
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

    def test_a_model_output_arrives_pending_and_an_accepted_row_survives_a_rerun(self, toy) -> None:
        """A rerun replaces what is still pending, never what a person accepted."""
        from pixano.schemas.annotations.classification import Classification

        writer = JobWriter(lambda: toy, "detection", "job-1", "model", model=ModelIdentity("yolo"))

        def boxes(labels: list[str]) -> list[Classification]:
            return [
                Classification(id="", record_id="task-0", labels=[label], confidences=[1.0], **writer.provenance())
                for label in labels
            ]

        first = writer.replace("classifications", "task-0", boxes(["cat", "dog", "cow"]))
        assert {row.review_status for row in toy.get_data("classifications", limit=None)} == {"pending"}

        # A person accepts the second box; the two others stay pending.
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

    def test_an_accepted_row_is_frozen(self, toy) -> None:
        run = self._detections(toy)
        first = run(["cat", "dog"])
        self._review(toy, first[0], "accepted")

        run([])

        assert self._statuses(toy) == {first[0]: ("cat", "accepted")}

    def test_a_model_row_stored_without_a_status_is_replaced(self, toy) -> None:
        """Re-imported from JSONL, whose grammar carries no status: nobody reviewed it, as the
        application reads it (`NOT_REVIEWED_STATUSES`), so a rerun replaces it like a pending one."""
        run = self._detections(toy)
        first = run(["cat", "dog"])
        self._review(toy, first[0], "")

        written = run(["cow"])

        assert self._statuses(toy) == {written[0]: ("cow", "pending")}

    def test_new_rows_skip_the_ranks_accepted_rows_hold(self, toy) -> None:
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
        self._review(toy, first[1], "accepted")
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

        other = Dataset.create(
            tmp_path / "other",
            DatasetInfo(id="other", name="Other", record=Record, classification=Classification),
        )
        other.add_data("records", [Record(id="a-real-image")])

        with pytest.raises(Exception):
            self._run(other, "job-1", 20)

    def test_a_kind_declares_what_it_produces(self, dataset: _FakeDataset) -> None:
        """The vocabulary is that of the schemas: model, human, ground_truth, other.

        Writing "job" there would be refused, and so much the better — what matters to a
        reviewer is knowing whether an annotation comes from a model, not which cog wrote it.
        """
        assert JobWriter(lambda: dataset, "embeddings", "j", "model").provenance()["source_type"] == "model"


class TestMediaEmbeddings:
    """Each model writes a table of its own, a model being its name and its checkpoint."""

    def test_the_first_write_creates_the_table_for_its_model(self, dataset: _FakeDataset) -> None:
        """With the vector index the job's closing step will give it, the one measured best."""
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")

        writer.write_media_embeddings(
            ["r1", "r2"], ["v-r1", "v-r2"], [[0.1, 0.2], [0.3, 0.4]], model="clip", checkpoint="ckpt-a"
        )

        space = _space(dataset, "clip")
        assert (space["model_id"], space["checkpoint"], space["dim"], space["index_type"]) == (
            "clip",
            "ckpt-a",
            2,
            "IVF_SQ",
        )
        assert len(dataset.tables[space["table"]]) == 2

    def test_the_same_model_replaces_its_vectors(self, dataset: _FakeDataset) -> None:
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.1, 0.2]], model="clip")

        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.5, 0.6]], model="clip")

        assert len(dataset.tables[_space(dataset, "clip")["table"]]) == 1

    def test_a_record_with_several_media_gets_a_vector_each(self, dataset: _FakeDataset) -> None:
        """An embedding belongs to a medium — nuScenes has six cameras per record."""
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")

        writer.write_media_embeddings(["r1", "r1"], ["cam-front", "cam-back"], [[0.1, 0.2], [0.3, 0.4]], model="clip")
        writer.write_media_embeddings(["r1"], ["cam-front"], [[0.9, 0.9]], model="clip")

        table = dataset.tables[_space(dataset, "clip")["table"]]
        rows = {row.view_id: (row.record_id, row.vector) for row in table.values()}
        assert rows == {"cam-front": ("r1", [0.9, 0.9]), "cam-back": ("r1", [0.3, 0.4])}

    def test_media_and_vectors_must_match(self, dataset: _FakeDataset) -> None:
        with pytest.raises(ValueError, match="2 media for 1 vectors"):
            JobWriter(lambda: dataset, "embeddings", "j").write_media_embeddings(
                ["r1", "r1"], ["a", "b"], [[0.1]], model="clip"
            )

    def test_another_model_writes_a_table_of_its_own(self, dataset: _FakeDataset) -> None:
        """Same dimension, other model: mixed in one table, every search would be wrong without a word."""
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.1, 0.2]], model="clip")

        writer.write_media_embeddings(["r2"], ["v-r2"], [[0.3, 0.4]], model="dinov2")

        clip, dinov2 = _space(dataset, "clip"), _space(dataset, "dinov2")
        assert list(dataset.tables[clip["table"]]) == [derive_id("embeddings", "v-r1", 0)]
        assert list(dataset.tables[dinov2["table"]]) == [derive_id("embeddings", "v-r2", 0)]

    def test_another_checkpoint_of_the_model_writes_a_table_of_its_own(self, dataset: _FakeDataset) -> None:
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.1, 0.2]], model="clip", checkpoint="ckpt-a")

        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.3, 0.4]], model="clip", checkpoint="ckpt-b")

        assert [space.checkpoint for space in dataset.spaces.spaces] == ["ckpt-a", "ckpt-b"]

    def test_the_very_model_at_another_dimension_is_refused(self, dataset: _FakeDataset) -> None:
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.1, 0.2]], model="clip", checkpoint="ckpt-a")

        with pytest.raises(ValueError, match="dimension 2, not 3"):
            writer.write_media_embeddings(["r2"], ["v-r2"], [[0.3, 0.4, 0.5]], model="clip", checkpoint="ckpt-a")

    def test_a_checkpoint_left_untold_never_writes_into_one_of_several(self, dataset: _FakeDataset) -> None:
        """Two checkpoints of the model, and a writer that cannot tell its own: no guess, no row."""
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.1, 0.2]], model="clip", checkpoint="ckpt-a")
        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.3, 0.4]], model="clip", checkpoint="ckpt-b")

        with pytest.raises(AmbiguousModelError, match="ckpt-a, ckpt-b"):
            writer.write_media_embeddings(["r2"], ["v-r2"], [[0.5, 0.6]], model="clip")

        assert sum(len(dataset.tables[space.table]) for space in dataset.spaces.spaces) == 2

    def test_a_checkpoint_the_inference_tells_late_is_recorded_on_the_same_space(self, dataset: _FakeDataset) -> None:
        """An inference that could not tell its checkpoint for the first chunk: one space all the same."""
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.1, 0.2]], model="clip")

        writer.write_media_embeddings(["r2"], ["v-r2"], [[0.3, 0.4]], model="clip", checkpoint="ckpt-a")

        (space,) = dataset.spaces.spaces
        assert space.checkpoint == "ckpt-a"
        assert len(dataset.tables[space.table]) == 2

    def test_emptying_a_models_embeddings_keeps_its_space_and_leaves_the_others(self, dataset: _FakeDataset) -> None:
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.1, 0.2]], model="clip", checkpoint="ckpt-a")
        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.3, 0.4]], model="dinov2", checkpoint="vitb14")

        writer.empty_embeddings("clip", "ckpt-a")

        clip, dinov2 = dataset.spaces.spaces
        assert (clip.model_id, clip.index_type, dataset.spaces.default) == ("clip", "IVF_SQ", clip.id)
        assert (clip.table in dataset.tables, len(dataset.tables[dinov2.table])) == (False, 1)

    def test_emptying_a_model_the_dataset_holds_none_of_does_nothing(self, dataset: _FakeDataset) -> None:
        """`prepare` may run twice: a planner that died after it lets the next one start over."""
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        writer.write_media_embeddings(["r1"], ["v-r1"], [[0.1, 0.2]], model="dinov2", checkpoint="vitb14")

        writer.empty_embeddings("clip", "ckpt-a")

        (dinov2,) = dataset.spaces.spaces
        assert (dinov2.model_id, len(dataset.tables[dinov2.table])) == ("dinov2", 1)


class TestCompaction:
    """Every write creates a Lance version, nothing reclaimed them."""

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
            tmp_path / "toy", DatasetInfo(id="toy", name="Toy", record=Record, classification=Classification)
        )
        toy.add_data("records", [Record(id=f"task-{n}") for n in range(40)])
        writer = JobWriter(lambda: toy, "label", "job-1", "other")

        for n in range(40):
            row = Classification(id="", record_id=f"task-{n}", labels=["x"], confidences=[1.0], **writer.provenance())
            writer.replace("classifications", key=f"task-{n}", rows=[row])

        versions = len(toy.open_table("classifications").list_versions())
        assert versions < 40, f"{versions} versions for 40 writes: nothing was compacted"


class TestEmbeddingSpaceCreatedElsewhere:
    """A worker's cached dataset did not see the space another worker created: it finds it, not recreates it."""

    def test_writes_into_the_space_another_worker_created(self, tmp_path) -> None:
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas.records import Record

        dataset = Dataset.create(tmp_path / "shared", DatasetInfo(id="shared", name="Shared", record=Record))
        dataset.add_data("records", [Record(id="r1"), Record(id="r2")])
        stale = Dataset(dataset.path)
        JobWriter(lambda: dataset, "embeddings", "job-1").write_media_embeddings(
            ["r1"], ["v-r1"], [[0.1, 0.2]], model="clip", checkpoint="ckpt-a"
        )

        JobWriter(lambda: stale, "embeddings", "job-1").write_media_embeddings(
            ["r2"], ["v-r2"], [[0.3, 0.4]], model="clip", checkpoint="ckpt-a"
        )

        reopened = Dataset(dataset.path)
        (space,) = reopened.record_embedding_spaces()
        assert reopened.open_table(space["table"]).count_rows() == 2

    def test_creates_again_the_space_another_worker_deleted_rather_than_write_from_what_it_read(
        self, tmp_path
    ) -> None:
        """Another worker's replacement deleted the space this worker's cached dataset still holds."""
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas.records import Record

        dataset = Dataset.create(tmp_path / "shared", DatasetInfo(id="shared", name="Shared", record=Record))
        dataset.add_data("records", [Record(id="r1"), Record(id="r2")])
        JobWriter(lambda: dataset, "embeddings", "job-1").write_media_embeddings(
            ["r1"], ["v-r1"], [[0.1, 0.2]], model="clip", checkpoint="ckpt-a"
        )
        stale = Dataset(dataset.path)
        # Deleted from the application, as a person can.
        other = Dataset(dataset.path)
        other.drop_record_embeddings(_space(other, "clip")["id"])

        JobWriter(lambda: stale, "embeddings", "job-2").write_media_embeddings(
            ["r2"], ["v-r2"], [[0.3, 0.4]], model="clip", checkpoint="ckpt-a"
        )

        reopened = Dataset(dataset.path)
        (space,) = reopened.record_embedding_spaces()
        assert reopened.open_table(space["table"]).count_rows() == 1


class TestIndexingEmbeddings:
    """The embeddings job's closing step, against real Lance: the indexes a search reads."""

    #: Vectors per write, as chunks deliver them: the table is built the way a job builds it.
    VECTORS_PER_WRITE = 250

    @classmethod
    def _embedded(cls, tmp_path, vectors: int) -> tuple[Any, JobWriter]:
        import numpy as np

        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas.records import Record

        dataset = Dataset.create(tmp_path / "embedded", DatasetInfo(id="embedded", name="Embedded", record=Record))
        dataset.add_data("records", [Record(id=f"rec-{n}") for n in range(vectors)] + [Record(id="rec-new")])
        writer = JobWriter(lambda: dataset, "embeddings", "job-1")
        rng = np.random.default_rng(3)
        for start in range(0, vectors, cls.VECTORS_PER_WRITE):
            batch = range(start, min(start + cls.VECTORS_PER_WRITE, vectors))
            writer.write_media_embeddings(
                [f"rec-{n}" for n in batch],
                [f"img-{n}" for n in batch],
                rng.standard_normal((len(batch), 16)).tolist(),
                model="clip",
            )
        return dataset, writer

    @staticmethod
    def _indexes(dataset: Any) -> dict[str, str]:
        """The clip embeddings table's indexes, by the column each covers."""
        table = dataset.open_table(_space(dataset, "clip")["table"])
        return {index.columns[0]: index.index_type for index in table.list_indices()}

    def test_a_small_table_gets_its_record_index_and_no_vector_index(self, tmp_path) -> None:
        """Below the threshold, exact search is fast, and an index would only make it approximate."""
        dataset, writer = self._embedded(tmp_path, 300)

        assert writer.index_embeddings("clip", min_rows=1_000) == []

        assert self._indexes(dataset) == {"record_id": "BTree"}

    def test_a_large_table_gets_the_vector_index_its_descriptor_declares(self, tmp_path) -> None:
        """Over every vector, none left to an exact scan."""
        dataset, writer = self._embedded(tmp_path, 1_000)

        assert writer.index_embeddings("clip", min_rows=1_000) == ["IVF_SQ"]

        assert self._indexes(dataset) == {"record_id": "BTree", "vector": "IvfSq"}
        stats = dataset.open_table(_space(dataset, "clip")["table"]).index_stats("vector_idx")
        assert (stats.num_indexed_rows, stats.num_unindexed_rows) == (1_000, 0)

    def test_indexing_again_rebuilds_rather_than_stacks(self, tmp_path) -> None:
        """A final chunk run again, after its worker died, leaves the table as one run does."""
        dataset, writer = self._embedded(tmp_path, 1_000)
        writer.index_embeddings("clip", min_rows=1_000)
        writer.write_media_embeddings(["rec-new"], ["img-new"], [[0.5] * 16], model="clip")

        writer.index_embeddings("clip", min_rows=1_000)
        writer.index_embeddings("clip", min_rows=1_000)

        assert self._indexes(dataset) == {"record_id": "BTree", "vector": "IvfSq"}
        stats = dataset.open_table(_space(dataset, "clip")["table"]).index_stats("vector_idx")
        assert (stats.num_indexed_rows, stats.num_unindexed_rows) == (1_001, 0)

    def test_a_search_through_the_index_finds_the_vector_asked_for(self, tmp_path) -> None:
        dataset, writer = self._embedded(tmp_path, 1_000)
        writer.index_embeddings("clip", min_rows=1_000)
        query = (
            dataset.open_table(_space(dataset, "clip")["table"])
            .search()
            .where("view_id = 'img-421'")
            .to_list()[0]["vector"]
        )

        records, _ = dataset.search_records(list(query), k=1)

        assert [record.id for record in records] == ["rec-421"]

    def test_a_dataset_without_embeddings_has_nothing_to_index(self, tmp_path) -> None:
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas.records import Record

        dataset = Dataset.create(tmp_path / "bare", DatasetInfo(id="bare", name="Bare", record=Record))

        assert JobWriter(lambda: dataset, "embeddings", "job-1").index_embeddings("clip", min_rows=1) == []

    def test_indexes_every_checkpoint_of_the_models_name(self, tmp_path) -> None:
        """The closing step cannot tell which checkpoint the job wrote: it indexes them all."""
        dataset, writer = self._embedded(tmp_path, 1_000)
        # The space learns its checkpoint; another checkpoint gets a space of its own.
        writer.write_media_embeddings(["rec-0"], ["img-0"], [[0.5] * 16], model="clip", checkpoint="ckpt-a")
        writer.write_media_embeddings(["rec-1"], ["img-1"], [[0.5] * 16], model="clip", checkpoint="ViT-L-14")

        built = writer.index_embeddings("clip", min_rows=1_000)

        assert built == ["IVF_SQ"]
        tables = {space["checkpoint"]: space["table"] for space in dataset.record_embedding_spaces()}
        indexes = {
            checkpoint: {index.columns[0] for index in dataset.open_table(table).list_indices()}
            for checkpoint, table in tables.items()
        }
        assert indexes == {"ckpt-a": {"record_id", "vector"}, "ViT-L-14": {"record_id"}}

    def test_a_space_that_cannot_be_indexed_keeps_none_of_the_others_from_it(self, tmp_path) -> None:
        """Its failure is raised once the others were indexed: the job is tried again, not left unindexed."""
        dataset, writer = self._embedded(tmp_path, 1_000)
        writer.write_media_embeddings(["rec-0"], ["img-0"], [[0.5] * 16], model="clip", checkpoint="ckpt-a")
        broken = writer.write_media_embeddings(["rec-1"], ["img-1"], [[0.5] * 16], model="clip", checkpoint="ViT-L-14")
        assert broken is not None
        dataset._db_connection.drop_table(broken["table"])

        with pytest.raises(Exception, match=broken["table"]):
            writer.index_embeddings("clip", min_rows=1_000)

        indexed = next(space for space in dataset.record_embedding_spaces() if space["checkpoint"] == "ckpt-a")
        assert {index.columns[0] for index in dataset.open_table(indexed["table"]).list_indices()} == {
            "record_id",
            "vector",
        }

    def test_indexes_the_table_of_its_own_model(self, tmp_path) -> None:
        """Another model's table is left as it is."""
        dataset, writer = self._embedded(tmp_path, 300)
        writer.write_media_embeddings(["rec-1"], ["img-1"], [[0.5] * 8], model="dinov2")
        dinov2 = _space(dataset, "dinov2")

        writer.index_embeddings("dinov2", min_rows=1_000)

        indexed = {index.columns[0] for index in dataset.open_table(dinov2["table"]).list_indices()}
        assert (indexed, self._indexes(dataset)) == ({"record_id"}, {})
