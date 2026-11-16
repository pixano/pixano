# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The clustering job, run as the runner runs it, on a real dataset: the groups it writes, the run it
records, and what it refuses."""

import threading
from collections import OrderedDict
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
from pixano_worker import runner
from pixano_worker.kinds import ClusteringKind
from pixano_worker.kinds import clustering as clustering_module
from pixano_worker.kinds.base import Outcome
from pixano_worker.kinds.clustering import (
    HDBSCAN_MAX_NEIGHBOURS,
    NO_EMBEDDINGS,
    NO_RECORDS,
    NO_VECTORS,
    RECORDS_OF_UNIT_WEIGHT,
    _numbered_by_size,
    _placed,
)
from pixano_worker.media import MediaResolver
from pixano_worker.progress import ChunkCancelled, ChunkProgress
from pixano_worker.reader import RecordVectors
from pydantic import ValidationError

from pixano.clustering.runs import ClusteringAlgorithm
from pixano.datasets import Dataset
from pixano.datasets.dataset_info import DatasetInfo
from pixano.schemas import NOISE_CLUSTER, Image, Record


DATASET_ID = "shapes"
DIM = 4
MODEL = "clip"
TABLE = "record_clusters"
#: Six records close to one direction, four close to a direction near it, and one opposite both:
#: two groups, the larger first, and a record no group takes in.
NEAR_A = {f"a{n}": [1.0, 0.0, 0.01 * n, 0.0] for n in range(6)}
NEAR_B = {f"b{n}": [0.7, 0.7, 0.0, 0.01 * n] for n in range(4)}
FAR = {"far": [-1.0, 0.0, 0.0, 0.0]}
#: A record with no embedding: the job skips it.
BARE = "bare"


def _library(tmp_path: Path, vectors: dict[str, list[list[float]]], embeddings: bool = True) -> Path:
    """A dataset of these records, each with these vectors — one per image —, and one without any."""
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID, DatasetInfo(id=DATASET_ID, name="Shapes", record=Record, views={"image": Image})
    )
    dataset.add_records({"records": [Record(id=record_id) for record_id in [*vectors, BARE]]})
    if embeddings:
        dataset.create_record_embedding_table(dim=DIM, model_id=MODEL)
        rows = [
            {"record_id": record_id, "view_id": f"{record_id}-image-{n}", "vector": vector}
            for record_id, its_vectors in vectors.items()
            for n, vector in enumerate(its_vectors)
        ]
        if rows:
            dataset.add_record_embeddings(rows)
    return library


def _one_each(vectors: dict[str, list[float]]) -> dict[str, list[list[float]]]:
    return {record_id: [vector] for record_id, vector in vectors.items()}


@pytest.fixture(autouse=True)
def _no_dataset_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    # The runner keeps the datasets it opened in a module-level cache: empty, the tests stay apart.
    monkeypatch.setattr(runner, "_open_datasets", OrderedDict())


@pytest.fixture
def library(tmp_path: Path) -> Path:
    """Two groups and a record far from both, every record with one vector, and one record without."""
    return _library(tmp_path, _one_each({**NEAR_A, **NEAR_B, **FAR}))


def _planned(library: Path, params: dict[str, Any], job_id: str = "job-1") -> tuple[Any, list[Any]]:
    kind = ClusteringKind()
    validated = kind.validate_params(params)
    media = MediaResolver(str(library), str(library))
    chunks = runner._plan_and_prepare(kind, library, DATASET_ID, media, job_id, validated, threading.Event())
    return validated, chunks


def _processed(library: Path, validated: Any, chunk: Any, progress: ChunkProgress | None = None) -> dict[str, Any]:
    media = MediaResolver(str(library), str(library))
    reader = runner._reader_for(library, DATASET_ID, media, progress=progress)
    return ClusteringKind().process(reader, chunk.payload, validated)


def _written(library: Path, validated: Any, chunk: Any, result: dict[str, Any], job_id: str = "job-1") -> None:
    kind = ClusteringKind()
    kind.write(runner._writer_for(library, DATASET_ID, kind, job_id, validated), result, chunk.payload, validated)


def _run(library: Path, params: dict[str, Any], job_id: str = "job-1") -> Outcome:
    """One job as the runner runs it, without the queue: planned and prepared, its chunk processed
    and written; what became of its records."""
    validated, chunks = _planned(library, params, job_id)
    produced = skipped = 0
    for chunk in chunks:
        result = _processed(library, validated, chunk)
        _written(library, validated, chunk, result, job_id)
        outcome = ClusteringKind().outcome(result, chunk.payload, chunk.task_count)
        produced, skipped = produced + outcome.produced, skipped + outcome.skipped
    return Outcome(produced=produced, skipped=skipped)


def _clusters(library: Path, run_id: str = "job-1") -> dict[str, int]:
    """Each record's cluster in a run, as the dataset holds it."""
    rows = Dataset(library / DATASET_ID).open_table(TABLE).to_arrow().to_pylist()
    return {row["record_id"]: row["cluster"] for row in rows if row["run_id"] == run_id}


def _groups(clusters: dict[str, int]) -> list[set[str]]:
    """The records of each group, in the order of its number; noise left out."""
    numbers = sorted({cluster for cluster in clusters.values() if cluster != NOISE_CLUSTER})
    return [{record for record, cluster in clusters.items() if cluster == number} for number in numbers]


def _vectors(rows: list[tuple[str, str, list[float]]]) -> RecordVectors:
    return RecordVectors(
        record_ids=[record for record, _view, _vector in rows],
        view_ids=[view for _record, view, _vector in rows],
        vectors=np.array([vector for _record, _view, vector in rows], dtype=np.float32),
    )


class TestGroups:
    def test_k_means_makes_the_groups_asked_the_largest_first(self, tmp_path: Path) -> None:
        library = _library(tmp_path, _one_each({**NEAR_A, **NEAR_B}))

        _run(library, {"algorithm": "kmeans", "clusters": 2})

        assert _groups(_clusters(library)) == [set(NEAR_A), set(NEAR_B)]

    def test_k_means_asked_more_groups_than_records_makes_one_a_record(self, tmp_path: Path) -> None:
        library = _library(tmp_path, _one_each({"a0": NEAR_A["a0"], "b0": NEAR_B["b0"]}))

        _run(library, {"algorithm": "kmeans", "clusters": 5})

        assert sorted(_clusters(library).values()) == [0, 1]

    def test_hdbscan_leaves_a_record_far_from_every_group_as_noise(self, library: Path) -> None:
        _run(library, {"algorithm": "hdbscan", "min_cluster_size": 3})

        clusters = _clusters(library)
        assert _groups(clusters) == [set(NEAR_A), set(NEAR_B)]
        assert clusters["far"] == NOISE_CLUSTER

    def test_hdbscan_over_fewer_records_than_a_group_calls_them_all_noise(self, library: Path) -> None:
        _run(library, {"algorithm": "hdbscan", "min_cluster_size": 20})

        assert set(_clusters(library).values()) == {NOISE_CLUSTER}

    def test_hdbscan_groups_identical_vectors_together(self, tmp_path: Path) -> None:
        # Duplicate images: their neighbours sit at no distance at all.
        twins = {f"twin{n}": [0.0, 0.0, 1.0, 0.0] for n in range(5)}
        library = _library(tmp_path, _one_each({**NEAR_A, **twins}))

        _run(library, {"algorithm": "hdbscan", "min_cluster_size": 3})

        assert set(twins) in _groups(_clusters(library))

    def test_hdbscan_reads_no_more_neighbours_than_its_bound(self, tmp_path: Path, monkeypatch) -> None:
        import sklearn.cluster

        # More records than a group of more than the bound: HDBSCAN runs.
        directions = np.random.default_rng(0).normal(size=(HDBSCAN_MAX_NEIGHBOURS + 10, DIM))
        library = _library(tmp_path, {f"r{n}": [list(vector)] for n, vector in enumerate(directions)})

        asked: dict[str, Any] = {}
        real = sklearn.cluster.HDBSCAN

        def spying(**kwargs: Any) -> Any:
            asked.update(kwargs)
            return real(**{**kwargs, "min_cluster_size": 3, "min_samples": 3})

        monkeypatch.setattr(sklearn.cluster, "HDBSCAN", spying)

        _run(library, {"algorithm": "hdbscan", "min_cluster_size": HDBSCAN_MAX_NEIGHBOURS + 5})

        assert (asked["min_cluster_size"], asked["min_samples"]) == (
            HDBSCAN_MAX_NEIGHBOURS + 5,
            HDBSCAN_MAX_NEIGHBOURS,
        )

    def test_a_record_without_an_embedding_gets_no_row_and_is_skipped(self, library: Path) -> None:
        outcome = _run(library, {"algorithm": "kmeans", "clusters": 2})

        assert BARE not in _clusters(library)
        assert (outcome.produced, outcome.skipped) == (len(NEAR_A) + len(NEAR_B) + len(FAR), 1)

    def test_a_record_with_a_vector_per_image_is_grouped_once(self, tmp_path: Path) -> None:
        library = _library(tmp_path, {**_one_each(NEAR_A), "b0": [NEAR_B["b0"], NEAR_B["b1"]]})

        outcome = _run(library, {"algorithm": "kmeans", "clusters": 2})

        assert _groups(_clusters(library)) == [set(NEAR_A), {"b0"}]
        assert (outcome.produced, outcome.skipped) == (len(NEAR_A) + 1, 1)

    def test_a_vector_of_zeros_groups_nothing(self, tmp_path: Path) -> None:
        library = _library(tmp_path, {**_one_each({**NEAR_A, **NEAR_B}), "zeros": [[0.0] * DIM]})

        outcome = _run(library, {"algorithm": "kmeans", "clusters": 2})

        assert "zeros" not in _clusters(library)
        assert outcome.skipped == 2


class TestPlaces:
    def test_a_record_is_placed_by_the_mean_of_its_vectors_each_of_unit_length(self) -> None:
        # A long vector weighs no more than a short one.
        records, places = _placed(
            _vectors(
                [("r1", "v1", [10.0, 0.0, 0.0, 0.0]), ("r1", "v2", [0.0, 0.1, 0.0, 0.0]), ("r2", "v3", [0, 0, 3, 0])]
            ),
            held={"r1", "r2"},
        )

        assert records == ["r1", "r2"]
        np.testing.assert_allclose(places, [[2**-0.5, 2**-0.5, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]], rtol=1e-6)

    def test_a_whole_records_vector_counts_when_its_medias_point_nowhere(self) -> None:
        records, places = _placed(
            _vectors([("r1", "v1", [0.0, 0.0, 0.0, 0.0]), ("r1", "", [0.0, 2.0, 0.0, 0.0])]), held={"r1"}
        )

        assert records == ["r1"]
        np.testing.assert_allclose(places, [[0.0, 1.0, 0.0, 0.0]], rtol=1e-6)

    def test_a_medium_counts_once_and_a_whole_records_vector_only_alone(self) -> None:
        records, places = _placed(
            _vectors(
                [
                    ("r1", "v1", [1.0, 0.0, 0.0, 0.0]),
                    # The same image computed twice — by the application and by a job.
                    ("r1", "v1", [0.0, 1.0, 0.0, 0.0]),
                    # A vector of the whole record, beside its images': left out.
                    ("r1", "", [0.0, 0.0, 1.0, 0.0]),
                    # A record with nothing but such a vector: placed by it.
                    ("r2", "", [0.0, 0.0, 0.0, 2.0]),
                ]
            ),
            held={"r1", "r2"},
        )

        assert records == ["r1", "r2"]
        np.testing.assert_allclose(places, [[1.0, 0.0, 0.0, 0.0], [0.0, 0.0, 0.0, 1.0]], rtol=1e-6)

    def test_a_vector_of_no_number_points_nowhere(self) -> None:
        # LanceDB refuses to store one; another writer of the table may not.
        records, _places = _placed(
            _vectors(
                [
                    ("r1", "v1", [float("nan"), 0, 0, 0]),
                    ("r2", "v2", [float("inf"), 0, 0, 0]),
                    ("r3", "v3", [1, 0, 0, 0]),
                ]
            ),
            held={"r1", "r2", "r3"},
        )

        assert records == ["r3"]

    def test_a_record_the_dataset_no_longer_holds_is_left_out(self) -> None:
        records, _places = _placed(
            _vectors([("r1", "v1", [1.0, 0, 0, 0]), ("gone", "v2", [0, 1.0, 0, 0])]), held={"r1"}
        )

        assert records == ["r1"]

    def test_a_record_whose_vectors_cancel_out_is_placed_nowhere(self) -> None:
        records, _places = _placed(
            _vectors([("r1", "v1", [1.0, 0, 0, 0]), ("r1", "v2", [-1.0, 0, 0, 0]), ("r2", "v3", [0, 1.0, 0, 0])]),
            held={"r1", "r2"},
        )

        assert records == ["r2"]

    def test_groups_are_numbered_by_decreasing_size_and_every_negative_label_is_noise(self) -> None:
        numbered = _numbered_by_size(np.array([3, 3, NOISE_CLUSTER, 1, 3, 1, 7, -2]))

        assert numbered.tolist() == [0, 0, NOISE_CLUSTER, 1, 0, 1, 2, NOISE_CLUSTER]


class TestTheRun:
    def test_the_dataset_says_what_the_run_was(self, library: Path) -> None:
        _run(library, {"algorithm": "hdbscan", "min_cluster_size": 3}, job_id="job-7")

        (run,) = Dataset(library / DATASET_ID).info.clusterings
        assert (run.run_id, run.algorithm, run.parameters, run.model) == (
            "job-7",
            ClusteringAlgorithm.HDBSCAN,
            {"min_cluster_size": 3},
            MODEL,
        )
        assert (run.clusters, run.noise, run.records) == (2, 1, len(NEAR_A) + len(NEAR_B) + len(FAR))

    def test_a_job_run_again_under_its_identifier_writes_the_same_rows_over_its_own(self, library: Path) -> None:
        _run(library, {"algorithm": "kmeans", "clusters": 2})
        first = _clusters(library)

        _run(library, {"algorithm": "kmeans", "clusters": 2})

        rows = Dataset(library / DATASET_ID).open_table(TABLE).count_rows()
        assert (_clusters(library), rows) == (first, len(first))
        assert len(Dataset(library / DATASET_ID).info.clusterings) == 1

    def test_another_job_keeps_the_first_run(self, library: Path) -> None:
        _run(library, {"algorithm": "kmeans", "clusters": 2}, job_id="job-1")
        first = _clusters(library, "job-1")

        _run(library, {"algorithm": "hdbscan", "min_cluster_size": 3}, job_id="job-2")

        assert _clusters(library, "job-1") == first
        assert _clusters(library, "job-2")["far"] == NOISE_CLUSTER
        assert [run.run_id for run in Dataset(library / DATASET_ID).info.clusterings] == ["job-1", "job-2"]

    def test_the_table_is_indexed_on_its_records_and_its_runs(self, library: Path) -> None:
        _run(library, {"algorithm": "kmeans", "clusters": 2}, job_id="job-1")
        _run(library, {"algorithm": "kmeans", "clusters": 3}, job_id="job-2")

        table = Dataset(library / DATASET_ID).open_table(TABLE)
        indexed = {
            index.columns[0]: (index.index_type, table.index_stats(index.name).num_unindexed_rows)
            for index in table.list_indices()
        }
        assert indexed == {"record_id": ("BTree", 0), "run_id": ("Bitmap", 0)}

    def test_a_record_deleted_meanwhile_gets_no_row_and_counts_in_none(self, library: Path) -> None:
        validated, (chunk,) = _planned(library, {"algorithm": "hdbscan", "min_cluster_size": 3})
        result = _processed(library, validated, chunk)
        Dataset(library / DATASET_ID).delete_records(["far"])

        _written(library, validated, chunk, result)

        (run,) = Dataset(library / DATASET_ID).info.clusterings
        assert "far" not in _clusters(library)
        assert (run.records, run.noise) == (len(NEAR_A) + len(NEAR_B), 0)

    def test_the_vectors_of_a_record_deleted_before_are_left_out(self, library: Path) -> None:
        # Deleting a record alone leaves its vectors, as the records route does.
        Dataset(library / DATASET_ID).delete_data("records", ["far"])

        outcome = _run(library, {"algorithm": "hdbscan", "min_cluster_size": 3})

        assert "far" not in _clusters(library)
        assert outcome.produced == len(NEAR_A) + len(NEAR_B)


class TestOneGroupingOfADatasetAtATime:
    """An attempt past its time limit runs on to its grouping's end: the next one waits for it."""

    def test_an_attempt_waits_for_an_earlier_one_and_stops_when_no_longer_awaited(
        self, library: Path, monkeypatch
    ) -> None:
        monkeypatch.setattr(clustering_module, "GROUPING_WAIT_CHECK_S", 0.01)
        validated, (chunk,) = _planned(library, {"algorithm": "kmeans", "clusters": 2})
        progress = ChunkProgress(chunk.task_count)
        outcome: list[BaseException] = []

        def attempt() -> None:
            try:
                _processed(library, validated, chunk, progress)
            except BaseException as error:  # noqa: BLE001 - what the thread ended with
                outcome.append(error)

        with clustering_module._grouping_of(DATASET_ID, ChunkProgress(0)):
            waiting = threading.Thread(target=attempt)
            waiting.start()
            waiting.join(timeout=0.2)
            assert waiting.is_alive(), "the attempt grouped beside the earlier one"
            progress.cancel()
            waiting.join(timeout=5)

        assert not waiting.is_alive()
        assert [type(error) for error in outcome] == [ChunkCancelled]

    def test_an_attempt_groups_once_the_earlier_one_ended(self, library: Path, monkeypatch) -> None:
        monkeypatch.setattr(clustering_module, "GROUPING_WAIT_CHECK_S", 0.01)
        validated, (chunk,) = _planned(library, {"algorithm": "kmeans", "clusters": 2})
        results: list[dict[str, Any]] = []

        with clustering_module._grouping_of(DATASET_ID, ChunkProgress(0)):
            waiting = threading.Thread(target=lambda: results.append(_processed(library, validated, chunk)))
            waiting.start()
            waiting.join(timeout=0.2)
            assert not results
        waiting.join(timeout=30)

        assert len(results[0]["clusters"]) == len(NEAR_A) + len(NEAR_B) + len(FAR)

    def test_another_datasets_grouping_does_not_wait(self, library: Path) -> None:
        validated, (chunk,) = _planned(library, {"algorithm": "kmeans", "clusters": 2})

        with clustering_module._grouping_of("another-dataset", ChunkProgress(0)):
            result = _processed(library, validated, chunk)

        assert result["clusters"]


class TestCancelled:
    def test_before_the_grouping_writes_nothing(self, library: Path) -> None:
        validated, (chunk,) = _planned(library, {"algorithm": "kmeans", "clusters": 2})
        progress = ChunkProgress(chunk.task_count)
        progress.cancel()

        with pytest.raises(ChunkCancelled):
            _processed(library, validated, chunk, progress)

    def test_during_the_grouping_stops_once_it_ends(self, library: Path, monkeypatch) -> None:
        validated, (chunk,) = _planned(library, {"algorithm": "kmeans", "clusters": 2})
        progress = ChunkProgress(chunk.task_count)
        grouped = clustering_module._grouped

        def cancelled_meanwhile(*args: Any, **kwargs: Any) -> np.ndarray:
            groups = grouped(*args, **kwargs)
            progress.cancel()
            return groups

        monkeypatch.setattr(clustering_module, "_grouped", cancelled_meanwhile)

        with pytest.raises(ChunkCancelled):
            _processed(library, validated, chunk, progress)

    def test_between_hdbscans_projection_and_its_grouping(self, library: Path, monkeypatch) -> None:
        import sklearn.decomposition

        validated, (chunk,) = _planned(library, {"algorithm": "hdbscan", "min_cluster_size": 3})
        progress = ChunkProgress(chunk.task_count)
        real = sklearn.decomposition.PCA

        class CancellingPCA(real):  # type: ignore[misc, valid-type]
            def fit_transform(self, *args: Any, **kwargs: Any) -> Any:
                reduced = super().fit_transform(*args, **kwargs)
                progress.cancel()
                return reduced

        monkeypatch.setattr(sklearn.decomposition, "PCA", CancellingPCA)
        monkeypatch.setattr(clustering_module, "_numbered_by_size", lambda groups: pytest.fail("HDBSCAN ran"))

        with pytest.raises(ChunkCancelled):
            _processed(library, validated, chunk, progress)


class TestRefused:
    def test_a_dataset_without_embeddings(self, tmp_path: Path) -> None:
        library = _library(tmp_path, _one_each(NEAR_A), embeddings=False)

        with pytest.raises(ValueError, match=NO_EMBEDDINGS):
            _run(library, {"algorithm": "kmeans"})

    def test_a_dataset_whose_embeddings_table_holds_no_vector(self, tmp_path: Path) -> None:
        library = _library(tmp_path, {})

        with pytest.raises(ValueError, match=f"the embeddings of '{MODEL}' hold no vector"):
            _run(library, {"algorithm": "kmeans"})

    def test_a_model_the_dataset_holds_no_embeddings_of(self, library: Path) -> None:
        with pytest.raises(ValueError, match="holds no embeddings of 'siglip'"):
            _run(library, {"algorithm": "kmeans", "model": "siglip"})

    def test_not_the_model_the_dataset_holds_when_named(self, library: Path) -> None:
        assert _run(library, {"algorithm": "kmeans", "clusters": 2, "model": MODEL}).produced > 0

    def test_a_dataset_without_records(self, library: Path) -> None:
        dataset = Dataset(library / DATASET_ID)
        dataset.delete_data("records", [*NEAR_A, *NEAR_B, *FAR, BARE])

        with pytest.raises(ValueError, match=NO_RECORDS):
            _run(library, {"algorithm": "kmeans"})

    def test_embeddings_gone_since_the_job_was_planned(self, library: Path) -> None:
        # The chunk reads the dataset as it is now, reopened: the space its plan names is gone.
        validated, (chunk,) = _planned(library, {"algorithm": "kmeans"})
        Dataset(library / DATASET_ID).drop_record_embeddings()

        with pytest.raises(ValueError, match=f"the embeddings of '{MODEL}' went since the job was planned"):
            _processed(library, validated, chunk)

    def test_vectors_of_records_all_gone(self, library: Path) -> None:
        validated, (chunk,) = _planned(library, {"algorithm": "kmeans"})
        Dataset(library / DATASET_ID).delete_data("records", [*NEAR_A, *NEAR_B, *FAR])

        with pytest.raises(ValueError, match=NO_VECTORS):
            _processed(library, validated, chunk)

    @pytest.mark.parametrize(
        "params",
        [{"clusters": 1}, {"clusters": 1_001}, {"min_cluster_size": 1}, {"algorithm": "spectral"}],
        ids=["one group", "too many groups", "groups of one", "unknown algorithm"],
    )
    def test_parameters_out_of_bounds(self, params: dict[str, Any]) -> None:
        with pytest.raises(ValidationError):
            ClusteringKind().validate_params(params)


class TestSeveralModels:
    """A dataset holds the embeddings of several models; a run groups the records by one of them."""

    #: A second model, which sees the far record next to the first group.
    OTHER_MODEL = "siglip"

    def _with_another_model(self, library: Path) -> dict[str, Any]:
        dataset = Dataset(library / DATASET_ID)
        other = dataset.ensure_record_embedding_space(self.OTHER_MODEL, "", dim=DIM)
        seen = {**NEAR_A, "far": next(iter(NEAR_A.values())), **NEAR_B}
        rows = [
            {"record_id": record_id, "view_id": f"{record_id}-image-0", "vector": vector}
            for record_id, vector in seen.items()
        ]
        dataset.add_record_embeddings(rows, other["id"])
        return other

    def test_a_run_groups_by_the_model_it_names(self, library: Path) -> None:
        self._with_another_model(library)

        _run(library, {"algorithm": "kmeans", "clusters": 2, "model": self.OTHER_MODEL})

        (run,) = Dataset(library / DATASET_ID).info.clusterings
        assert run.model == self.OTHER_MODEL
        # The far record with the first group, as this model sees it: clip leaves it alone.
        assert {*NEAR_A, "far"} in _groups(_clusters(library))

    def test_a_run_naming_no_model_groups_by_the_default_one(self, library: Path) -> None:
        self._with_another_model(library)

        _run(library, {"algorithm": "kmeans", "clusters": 2})

        (run,) = Dataset(library / DATASET_ID).info.clusterings
        assert run.model == MODEL

    def test_a_worker_reads_a_space_another_created_after_it_opened_the_dataset(
        self, library: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A worker's cached dataset is opened again once another process changed it."""
        monkeypatch.setattr(runner, "_open_datasets", OrderedDict())
        opened = runner._open_dataset(library, DATASET_ID)
        assert runner._open_dataset(library, DATASET_ID) is opened

        other = self._with_another_model(library)

        again = runner._open_dataset(library, DATASET_ID)
        assert again is not opened and again.has_record_embeddings(other["id"])

    def test_a_chunk_reads_the_space_it_was_planned_on_whatever_the_default_becomes(self, library: Path) -> None:
        other = self._with_another_model(library)
        validated, (chunk,) = _planned(library, {"algorithm": "kmeans", "clusters": 2})
        Dataset(library / DATASET_ID).set_default_record_embedding_space(other["id"])

        result = _processed(library, validated, chunk)

        # The far record alone, as clip sees it: the other model would have put it with the first group.
        assert result["model"] == MODEL
        assert {"far"} in _groups(result["clusters"])


class TestWeight:
    @pytest.mark.parametrize(
        ("records", "weight"),
        [(1, 1), (RECORDS_OF_UNIT_WEIGHT, 1), (RECORDS_OF_UNIT_WEIGHT + 1, 2), (2 * RECORDS_OF_UNIT_WEIGHT, 4)],
    )
    def test_grows_as_the_square_of_the_records(self, records: int, weight: int) -> None:
        # A dataset of hundreds of thousands of records, counted as the reader counts it.
        reader = SimpleNamespace(
            dataset=SimpleNamespace(
                record_embedding_space=lambda model=None: {"id": "clip-0", "table": "embeddings", "model_id": MODEL}
            ),
            count=lambda table: records,
        )

        (chunk,) = ClusteringKind().plan(reader, ClusteringKind().validate_params({}))  # type: ignore[arg-type]

        assert (chunk.task_count, chunk.weight) == (records, weight)
