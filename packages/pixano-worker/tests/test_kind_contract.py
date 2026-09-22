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
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from pixano_worker.kinds import JobParams, default_registry
from pixano_worker.kinds.base import JobKind
from pixano_worker.media import MediaResolver
from pixano_worker.reader import JobReader
from pixano_worker.writer import JobWriter


#: The provenance vocabulary of the Pixano schemas. Writing anything else is refused at write time.
SOURCE_TYPES = {"model", "human", "ground_truth", "other"}

#: What it takes to exercise each kind: valid parameters, and a table to write into.
CONTRACT_EXAMPLES: dict[str, dict[str, Any]] = {
    "fake": {"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0, "write_to": "toy"},
    # The contract's dataset is empty, so planning produces no chunk and nothing is called on
    # the inference — which is the point: the contract exercises the shape, not the model. The
    # real path is checked end to end in the lot's demonstration.
    "embeddings": {"model": "clip", "chunk_size": 8},
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


class _Target:
    """A write target that behaves like LanceDB on the three operations used."""

    def __init__(self) -> None:
        self.compactions: list[str] = []
        self.rows: dict[str, Any] = {}
        self._embeddings_ready = False
        self.info = SimpleNamespace(tables={})

    def update_data(self, table_name: str, data: list[Any]) -> None:
        for row in data:
            self.rows[row.id] = row

    def delete_data(self, table_name: str, ids: list[str]) -> None:
        for row_id in ids:
            self.rows.pop(row_id, None)

    def get_data(self, table_name: str, ids: list[str]) -> list[Any]:
        return [self.rows[i] for i in ids if i in self.rows]

    def open_table(self, table_name: str) -> Any:
        self.compactions.append(table_name)
        return SimpleNamespace(optimize=lambda **_kwargs: None)

    def has_record_embeddings(self) -> bool:
        return self._embeddings_ready

    def create_record_embedding_table(self, dim: int, model_id: str) -> None:
        self._embeddings_ready = True
        self.info.tables["embeddings"] = _Vector
        self._space = {"model_id": model_id, "dim": dim}

    def record_embedding_space(self) -> dict[str, Any] | None:
        return getattr(self, "_space", None)

    def fingerprint(self) -> str:
        material = sorted(
            (row_id, getattr(row, "record_id", ""), repr(getattr(row, "labels", getattr(row, "vector", None))))
            for row_id, row in self.rows.items()
        )
        return hashlib.sha256(repr(material).encode()).hexdigest()


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

    def __init__(self, id: str, record_id: str, vector: Any) -> None:
        self.id, self.record_id, self.vector = id, record_id, vector


class _Row:
    def __init__(self, row_id: str, record_id: str = "", uri: str = "") -> None:
        self.id = row_id
        self.record_id = record_id
        self.uri = uri


class _Source:
    """A dataset of twenty-five records, each with an image designated by path.

    By path and not by bytes, so that the contract does not have to simulate images: what the
    resolver does with them is exercised elsewhere.
    """

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
            return [_Row(f"img-{i}", record_id=i, uri=f"/medias/{i}.jpg") for i in record_ids or []]
        end = CONTRACT_RECORDS if limit is None else min(skip + limit, CONTRACT_RECORDS)
        return [_Row(f"rec-{n}") for n in range(skip, end)]

    def get_view_binary(self, table_name: str, row_id: str) -> tuple[bytes, str] | None:
        return None


def _reader() -> JobReader:
    return JobReader(lambda: _Source(), MediaResolver("/medias", "/medias"))


def _writer(kind: JobKind, target: _Target, job_id: str) -> JobWriter:
    return JobWriter(lambda: target, kind.name, job_id, kind.source_type)


def _execute(kind: JobKind, target: _Target, job_id: str, prepare_times: int = 1) -> None:
    """A whole job, as the engine runs it: prepare, split, then every chunk."""
    params = _params(kind)
    for _ in range(prepare_times):
        kind.prepare(_writer(kind, target, job_id), params)
    for chunk in kind.plan(_reader(), params):
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

        def embedding(self, request: Any, **_kwargs: Any) -> Any:
            count = len(request.image) if isinstance(request.image, list) else 1
            vectors = np.full((count, FAKE_DIM), 0.1, dtype=np.float32)
            return SimpleNamespace(data=SimpleNamespace(embeddings=SimpleNamespace(to_numpy=lambda: vectors)))

    monkeypatch.setattr("pixano_worker.kinds.embeddings.SyncPixanoInferenceClient", _Client)


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
