# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The suite every job kind must pass.

It is parametrised on the registry, not on a hand-written list: registering a new kind submits
it automatically, and that is the only way a frozen contract stays frozen. A kind that failed
here would break the engine in production, not only its own results.

The parameter examples live in `CONTRACT_EXAMPLES`. A kind without an example fails the suite
deliberately: adding a kind without saying how to exercise it would amount to exempting it
from the contract.
"""

import hashlib
import json
import re
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from pixano_worker.kinds import JobParams, default_registry
from pixano_worker.kinds.base import JobKind
from pixano_worker.media import MediaResolver
from pixano_worker.reader import JobReader
from pixano_worker.writer import JobWriter
from pydantic import create_model

from pixano.schemas import BBox, Entity, Image, Record


#: The provenance vocabulary of the Pixano schemas. Writing anything else is refused at write time.
SOURCE_TYPES = {"model", "human", "ground_truth", "other"}

#: What it takes to exercise each kind: valid parameters, and a table to write into.
CONTRACT_EXAMPLES: dict[str, dict[str, Any]] = {
    "fake": {"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0, "write_to": "toy"},
    # The contract's dataset is empty, so planning produces no chunk and nothing is called on
    # the inference — which is the point: the contract exercises the shape, not the model. The
    # real path is checked end to end in the lot's demonstration.
    "embeddings": {"model": "clip", "chunk_size": 8},
    "detection": {"model": "yolo", "chunk_size": 8},
    "label": {
        "record_ids": [f"rec-{n}" for n in range(25)],
        "label": "to-review",
        "chunk_size": 10,
        "write_to": "toy",
    },
}

#: The kinds that know how to write nothing, and how to ask them to.
QUIET_EXAMPLES: dict[str, dict[str, Any]] = {
    "fake": {**CONTRACT_EXAMPLES["fake"], "write_to": None},
    "label": {**CONTRACT_EXAMPLES["label"], "write_to": None},
}

REGISTRY = default_registry(demo_kinds=True)


def _matching(rows: dict[str, Any], ids: list[str] | None, where: str | None) -> list[Any]:
    """The reads the writers make: by identifiers, by the prefix filter of a cleanup, or by a
    list of values of one field — a detection's look at the boxes already on a medium."""
    if ids is not None:
        return [rows[i] for i in ids if i in rows]
    prefix = re.fullmatch(r"id LIKE '([^']*)%'", where or "")
    if prefix is not None:
        return [row for row_id, row in rows.items() if row_id.startswith(prefix.group(1))]
    among = re.fullmatch(r"(\w+) IN \((.*)\)", where or "")
    assert among is not None, f"unexpected filter in a test double: {where!r}"
    values = set(re.findall(r"'([^']*)'", among.group(2)))
    return [row for row in rows.values() if getattr(row, among.group(1)) in values]


class _Target:
    """A write target that behaves like LanceDB on the three operations used.

    One store per table: a detected box and the object it names share an identifier.
    """

    def __init__(self) -> None:
        self.compactions: list[str] = []
        self.tables: dict[str, dict[str, Any]] = {}
        self._embeddings_ready = False
        self.info = SimpleNamespace(tables={"bboxes": BBox, "entities": Entity}, entity=Entity)

    @property
    def rows(self) -> dict[str, Any]:
        """Every row written, whatever its table."""
        return {f"{table}/{row_id}": row for table, rows in self.tables.items() for row_id, row in rows.items()}

    def update_data(self, table_name: str, data: list[Any]) -> None:
        for row in data:
            self.tables.setdefault(table_name, {})[row.id] = row

    def delete_data(self, table_name: str, ids: list[str]) -> None:
        for row_id in ids:
            self.tables.get(table_name, {}).pop(row_id, None)

    def get_data(self, table_name: str, ids: list[str] | None = None, *, where: str | None = None) -> list[Any]:
        return _matching(self.tables.get(table_name, {}), ids, where)

    def ensure_entity_text_field(self, name: str) -> None:
        self.info.entity = create_model("ContractEntity", __base__=Entity, **{name: (str, "")})
        self.info.tables["entities"] = self.info.entity

    def open_table(self, table_name: str) -> Any:
        self.compactions.append(table_name)
        return SimpleNamespace(optimize=lambda **_kwargs: None)

    def has_record_embeddings(self) -> bool:
        return self._embeddings_ready

    def create_record_embedding_table(self, dim: int, model_id: str) -> None:
        self._embeddings_ready = True
        self.info.tables["embeddings"] = _Vector
        self._space: dict[str, Any] | None = {"model_id": model_id, "dim": dim}

    def drop_record_embeddings(self) -> None:
        self._embeddings_ready = False
        self.info.tables.pop("embeddings", None)
        self._space = None

    def record_embedding_space(self) -> dict[str, Any] | None:
        return getattr(self, "_space", None)

    def fingerprint(self) -> str:
        material = sorted(
            (row_id, getattr(row, "record_id", ""), repr([getattr(row, field, None) for field in _CONTENT]))
            for row_id, row in self.rows.items()
        )
        return hashlib.sha256(repr(material).encode()).hexdigest()


#: The fields that say what a row holds, whatever the kind that wrote it.
_CONTENT = ("labels", "vector", "coords", "entity_id", "category")


def _params(kind: JobKind) -> JobParams:
    if kind.name not in CONTRACT_EXAMPLES:
        pytest.fail(
            f"the kind '{kind.name}' has no example in CONTRACT_EXAMPLES — "
            "a kind without an example escapes the contract"
        )
    return kind.validate_params(CONTRACT_EXAMPLES[kind.name])


#: The dataset the contract sees. Non-empty, because a data-driven kind produces nothing on an
#: empty dataset — and the contract must exercise those kinds too.
CONTRACT_RECORDS = 25


class _Vector:
    """An embedding row: no provenance, only a vector.

    This absence is not an oversight of the Pixano schema — an embedding is not an annotation,
    nobody reviews it, and the model that produced it is described once for the whole table.
    """

    def __init__(self, id: str, record_id: str, vector: Any, view_id: str = "") -> None:
        self.id, self.record_id, self.view_id, self.vector = id, record_id, view_id, vector


#: The side of every image of the contract's dataset, in pixels.
IMAGE_SIDE = 100


class _Row:
    def __init__(self, row_id: str, record_id: str = "", uri: str = "") -> None:
        self.id = row_id
        self.record_id = record_id
        self.uri = uri
        self.width = self.height = IMAGE_SIDE


class _Source:
    """A dataset of twenty-five records, each with an image designated by path.

    By path and not by bytes, so that the contract does not have to simulate images: what the
    resolver does with them is exercised elsewhere.
    """

    # The real schemas: the reader finds a dataset's media by looking at them.
    info = SimpleNamespace(tables={"records": Record, "images": Image, "bboxes": BBox, "entities": Entity})

    def count_rows_where(self, table_name: str, where: str | None = None) -> int:
        return CONTRACT_RECORDS

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
        if table_name == "images":
            if ids is None:
                end = CONTRACT_RECORDS if limit is None else min(skip + limit, CONTRACT_RECORDS)
                ids = [f"img-{n}" for n in range(skip, end)]
            return [_Row(i, record_id=f"rec-{i.removeprefix('img-')}", uri=f"/medias/{i}.jpg") for i in ids]
        end = CONTRACT_RECORDS if limit is None else min(skip + limit, CONTRACT_RECORDS)
        return [_Row(f"rec-{n}") for n in range(skip, end)]

    def get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str] | None:
        return None


def _reader() -> JobReader:
    return JobReader(lambda: _Source(), MediaResolver("/medias", "/medias"))


def _writer(kind: JobKind, target: _Target, job_id: str) -> JobWriter:
    params = _params(kind)
    return JobWriter(
        lambda: target,
        kind.name,
        job_id,
        kind.source_type,
        params=kind.provenance_params(params),
        model=kind.model_identity(params),
    )


def _execute(kind: JobKind, target: _Target, job_id: str, prepare_times: int = 1) -> None:
    """A whole job, as the engine runs it: split, prepare, then every chunk."""
    params = _params(kind)
    chunks = list(kind.plan(_reader(), params))
    for _ in range(prepare_times):
        kind.prepare(_writer(kind, target, job_id), params)
    for chunk in chunks:
        kind.write(
            _writer(kind, target, job_id), kind.process(_reader(), chunk.payload, params), chunk.payload, params
        )


#: Width of the vectors the simulated inference returns.
FAKE_DIM = 8


@pytest.fixture(autouse=True)
def _offline_inference(monkeypatch: pytest.MonkeyPatch) -> None:
    """Answer in place of the inference.

    The contract exercises the shape of a kind, not the quality of a model: it must run without
    a server, in one second, on anybody's machine. What the real model produces is checked end
    to end elsewhere.
    """

    class _Client:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            pass

        def __enter__(self) -> "_Client":
            return self

        def __exit__(self, *_exc: Any) -> None:
            return None

        def list_models(self) -> list[Any]:
            return [
                SimpleNamespace(name="clip", model_path="MobileCLIP2-S2", capability="embedding"),
                SimpleNamespace(name="yolo", model_path="yolo26s.pt", capability="detection"),
            ]

        def detection(self, request: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(data=SimpleNamespace(boxes=[[10, 20, 50, 60]], scores=[0.8], classes=["thing"]))

        def embedding(self, request: Any, **_kwargs: Any) -> Any:
            count = len(request.image) if isinstance(request.image, list) else 1
            vectors = np.full((count, FAKE_DIM), 0.1, dtype=np.float32)
            return SimpleNamespace(data=SimpleNamespace(embeddings=SimpleNamespace(to_numpy=lambda: vectors)))

    monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", _Client)


@pytest.fixture(params=REGISTRY.names())
def kind(request: pytest.FixtureRequest) -> JobKind:
    """Each registered kind, in turn."""
    registered = REGISTRY.get(request.param)
    assert registered is not None
    return registered


class TestDeclaration:
    def test_it_has_a_name(self, kind: JobKind) -> None:
        assert kind.name

    def test_its_parameters_forbid_unknown_fields(self, kind: JobKind) -> None:
        """This is what lets the application refuse a typo at submission.

        Without this property, a misspelled parameter passes validation and gets silently
        ignored: the user gets a job that runs with other settings than the ones they believe
        they set.
        """
        assert kind.params_schema()["additionalProperties"] is False

    def test_it_declares_a_provenance_the_schemas_accept(self, kind: JobKind) -> None:
        """A kind that declared anything else would see its writes refused at execution."""
        assert kind.source_type in SOURCE_TYPES

    def test_its_parameter_example_is_valid(self, kind: JobKind) -> None:
        assert isinstance(_params(kind), JobParams)

    def test_a_model_parameter_names_a_task_the_application_knows(self, kind: JobKind) -> None:
        """Independent review of lot 2: the form sends the marker to the application, which
        refuses a pixano-inference capability name where it differs — `segmentation` for
        `image_mask_generation` — and the field fell back to typing without a word."""
        from pixano_worker.kinds import MODEL_TASK_MARKER

        from pixano.inference.types import InferenceTask

        for name, field in kind.params_schema()["properties"].items():
            if MODEL_TASK_MARKER in field:
                assert field[MODEL_TASK_MARKER] in {task.value for task in InferenceTask}, name


class TestProvenance:
    """Every row a kind writes must say, by itself, how it was produced."""

    def test_every_written_row_carries_the_kind_and_its_parameters(self, kind: JobKind) -> None:
        target = _Target()
        _execute(kind, target, "job-1")
        # Embedding rows carry no provenance fields: the model lives in the dataset's sidecar
        # as long as one table holds one model (step 2 design, question 4).
        with_provenance = [row for row in target.rows.values() if hasattr(row, "source_metadata")]
        if not with_provenance:
            pytest.skip(f"'{kind.name}' writes no row that carries provenance with its example")

        for row in with_provenance:
            metadata = json.loads(row.source_metadata)
            assert row.source_name == kind.name
            assert metadata["kind"] == kind.name
            assert metadata["job_id"] == "job-1"
            assert set(metadata["params"]) == set(_params(kind).model_dump()) - kind.params_not_in_provenance

    def test_a_kind_that_runs_a_model_names_it(self, kind: JobKind) -> None:
        params = _params(kind)
        identity = kind.model_identity(params)
        if identity is None:
            assert kind.source_type != "model", "a kind producing model output must say which model"
            return

        assert identity.name == getattr(params, "model", identity.name)


class TestPreparation:
    """The `prepare` hook: nothing by default, and never two different states for two calls."""

    def test_preparing_with_default_parameters_destroys_nothing(self, kind: JobKind) -> None:
        target = _Target()
        _execute(kind, target, "job-1")
        before = target.fingerprint()

        kind.prepare(_writer(kind, target, "job-2"), _params(kind))

        assert target.fingerprint() == before

    def test_preparing_twice_is_the_same_as_once(self, kind: JobKind) -> None:
        """A planner that died after `prepare` lets the next one redo everything."""
        once, twice = _Target(), _Target()
        _execute(kind, once, "job-1")
        _execute(kind, twice, "job-1", prepare_times=2)

        assert twice.fingerprint() == once.fingerprint()


class TestPlanning:
    def test_it_produces_work(self, kind: JobKind) -> None:
        assert list(kind.plan(_reader(), _params(kind)))

    def test_every_chunk_carries_at_least_one_task(self, kind: JobKind) -> None:
        """An empty chunk would block progress: it would consume a turn without advancing."""
        assert all(chunk.task_count > 0 for chunk in kind.plan(_reader(), _params(kind)))

    def test_planning_twice_gives_the_same_work(self, kind: JobKind) -> None:
        """Planning must be reproducible: a job replanned after an outage must not describe
        work different from the one already partly executed."""
        first = [(c.payload, c.task_count) for c in kind.plan(_reader(), _params(kind))]
        second = [(c.payload, c.task_count) for c in kind.plan(_reader(), _params(kind))]

        assert first == second

    def test_the_payload_is_an_object(self, kind: JobKind) -> None:
        """The schema constrains payloads to objects; a scalar would be refused by the database."""
        assert all(isinstance(chunk.payload, dict) for chunk in kind.plan(_reader(), _params(kind)))


class TestExecution:
    def test_it_processes_every_chunk(self, kind: JobKind) -> None:
        params = _params(kind)

        for chunk in kind.plan(_reader(), params):
            kind.process(_reader(), chunk.payload, params)

    def test_its_outcome_accounts_for_every_task(self, kind: JobKind) -> None:
        """The engine refuses an outcome that does not add up; better to learn it here than in production."""
        params = _params(kind)

        for chunk in kind.plan(_reader(), params):
            result = kind.process(_reader(), chunk.payload, params)
            assert kind.outcome(result, chunk.payload, chunk.task_count).total == chunk.task_count

    def test_writing_twice_changes_nothing(self, kind: JobKind) -> None:
        """Idempotence, required of all: results go to LanceDB and progress to PostgreSQL,
        so a worker that dies between the two redoes the chunk."""
        target = _Target()
        _execute(kind, target, "job-1")
        first = (len(target.rows), target.fingerprint())

        _execute(kind, target, "job-1")

        assert (len(target.rows), target.fingerprint()) == first

    def test_a_resubmission_does_not_duplicate(self, kind: JobKind) -> None:
        target = _Target()
        _execute(kind, target, "job-1")
        first = (len(target.rows), target.fingerprint())

        _execute(kind, target, "job-2")

        assert (len(target.rows), target.fingerprint()) == first

    def test_every_annotation_says_where_it_came_from(self, kind: JobKind) -> None:
        """Provenance is required of annotations, not of every output.

        An embedding carries none, and that is consistent: nobody reviews it, and the model
        that produced it is described once for the whole table rather than on every row. The
        contract therefore checks that what *can* carry a provenance carries a correct one.
        """
        target = _Target()

        _execute(kind, target, "job-1")

        assert target.rows, "a kind that writes must write something with this example"
        for row in target.rows.values():
            if not hasattr(row, "source_name"):
                continue
            assert row.source_name == kind.name
            assert row.source_type == kind.source_type

    def test_a_kind_can_be_told_to_write_nothing(self, kind: JobKind) -> None:
        """Some kinds know how to stay quiet — a statistic, a dry run. Those that do not are
        ignored here: it is a capability, not an obligation of the contract."""
        if kind.name not in QUIET_EXAMPLES:
            pytest.skip(f"'{kind.name}' has no quiet mode")
        params = kind.validate_params(QUIET_EXAMPLES[kind.name])
        target = _Target()

        for chunk in kind.plan(_reader(), params):
            writer = JobWriter(lambda: target, kind.name, "job-1", kind.source_type)
            kind.write(writer, kind.process(_reader(), chunk.payload, params), chunk.payload, params)

        assert target.rows == {}


class TestRegistry:
    def test_every_registered_kind_is_covered(self) -> None:
        """The contract's safeguard: a kind added without an example fails the suite."""
        assert set(REGISTRY.names()) <= set(CONTRACT_EXAMPLES)

    def test_two_kinds_cannot_share_a_name(self) -> None:
        from pixano_worker.kinds import FakeKind, Registry

        registry = Registry()
        registry.register(FakeKind())

        with pytest.raises(ValueError, match="already registered"):
            registry.register(FakeKind())


class TestProvenanceParameters:
    """What the provenance records of a job's parameters."""

    def test_a_selection_is_not_copied_into_every_row(self) -> None:
        """Review of step 2, lot 0: ten thousand ids made 260 kB of metadata on each labelled row."""
        from pixano_worker.kinds import LabelKind

        kind = LabelKind()
        params = kind.validate_params({"record_ids": [f"r{n}" for n in range(10_000)], "label": "cat"})

        assert "record_ids" not in kind.provenance_params(params)

    def test_a_parameter_json_cannot_hold_is_recorded_as_json(self) -> None:
        """A path, an enum or a date must not fail the chunk at write time."""
        from datetime import date
        from pathlib import Path

        from pixano_worker.kinds import FakeKind, JobParams

        class _Params(JobParams):
            where: Path
            since: date

        recorded = FakeKind.provenance_params(FakeKind(), _Params(where=Path("/a"), since=date(2026, 1, 2)))

        assert json.dumps(recorded) == '{"where": "/a", "since": "2026-01-02"}'
