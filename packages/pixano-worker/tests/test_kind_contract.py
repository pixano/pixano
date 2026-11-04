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
from the contract. Its destructive parameters are found the same way, from the `CONFIRM_MARKER`
its schema carries, and each is exercised set.
"""

import json
import re
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from pixano_worker.kinds import CONFIRM_MARKER, JobParams, default_registry
from pixano_worker.kinds.base import Chunk, JobKind
from pixano_worker.media import MediaResolver
from pixano_worker.reader import JobReader
from pixano_worker.writer import JobWriter
from pydantic import BaseModel

from pixano.schemas import Image, Record


#: The provenance vocabulary of the Pixano schemas. Writing anything else is refused at write time.
SOURCE_TYPES = {"model", "human", "ground_truth", "other"}

#: What it takes to exercise each kind: valid parameters, and a table to write into.
CONTRACT_EXAMPLES: dict[str, dict[str, Any]] = {
    "fake": {"task_count": 40, "chunk_size": 10, "seconds_per_task": 0.0, "write_to": "toy"},
    # The contract's dataset is empty, so planning produces no chunk and nothing is called on
    # the inference — which is the point: the contract exercises the shape, not the model. The
    # real path is checked end to end on the stack, in the demo (docs/demo-etape1.md).
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


def _registered(name: str) -> JobKind:
    """The registered kind bearing this name."""
    kind = REGISTRY.get(name)
    assert kind is not None, f"no kind named '{name}' is registered"
    return kind


def _confirmed_parameters(kind: JobKind) -> list[str]:
    """The parameters that destroy something when set: those the submission form asks to confirm."""
    return [name for name, field in kind.params_schema()["properties"].items() if CONFIRM_MARKER in field]


#: Every registered kind's destructive parameters, as (kind, parameter). Read from the schemas,
#: not listed by hand: a new kind's, or a kind's new one, is checked without being named here.
CONFIRMED = [(name, parameter) for name in REGISTRY.names() for parameter in _confirmed_parameters(_registered(name))]


class _Target:
    """A write target that behaves like LanceDB on the three operations used.

    One store per table, as in LanceDB: a dropped table takes its rows with it, and the suite
    compares every row of every table.
    """

    def __init__(self) -> None:
        self.compactions: list[str] = []
        self.tables: dict[str, dict[str, Any]] = {}
        self._embeddings_ready = False
        self.info = SimpleNamespace(tables={})

    @property
    def rows(self) -> dict[str, Any]:
        """Every row a kind wrote, whatever its table."""
        return {f"{table}/{row_id}": row for table, rows in self.tables.items() for row_id, row in rows.items()}

    def snapshot(self) -> list[tuple[str, str, str]]:
        """What the dataset holds: every row of every table, by content.

        A list rather than a digest, so that a failed comparison names the rows that differ.
        """
        return sorted(
            (table, row_id, _content(row)) for table, rows in self.tables.items() for row_id, row in rows.items()
        )

    def update_data(self, table_name: str, data: list[Any]) -> None:
        for row in data:
            self.tables.setdefault(table_name, {})[row.id] = row

    def delete_data(self, table_name: str, ids: list[str]) -> None:
        for row_id in ids:
            self.tables.get(table_name, {}).pop(row_id, None)

    def get_data(self, table_name: str, ids: list[str] | None = None, *, where: str | None = None) -> list[Any]:
        """By identifiers, or by the prefix filter of a cleanup."""
        rows = self.tables.get(table_name, {})
        if ids is not None:
            return [rows[i] for i in ids if i in rows]
        prefix = re.fullmatch(r"id LIKE '([^']*)%'", where or "")
        assert prefix is not None, f"unexpected filter in a test double: {where!r}"
        return [row for row_id, row in rows.items() if row_id.startswith(prefix.group(1))]

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
        # The vectors go with their table, as in LanceDB. Kept, they would let a kind that drops
        # them with its default parameters pass for one that destroys nothing.
        self.tables.pop(JobWriter.EMBEDDING_TABLE, None)

    def record_embedding_space(self) -> dict[str, Any] | None:
        return getattr(self, "_space", None)


#: The fields that change between two runs of the same work without changing what a row holds:
#: the run that wrote it, in its provenance, and when. Every other field counts, so that a rerun
#: changing a score or a label shows, with no list of fields to keep up to date.
_RUN_FIELDS = frozenset({"source_metadata", "created_at", "updated_at"})


def _content(row: Any) -> str:
    """What a row holds: every field it carries but those of `_RUN_FIELDS`."""
    fields = row.model_dump() if isinstance(row, BaseModel) else vars(row)
    return repr(sorted((name, value) for name, value in fields.items() if name not in _RUN_FIELDS))


def _params(kind: JobKind, **overrides: Any) -> JobParams:
    """The kind's example from `CONTRACT_EXAMPLES`, validated, with `overrides` set over it."""
    if kind.name not in CONTRACT_EXAMPLES:
        pytest.fail(
            f"the kind '{kind.name}' has no example in CONTRACT_EXAMPLES — "
            "a kind without an example escapes the contract"
        )
    return kind.validate_params({**CONTRACT_EXAMPLES[kind.name], **overrides})


def _confirmed(kind: JobKind, parameter: str) -> JobParams:
    """The kind's example with one destructive parameter set, as a person who confirmed it sends it.

    The form asks for confirmation when such a parameter holds a truthy value; the contract knows
    how to set a flag. Any other type fails here rather than leave the destructive branch unchecked.
    """
    if kind.params_schema()["properties"][parameter].get("type") != "boolean":
        pytest.fail(
            f"the kind '{kind.name}' asks to confirm '{parameter}', which is not a flag: "
            "the contract needs to be told which value sets it"
        )
    return _params(kind, **{parameter: True})


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

    # The real schemas: the reader finds a dataset's media by looking at them.
    info = SimpleNamespace(tables={"records": Record, "images": Image})

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


def _writer(kind: JobKind, target: _Target, job_id: str, params: JobParams | None = None) -> JobWriter:
    """A writer as the runner builds it, carrying the job's provenance."""
    params = _params(kind) if params is None else params
    return JobWriter(
        lambda: target,
        kind.name,
        job_id,
        kind.source_type,
        params=kind.provenance_params(params),
        model=kind.model_identity(params),
    )


def _plan_and_prepare(kind: JobKind, target: _Target, job_id: str, params: JobParams, times: int = 1) -> list[Chunk]:
    """What the engine does before recording a job's chunks: split the work, then prepare.

    `times` above one is a planner that died after `prepare`, and the next one starting over.
    """
    chunks = list(kind.plan(_reader(), params))
    for _ in range(times):
        kind.prepare(_writer(kind, target, job_id, params), params)
    return chunks


def _execute(
    kind: JobKind,
    target: _Target,
    job_id: str,
    prepare_times: int = 1,
    params: JobParams | None = None,
    finalize_times: int = 1,
) -> None:
    """A whole job, as the engine runs it: split, prepare, every chunk, then finalize.

    `finalize_times` above one is a worker that died while finalizing, and the next one running
    the final chunk again; zero stops the job before its closing step.
    """
    params = _params(kind) if params is None else params
    for chunk in _plan_and_prepare(kind, target, job_id, params, prepare_times):
        kind.write(
            _writer(kind, target, job_id, params),
            kind.process(_reader(), chunk.payload, params),
            chunk.payload,
            params,
        )
    for _ in range(finalize_times if kind.finalizes else 0):
        kind.finalize(_reader(), _writer(kind, target, job_id, params), params)


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
            return [SimpleNamespace(name="clip", model_path="MobileCLIP2-S2", capability="embedding")]

        def embedding(self, request: Any, **_kwargs: Any) -> Any:
            count = len(request.image) if isinstance(request.image, list) else 1
            vectors = np.full((count, FAKE_DIM), 0.1, dtype=np.float32)
            return SimpleNamespace(data=SimpleNamespace(embeddings=SimpleNamespace(to_numpy=lambda: vectors)))

    monkeypatch.setattr("pixano_worker.kinds.inference.SyncPixanoInferenceClient", _Client)


@pytest.fixture(params=REGISTRY.names())
def kind(request: pytest.FixtureRequest) -> JobKind:
    """Each registered kind, in turn."""
    return _registered(request.param)


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


class TestProvenance:
    """Every row a kind writes must say, by itself, how it was produced."""

    def test_every_written_row_carries_the_kind_and_its_parameters(self, kind: JobKind) -> None:
        target = _Target()
        _execute(kind, target, "job-1")
        # Embedding rows carry no provenance fields: the model lives in the dataset's sidecar
        # as long as one table holds one model (backend-processing §12).
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
        before = target.snapshot()

        kind.prepare(_writer(kind, target, "job-2"), _params(kind))

        assert target.snapshot() == before

    def test_preparing_twice_is_the_same_as_once(self, kind: JobKind) -> None:
        """A planner that died after `prepare` lets the next one redo everything."""
        once, twice = _Target(), _Target()
        _execute(kind, once, "job-1")
        _execute(kind, twice, "job-1", prepare_times=2)

        assert twice.snapshot() == once.snapshot()

    @pytest.mark.parametrize(("name", "parameter"), CONFIRMED)
    def test_preparing_twice_with_a_destructive_parameter_is_the_same_as_once(self, name: str, parameter: str) -> None:
        """The destructive branch is where a second call can differ from the first, and the
        default parameters never take it.

        On a dataset a previous run wrote into, so that the parameter has something to destroy —
        which `TestTheDoubles` checks it finds. Compared right after `prepare`: the chunks that
        follow could write back what a second call destroyed too much.
        """
        kind = _registered(name)
        params = _confirmed(kind, parameter)
        once, twice = _Target(), _Target()
        for target in (once, twice):
            _execute(kind, target, "job-1")

        _plan_and_prepare(kind, once, "job-2", params)
        _plan_and_prepare(kind, twice, "job-2", params, times=2)

        assert twice.snapshot() == once.snapshot()


class TestFinalization:
    """The `finalize` hook: no row deleted, and never two different states for two calls."""

    def test_finalizing_deletes_no_row(self, kind: JobKind) -> None:
        """The closing step derives from the rows; it leaves them as the chunks wrote them."""
        target = _Target()
        _execute(kind, target, "job-1", finalize_times=0)
        before = target.snapshot()

        if kind.finalizes:
            kind.finalize(_reader(), _writer(kind, target, "job-1"), _params(kind))

        assert target.snapshot() == before

    def test_finalizing_twice_is_the_same_as_once(self, kind: JobKind) -> None:
        """A worker that died while finalizing lets another run the final chunk again."""
        once, twice = _Target(), _Target()
        _execute(kind, once, "job-1")
        _execute(kind, twice, "job-1", finalize_times=2)

        assert twice.snapshot() == once.snapshot()


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
        first = (len(target.rows), target.snapshot())

        _execute(kind, target, "job-1")

        assert (len(target.rows), target.snapshot()) == first

    def test_a_resubmission_does_not_duplicate(self, kind: JobKind) -> None:
        target = _Target()
        _execute(kind, target, "job-1")
        first = (len(target.rows), target.snapshot())

        _execute(kind, target, "job-2")

        assert (len(target.rows), target.snapshot()) == first

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


class TestTheDoubles:
    """What the contract's stand-ins must do for the kinds' own paths to run through them."""

    @pytest.mark.parametrize(("name", "parameter"), CONFIRMED)
    def test_a_destructive_parameter_finds_what_a_previous_run_left(self, name: str, parameter: str) -> None:
        """A destructive branch reaches the rows through the doubles — a dropped table for the
        vectors — or its idempotence would be checked on nothing."""
        kind = _registered(name)
        target = _Target()
        _execute(kind, target, "job-1")
        left = target.snapshot()

        _plan_and_prepare(kind, target, "job-2", _confirmed(kind, parameter))

        assert target.snapshot() != left


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
        """Ten thousand ids made 260 kB of metadata on each labelled row."""
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
