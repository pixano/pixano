# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""Tests of the idempotent writing of job results."""

import hashlib
import json
import re
from collections import defaultdict
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

    # The statistics the writer writes are tested on a real dataset (test_statistics.py): these
    # stand in for the protocol only.
    def ensure_statistic_columns(self, level: Any, columns: dict[str, str]) -> str:
        raise NotImplementedError

    def write_statistic_values(self, level: Any, rows: list[dict[str, Any]], columns: dict[str, str]) -> list[str]:
        raise NotImplementedError

    def record_computed_statistics(self, computed: list[Any]) -> None:
        raise NotImplementedError

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

    def ensure_entity_text_field(self, name: str) -> None:
        self.entity_fields: set[str] = {*getattr(self, "entity_fields", set()), name}

    def ensure_annotation_table(self, slot: str) -> str:
        from pixano.schemas import canonical_table_name_for_slot

        table_name = canonical_table_name_for_slot(slot)
        self.tables.setdefault(table_name, {})
        return table_name

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


# A mask on the scene's image, which is not square, like every image of these fixtures: two rows,
# three columns, the left column empty and the two right ones full, as pycocotools encodes it.
MASK_SIZE = [2, 3]
MASK_COUNTS = b"24"


class TestDetectedObjects:
    """A detected box comes with the object it names, in the entities table.

    Other kinds annotate those objects — a mask on the object of the box that prompted it. Only a
    person's work on an object holds it; a model's unreviewed rows go with it when the detection
    rewrites or sweeps it.
    """

    @pytest.fixture
    def scene(self, tmp_path):
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas import BBox, CompressedRLE, Entity, EntityDynamicState, Image, Record, Tracklet

        dataset = Dataset.create(
            tmp_path / "scene",
            DatasetInfo(
                id="scene",
                name="Scene",
                record=Record,
                entity=Entity,
                entity_dynamic_state=EntityDynamicState,
                bbox=BBox,
                mask=CompressedRLE,
                tracklet=Tracklet,
                views={"image": Image},
            ),
        )
        dataset.add_records({"records": [Record(id="r1")]})
        return dataset

    @staticmethod
    def _detect(scene, classes: list[str], job_id: str = "job-1", covers: Any = None) -> list[str]:
        from pixano.schemas import BBox

        writer = JobWriter(lambda: scene, "detection", job_id, "model", model=ModelIdentity("yolo"))
        field = writer.ensure_label_field()
        boxes = [
            BBox(
                id="",
                record_id="r1",
                view_id="v1",
                coords=[0.1, 0.1, 0.2, 0.2],
                format="xywh",
                is_normalized=True,
                **writer.provenance(),
            )
            for _ in classes
        ]
        entities = [writer.table_schema("entities")(id="", record_id="r1", **{field: name}) for name in classes]
        return writer.replace("bboxes", "v1", boxes, entities, covers)

    @staticmethod
    def _objects(scene) -> dict[str, tuple[str, str]]:
        """Each box's class, through the entity it points to, and its review status."""
        entities = {entity.id: entity.category for entity in scene.get_data("entities", limit=None)}
        return {box.id: (entities[box.entity_id], box.review_status) for box in scene.get_data("bboxes", limit=None)}

    @staticmethod
    def _review(scene, box_id: str, status: str) -> None:
        box = scene.get_data("bboxes", ids=[box_id])[0]
        box.review_status = status
        scene.update_data("bboxes", [box])

    def test_a_dataset_whose_entities_hold_no_class_gains_one(self, scene) -> None:
        """nuScenes, a dataset imported with boxes only: entities are bare identifiers until a detection names them."""
        from pixano.schemas import label_field_of

        assert label_field_of(scene.info.entity) is None

        self._detect(scene, ["cat"])

        assert label_field_of(scene.info.entity) == "category"

    def test_each_box_points_to_an_entity_that_names_its_class(self, scene) -> None:
        written = self._detect(scene, ["cat", "dog"])

        assert self._objects(scene) == {written[0]: ("cat", "pending"), written[1]: ("dog", "pending")}

    def test_a_rerun_leaves_no_orphan_entity(self, scene) -> None:
        self._detect(scene, ["cat", "dog", "cow"])

        self._detect(scene, ["horse"])

        assert len(scene.get_data("entities", limit=None)) == 1
        assert list(self._objects(scene).values()) == [("horse", "pending")]

    def test_the_entity_of_a_reviewed_box_stays_with_it(self, scene) -> None:
        first = self._detect(scene, ["cat", "dog"])
        self._review(scene, first[1], "accepted")

        self._detect(scene, [])

        assert self._objects(scene) == {first[1]: ("dog", "accepted")}
        assert [entity.id for entity in scene.get_data("entities", limit=None)] == [first[1]]

    def test_rerunning_is_idempotent(self, scene) -> None:
        first = self._detect(scene, ["cat", "dog"])
        self._review(scene, first[0], "accepted")
        self._detect(scene, ["x", "y"])
        once = self._objects(scene)

        self._detect(scene, ["x", "y"], job_id="job-2")

        assert self._objects(scene) == once
        assert len(scene.get_data("entities", limit=None)) == len(once)

    def test_entities_left_by_a_crash_are_swept_by_the_next_attempt(self, scene) -> None:
        """The stale boxes were deleted, the worker died before
        their entities, and the next attempt, looking in bboxes only, never found them."""
        first = self._detect(scene, ["car", "dog", "cow"])
        scene.delete_data("bboxes", first[1:])

        self._detect(scene, ["car"])

        assert [entity.id for entity in scene.get_data("entities", limit=None)] == [first[0]]

    def test_dropping_the_pending_rows_keeps_what_a_person_accepted(self, scene) -> None:
        """Clearing a kind's previous proposals: what is still pending goes, whatever model wrote it."""
        first = self._detect(scene, ["cat", "dog"])
        self._review(scene, first[0], "accepted")
        writer = JobWriter(lambda: scene, "detection", "job-2", "model", model=ModelIdentity("other"))

        dropped = writer.drop_pending("bboxes", with_entities=True)

        assert dropped == 1
        assert self._objects(scene) == {first[0]: ("cat", "accepted")}
        assert len(scene.get_data("entities", limit=None)) == 1

    def test_dropping_clears_a_model_row_stored_without_a_status(self, scene) -> None:
        """A model's row re-imported from JSONL comes back without a status (the grammar carries
        none). Nobody reviewed it, as the application reads it: left behind, the record would end
        with the old model's boxes and the new one's, all pending."""
        first = self._detect(scene, ["cat", "dog"])
        for box_id in first:
            self._review(scene, box_id, "")
        writer = JobWriter(lambda: scene, "detection", "job-2", "model", model=ModelIdentity("other"))

        assert writer.drop_pending("bboxes", with_entities=True) == len(first)
        assert self._objects(scene) == {}
        assert scene.get_data("entities", limit=None) == []

    @pytest.mark.parametrize("source_type", ["human", "ground_truth"])
    def test_dropping_leaves_a_row_no_model_produced_under_the_kind_name(self, scene, source_type: str) -> None:
        """Not reviewed covers the empty status, which every row no model produced carries too: only
        the source keeps such a row out. Its name is free text, which an import's default source can
        set to the kind's."""
        from pixano.schemas import BBox

        detected = self._detect(scene, ["cat"])
        entity_schema = scene.info.tables["entities"]
        scene.add_data("entities", [entity_schema(id="person-object", record_id="r1", category="person")])
        scene.add_data(
            "bboxes",
            [
                BBox(
                    id="person-box",
                    record_id="r1",
                    view_id="v2",
                    entity_id="person-object",
                    coords=[0.5, 0.5, 0.1, 0.1],
                    format="xywh",
                    is_normalized=True,
                    source_type=source_type,
                    source_name="detection",
                    review_status="",
                )
            ],
        )
        writer = JobWriter(lambda: scene, "detection", "job-2", "model", model=ModelIdentity("other"))

        assert writer.drop_pending("bboxes", with_entities=True) == len(detected)
        assert [box.id for box in scene.get_data("bboxes", limit=None)] == ["person-box"]
        assert [entity.id for entity in scene.get_data("entities", limit=None)] == ["person-object"]

    def test_dropping_leaves_another_kind_alone(self, scene) -> None:
        self._detect(scene, ["cat"])
        writer = JobWriter(lambda: scene, "segmentation", "job-2", "model", model=ModelIdentity("sam"))

        assert writer.drop_pending("bboxes", with_entities=True) == 0
        assert len(self._objects(scene)) == 1

    def test_dropping_many_rows_names_them_in_bounded_batches(self, scene, monkeypatch: pytest.MonkeyPatch) -> None:
        """Clearing a dataset's pending boxes named all of them in one
        filter — hundreds of thousands on a large dataset."""
        import pixano_worker.writer as writer_module

        monkeypatch.setattr(writer_module, "IDS_PER_QUERY", 2)
        self._detect(scene, ["car", "dog", "cow", "cat", "bird"])
        longest: list[int] = []
        real_get, real_delete = scene.get_data, scene.delete_data

        def get_data(table_name: str, ids: list[str] | None = None, **kwargs: Any) -> Any:
            # The identifiers a filter names: those of its lists on an identifier column (id,
            # entity_id, parent_id). The status list of `drop_pending` names statuses, not rows.
            named_lists = re.findall(r"\b\w*id IN \(([^)]*)\)", kwargs.get("where") or "")
            longest.append(len(ids) if ids is not None else sum(names.count("'") // 2 for names in named_lists))
            return real_get(table_name, ids=ids, **kwargs)

        def delete_data(table_name: str, ids: list[str]) -> Any:
            longest.append(len(ids))
            return real_delete(table_name, ids)

        monkeypatch.setattr(scene, "get_data", get_data)
        monkeypatch.setattr(scene, "delete_data", delete_data)
        writer = JobWriter(lambda: scene, "detection", "job-2", "model", model=ModelIdentity("yolo"))

        dropped = writer.drop_pending("bboxes", with_entities=True, covers=lambda _row, _entity: True)

        assert dropped == 5
        assert max(longest) <= 2
        monkeypatch.undo()
        assert scene.get_data("bboxes", limit=None) == [] and scene.get_data("entities", limit=None) == []

    @staticmethod
    def _about_dogs(_box: Any, entity: Any) -> bool:
        return entity is not None and entity.category == "dog"

    def test_a_write_replaces_only_the_rows_it_covers(self, scene) -> None:
        """A detection asked for dogs finds none: the dog it found before goes, the car stays."""
        first = self._detect(scene, ["car", "dog"])

        self._detect(scene, [], covers=self._about_dogs)

        assert self._objects(scene) == {first[0]: ("car", "pending")}

    def test_a_covered_write_keeps_the_ranks_it_does_not_cover(self, scene) -> None:
        """The car keeps its rank, so the new dogs take the ranks around it instead of overwriting it."""
        first = self._detect(scene, ["car", "dog"])

        written = self._detect(scene, ["dog", "dog"], covers=self._about_dogs)

        assert first[0] not in written
        assert self._objects(scene)[first[0]] == ("car", "pending")
        assert len(self._objects(scene)) == 3

    def test_dropping_deletes_only_the_rows_it_covers(self, scene) -> None:
        first = self._detect(scene, ["car", "dog"])
        writer = JobWriter(lambda: scene, "detection", "job-2", "model", model=ModelIdentity("yolo"))

        assert writer.drop_pending("bboxes", with_entities=True, covers=self._about_dogs) == 1
        assert self._objects(scene) == {first[0]: ("car", "pending")}
        assert [entity.id for entity in scene.get_data("entities", limit=None)] == [first[0]]

    def test_one_entity_per_box_is_required(self, scene) -> None:
        writer = JobWriter(lambda: scene, "detection", "job-1", "model", model=ModelIdentity("yolo"))

        with pytest.raises(ValueError, match="1 entities for 0 rows"):
            writer.replace("bboxes", "v1", [], [SimpleNamespace(id="")])

    @staticmethod
    def _person_attaches_a_box(scene, entity_id: str) -> None:
        """Another annotation of the same object, made by a person — on another view here."""
        from pixano.schemas import BBox

        scene.add_data(
            "bboxes",
            [
                BBox(
                    id="person-box",
                    record_id="r1",
                    view_id="v2",
                    entity_id=entity_id,
                    coords=[0.5, 0.5, 0.1, 0.1],
                    format="xywh",
                    is_normalized=True,
                    source_type="human",
                )
            ],
        )

    def _class_of(self, scene, entity_id: str) -> str:
        found = scene.get_data("entities", ids=[entity_id])
        return found[0].category if found else "<missing>"

    def test_an_object_a_person_attached_work_to_keeps_its_class(self, scene) -> None:
        """Without the rule, the rank was reassigned to whatever the model found
        there next, and the person's box silently became a car."""
        first = self._detect(scene, ["car", "dog"])
        self._person_attaches_a_box(scene, first[1])

        self._detect(scene, ["dog", "car"])

        assert self._class_of(scene, first[1]) == "dog"

    def test_an_object_a_person_attached_work_to_outlives_its_detection(self, scene) -> None:
        first = self._detect(scene, ["car", "dog"])
        self._person_attaches_a_box(scene, first[1])

        self._detect(scene, ["car"])

        assert self._class_of(scene, first[1]) == "dog"

    def test_dropping_the_pending_rows_spares_an_object_a_person_attached_work_to(self, scene) -> None:
        first = self._detect(scene, ["car", "dog"])
        self._person_attaches_a_box(scene, first[1])
        writer = JobWriter(lambda: scene, "detection", "job-2", "model", model=ModelIdentity("yolo"))

        assert writer.drop_pending("bboxes", with_entities=True) == 1
        assert self._class_of(scene, first[1]) == "dog"

    # Masks on the detected objects.

    @staticmethod
    def _segment(scene, entity_ids: list[str], model: str = "sam") -> list[str]:
        """What a kind that segments writes: one pending mask per object, naming the object's entity."""
        writer = JobWriter(lambda: scene, "segmentation", "job-seg", "model", model=ModelIdentity(model))
        schema = writer.table_schema("masks")
        masks = [
            schema(
                id="",
                record_id="r1",
                view_id="v1",
                entity_id=entity_id,
                size=MASK_SIZE,
                counts=MASK_COUNTS,
                **writer.provenance(),
            )
            for entity_id in entity_ids
        ]
        return writer.replace("masks", "v1", masks)

    @staticmethod
    def _attach_a_mask(scene, entity_id: str, source_type: str, status: str) -> str:
        """A mask on an object, as a person left it: drawn, or a model's accepted."""
        from pixano.schemas import CompressedRLE

        mask_id = f"attached-mask-of-{entity_id}"
        scene.add_data(
            "masks",
            [
                CompressedRLE(
                    id=mask_id,
                    record_id="r1",
                    view_id="v1",
                    entity_id=entity_id,
                    size=MASK_SIZE,
                    counts=MASK_COUNTS,
                    source_type=source_type,
                    source_name="segmentation",
                    review_status=status,
                )
            ],
        )
        return mask_id

    @staticmethod
    def _masks(scene) -> dict[str, str]:
        """Each mask's object."""
        return {mask.id: mask.entity_id for mask in scene.get_data("masks", limit=None)}

    def test_a_rerun_over_pending_masks_doubles_no_object(self, scene) -> None:
        """Held by its pending mask, an object's rank would stay frozen, and the rerun would write
        its boxes beside the previous ones — two cars and two dogs, all pending."""
        first = self._detect(scene, ["car", "dog"])
        self._segment(scene, first)

        self._detect(scene, ["car", "dog"])

        assert len(scene.get_data("bboxes", limit=None)) == 2
        assert len(scene.get_data("entities", limit=None)) == 2

    def test_the_pending_masks_go_with_the_objects_a_rerun_rewrites(self, scene) -> None:
        """Rewritten in place, rank 0 is now a dog: the car's mask must not stay on it."""
        first = self._detect(scene, ["car", "dog"])
        self._segment(scene, first)

        self._detect(scene, ["dog", "car"])

        assert self._objects(scene) == {first[0]: ("dog", "pending"), first[1]: ("car", "pending")}
        assert self._masks(scene) == {}

    def test_a_shrinking_rerun_leaves_no_mask_naming_a_missing_object(self, scene) -> None:
        first = self._detect(scene, ["car", "dog"])
        self._segment(scene, first)

        self._detect(scene, ["car"])

        entities = {entity.id for entity in scene.get_data("entities", limit=None)}
        assert len(scene.get_data("bboxes", limit=None)) == len(entities) == 1
        assert set(self._masks(scene).values()) <= entities

    # What a person did to an object: a mask drawn by hand, imported as ground truth, or a model's
    # mask accepted.
    PERSONS_MASKS = [
        pytest.param("model", "accepted", id="accepted"),
        pytest.param("human", "", id="human"),
        pytest.param("ground_truth", "", id="ground-truth"),
    ]

    @pytest.mark.parametrize(("source_type", "status"), PERSONS_MASKS)
    def test_only_a_persons_mask_holds_its_object(self, scene, source_type: str, status: str) -> None:
        """The person's object keeps its rank, its class and its mask; the pending mask beside it
        holds nothing, and goes with the object the rerun rewrites."""
        first = self._detect(scene, ["car", "dog"])
        self._segment(scene, [first[0]])
        kept = self._attach_a_mask(scene, first[1], source_type, status)

        self._detect(scene, ["dog", "car"])

        assert self._class_of(scene, first[1]) == "dog"
        assert self._masks(scene) == {kept: first[1]}
        assert len(scene.get_data("bboxes", limit=None)) == 3, "one rank held, two written around it"

    def test_no_mask_is_left_on_an_object_a_crash_rewrote(self, scene, monkeypatch: pytest.MonkeyPatch) -> None:
        """The masks go before their objects change: a worker dying between the two writes leaves
        no car's mask on what is now a dog, and the next attempt finishes the job."""
        first = self._detect(scene, ["car", "dog"])
        self._segment(scene, first)
        real_update = scene.update_data

        def update_data(table_name: str, data: list[Any], *args: Any, **kwargs: Any) -> Any:
            if table_name == "bboxes":
                raise RuntimeError("the worker died")
            return real_update(table_name, data, *args, **kwargs)

        monkeypatch.setattr(scene, "update_data", update_data)
        with pytest.raises(RuntimeError, match="the worker died"):
            self._detect(scene, ["dog"])

        assert self._class_of(scene, first[0]) == "dog", "the object was rewritten before the crash"
        assert self._masks(scene) == {}, "and the car's mask had gone before it"
        monkeypatch.undo()
        self._detect(scene, ["dog"])
        assert self._objects(scene) == {first[0]: ("dog", "pending")}

    @staticmethod
    def _attach_a_row(scene, table_name: str, entity_id: str, **fields: str) -> str:
        """A row of `table_name` naming an object — its parent, for an entity."""
        row_id = f"attached-{table_name}"
        schema = scene.info.tables[table_name]
        if table_name == "entities":
            row = schema(id=row_id, record_id="r1", parent_id=entity_id)
        elif table_name == "masks":
            row = schema(
                id=row_id,
                record_id="r1",
                view_id="v1",
                entity_id=entity_id,
                size=MASK_SIZE,
                counts=MASK_COUNTS,
                **fields,
            )
        else:
            row = schema(id=row_id, record_id="r1", entity_id=entity_id, **fields)
        scene.add_data(table_name, [row])
        return row_id

    # Rows no job of this kind wrote, naming a detected object, each decided and pinned here. A
    # person's work holds the object: a row no model produced — a dynamic state imported or edited
    # with no source among them — or a child object.
    PERSONS_WORK = [
        pytest.param("tracklets", {"source_type": "human"}, id="person's tracklet"),
        pytest.param("entity_dynamic_states", {}, id="dynamic state with no source"),
        pytest.param("entity_dynamic_states", {"source_type": "human"}, id="person's dynamic state"),
        pytest.param("entities", {}, id="child object"),
    ]

    # A model's row nobody reviewed goes with the object: it reads as pending everywhere
    # (`NOT_REVIEWED_STATUSES`), and left behind it would name whatever the rank holds next, or an
    # entity that is gone. Tracklets and dynamic states are never reviewed, so a model's never holds.
    MODELS_UNREVIEWED_ROWS = [
        pytest.param(
            "masks",
            {
                "source_type": "model",
                "source_name": "smart-segmentation",
                "source_metadata": '{"provider_name": "sam"}',
            },
            id="legacy smart-tracking mask",
        ),
        pytest.param(
            "masks", {"source_type": "model", "source_name": "segmentation"}, id="model mask re-imported from JSONL"
        ),
        pytest.param("tracklets", {"source_type": "model", "source_name": "tracking"}, id="model tracklet"),
        pytest.param(
            "entity_dynamic_states", {"source_type": "model", "source_name": "tracking"}, id="model dynamic state"
        ),
    ]

    @pytest.mark.parametrize(("table_name", "fields"), PERSONS_WORK)
    def test_a_persons_work_holds_the_object(self, scene, table_name: str, fields: dict[str, str]) -> None:
        first = self._detect(scene, ["car", "dog"])
        attached = self._attach_a_row(scene, table_name, first[1], **fields)

        self._detect(scene, ["car"])

        assert self._class_of(scene, first[1]) == "dog"
        assert attached in {row.id for row in scene.get_data(table_name, limit=None)}

    @pytest.mark.parametrize(("table_name", "fields"), MODELS_UNREVIEWED_ROWS)
    def test_a_models_unreviewed_row_goes_with_the_object(
        self, scene, table_name: str, fields: dict[str, str]
    ) -> None:
        first = self._detect(scene, ["car", "dog"])
        attached = self._attach_a_row(scene, table_name, first[1], **fields)

        self._detect(scene, ["car"])

        assert self._objects(scene) == {first[0]: ("car", "pending")}
        assert attached not in {row.id for row in scene.get_data(table_name, limit=None)}

    def test_dropping_the_pending_rows_takes_their_pending_masks_along(self, scene) -> None:
        """Held by their pending masks, the boxes would stay, and clearing would clear nothing."""
        first = self._detect(scene, ["car", "dog"])
        self._segment(scene, first)
        writer = JobWriter(lambda: scene, "detection", "job-2", "model", model=ModelIdentity("other"))

        assert writer.drop_pending("bboxes", with_entities=True) == len(first)
        assert self._objects(scene) == {}
        assert scene.get_data("entities", limit=None) == []
        assert self._masks(scene) == {}

    @pytest.mark.parametrize(("source_type", "status"), PERSONS_MASKS)
    def test_dropping_spares_an_object_a_person_left_a_mask_on(self, scene, source_type: str, status: str) -> None:
        first = self._detect(scene, ["car", "dog"])
        self._segment(scene, [first[0]])
        kept = self._attach_a_mask(scene, first[1], source_type, status)
        writer = JobWriter(lambda: scene, "detection", "job-2", "model", model=ModelIdentity("yolo"))

        assert writer.drop_pending("bboxes", with_entities=True) == 1
        assert self._objects(scene) == {first[1]: ("dog", "pending")}
        assert self._masks(scene) == {kept: first[1]}

    def test_clearing_the_pending_masks_leaves_the_objects_they_name(self, scene) -> None:
        """A kind whose masks own no object clears them without the objects: the objects and their
        boxes stay, as does a mask a person accepted — whatever model wrote the pending ones."""
        first = self._detect(scene, ["car", "dog"])
        self._segment(scene, first, model="sam-tiny")
        self._segment(scene, first, model="sam-small")
        kept = self._attach_a_mask(scene, first[1], "model", "accepted")
        writer = JobWriter(lambda: scene, "segmentation", "job-2", "model", model=ModelIdentity("sam-tiny"))

        assert writer.drop_pending("masks", with_entities=False) == 2 * len(first)
        assert self._masks(scene) == {kept: first[1]}
        assert self._objects(scene) == {first[0]: ("car", "pending"), first[1]: ("dog", "pending")}

    def test_tells_which_objects_carry_a_persons_work(self, scene) -> None:
        """What a kind asks before proposing an object again. A pending mask is
        not a person's work, and neither is the object's own box, accepted or not: that one is the
        kind's own to judge."""
        first = self._detect(scene, ["car", "dog", "cow", "cat"])
        self._segment(scene, [first[0]])
        self._attach_a_mask(scene, first[1], "model", "accepted")
        self._person_attaches_a_box(scene, first[2])
        self._review(scene, first[3], "accepted")
        writer = JobWriter(lambda: scene, "detection", "job-2", "model", model=ModelIdentity("yolo"))

        assert writer.entities_with_a_persons_work(first, own_table="bboxes") == {first[1], first[2]}


class TestAnnotationTableForAKind:
    """A kind writes masks into a dataset built without them, holding boxes only."""

    @pytest.fixture
    def path(self, tmp_path):
        from pixano.datasets import Dataset
        from pixano.datasets.dataset_info import DatasetInfo
        from pixano.schemas import BBox, Entity, Image, Record

        dataset = Dataset.create(
            tmp_path / "boxes-only",
            DatasetInfo(
                id="boxes-only", name="Boxes only", record=Record, entity=Entity, bbox=BBox, views={"image": Image}
            ),
        )
        dataset.add_records({"records": [Record(id="r1")]})
        dataset.add_data("entities", [Entity(id="e1", record_id="r1")])
        return dataset.path

    @staticmethod
    def _writer(dataset) -> JobWriter:
        return JobWriter(lambda: dataset, "segmentation", "job-1", "model", model=ModelIdentity("sam"))

    @staticmethod
    def _add_a_mask(dataset) -> None:
        from pixano.schemas import CompressedRLE

        mask = CompressedRLE(
            id="m1",
            record_id="r1",
            view_id="v1",
            entity_id="e1",
            size=MASK_SIZE,
            counts=MASK_COUNTS,
            source_type="human",
        )
        dataset.add_data("masks", [mask])

    def test_a_dataset_without_the_slot_gains_its_table(self, path) -> None:
        from pixano.datasets import Dataset

        dataset = Dataset(path)

        assert self._writer(dataset).ensure_table("mask") == "masks"

        assert "masks" in dataset.info.tables
        reopened = Dataset(path)
        assert reopened.info.mask is not None and "masks" in reopened.info.tables

    def test_ensuring_again_changes_nothing(self, path) -> None:
        """Called by `prepare` and again by every write: the table and what it holds stay as they are."""
        from pixano.datasets import Dataset

        dataset = Dataset(path)
        writer = self._writer(dataset)
        writer.ensure_table("mask")
        self._add_a_mask(dataset)
        info_written = (path / "info.json").stat().st_mtime_ns

        assert writer.ensure_table("mask") == "masks"

        assert [mask.id for mask in dataset.get_data("masks", limit=None)] == ["m1"]
        assert (path / "info.json").stat().st_mtime_ns == info_written

    def test_a_worker_whose_dataset_predates_the_table_finds_it(self, path) -> None:
        """The worker caches its dataset; the API, or another worker, created the table since."""
        from pixano.datasets import Dataset

        stale = Dataset(path)
        elsewhere = Dataset(path)
        elsewhere.ensure_annotation_table("mask")
        self._add_a_mask(elsewhere)

        assert self._writer(stale).ensure_table("mask") == "masks"

        assert [mask.id for mask in stale.get_data("masks", limit=None)] == ["m1"]

    def test_a_slot_that_holds_no_annotations_is_refused(self, path) -> None:
        from pixano.datasets import Dataset

        with pytest.raises(ValueError, match="entity"):
            self._writer(Dataset(path)).ensure_table("entity")

    def test_a_table_already_there_is_found_while_someone_else_writes_the_dataset(self, path, writing) -> None:
        """Every job of a kind that writes masks ensures its table at planning. Taking the
        dataset's write lock for that, which never waits, refused the job whenever a person was
        saving or another job's chunk writing — and marked the dataset modified for nothing."""
        from pixano.datasets import Dataset
        from pixano.datasets.locking import mutation_token

        Dataset(path).ensure_annotation_table("mask")
        dataset = Dataset(path)
        modified = mutation_token(path)

        with writing(path):
            assert self._writer(dataset).ensure_table("mask") == "masks"

        assert mutation_token(path) == modified

    def test_creating_the_table_waits_for_no_one(self, path, writing) -> None:
        """Only creating the table takes the dataset's lock, and that lock does not wait: met
        busy, the dataset says so — the runner plans the job again later rather than failing it."""
        from pixano.datasets import Dataset
        from pixano.datasets.utils.errors import DatasetBusyError

        dataset = Dataset(path)

        with writing(path), pytest.raises(DatasetBusyError):
            self._writer(dataset).ensure_table("mask")

        assert "masks" not in Dataset(path).info.tables


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
        # A fresh count: a writer without a dataset identifier counts under its address, which an
        # earlier test's writer, freed, may have used for the same table.
        monkeypatch.setattr(writer_module, "_writes_since_compaction", defaultdict(int))
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
