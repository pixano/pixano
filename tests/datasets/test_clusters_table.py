# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""A dataset's clusters: one row per run and record, and what each run was."""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from pixano.clustering.runs import Clustering, ClusteringAlgorithm
from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.io import ImportSpec, SpecValidationError, resolve_dataset_info
from pixano.datasets.io.reader import RecordBundleReader
from pixano.datasets.io.spec import SchemaSpec
from pixano.schemas import NOISE_CLUSTER, BBox, Entity, Image, Record, RecordClusters, SchemaGroup


TABLE = "record_clusters"


def _dataset(tmp_path: Path) -> Dataset:
    target = tmp_path / "ds"
    dataset = Dataset.create(
        target, DatasetInfo(id="ds", name="ds", record=Record, entity=Entity, bbox=BBox, views={"image": Image})
    )
    dataset.add_records({"records": [Record(id="r1"), Record(id="r2"), Record(id="r3")]})
    return dataset


def _info_json(dataset: Dataset) -> dict:
    return json.loads((dataset.path / "info.json").read_text(encoding="utf-8"))


def _rows(dataset: Dataset) -> list[tuple[str, str, int]]:
    rows = dataset.open_table(TABLE).to_arrow().to_pylist()
    return sorted((row["run_id"], row["record_id"], row["cluster"]) for row in rows)


def _run(run_id: str = "job-1", clusters: int = 2) -> Clustering:
    """A run of K-Means as its job found it, before the dataset counts what it wrote."""
    return Clustering(
        run_id=run_id,
        algorithm=ClusteringAlgorithm.KMEANS,
        parameters={"clusters": clusters},
        model="clip",
        clusters=clusters,
        noise=0,
        records=3,
        computed_at=datetime(2026, 11, 6, 15, 40, tzinfo=timezone.utc),
    )


class TestTheTable:
    def test_is_created_and_declared_once(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)

        assert dataset.ensure_record_clusters() == TABLE
        written = (dataset.path / "info.json").stat().st_mtime_ns
        assert dataset.ensure_record_clusters() == TABLE

        assert "record_clusters" in _info_json(dataset)
        assert (dataset.path / "info.json").stat().st_mtime_ns == written, "info.json rewritten for nothing"
        assert Dataset(dataset.path).info.record_clusters is RecordClusters

    def test_is_in_a_group_of_its_own(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_record_clusters()

        assert Dataset(dataset.path).info.groups[SchemaGroup.CLUSTERS] == {TABLE}


class TestARunsRows:
    def test_one_row_per_record_with_its_cluster(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)

        dataset.write_clustering(_run(), {"r1": 0, "r2": 1, "r3": 0})

        assert _rows(dataset) == [("job-1", "r1", 0), ("job-1", "r2", 1), ("job-1", "r3", 0)]

    def test_a_run_written_again_replaces_its_rows_and_leaves_another_runs(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.write_clustering(_run("job-1"), {"r1": 0, "r2": 1, "r3": 0})
        dataset.write_clustering(_run("job-2"), {"r1": 1, "r2": 1})

        dataset.write_clustering(_run("job-1"), {"r1": 1, "r2": 0})

        assert _rows(dataset) == [("job-1", "r1", 1), ("job-1", "r2", 0), ("job-2", "r1", 1), ("job-2", "r2", 1)]

    def test_a_record_deleted_since_it_was_grouped_gets_no_row_and_counts_in_none(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.delete_data("records", ["r2"])

        recorded = dataset.write_clustering(_run(), {"r1": 0, "r2": 1})

        assert _rows(dataset) == [("job-1", "r1", 0)]
        assert (recorded.records, recorded.clusters, recorded.noise) == (1, 1, 0)

    def test_a_record_deleted_takes_its_rows_with_it(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.write_clustering(_run(), {"r1": 0, "r2": 1})

        dataset.delete_records(["r1"])

        assert _rows(dataset) == [("job-1", "r2", 1)]

    def test_a_run_of_no_record_writes_no_row(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)

        recorded = dataset.write_clustering(_run(), {})

        assert (_rows(dataset), recorded.records) == ([], 0)


class TestTheRuns:
    def test_a_run_is_kept_counted_from_its_rows_and_read_back(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)

        recorded = dataset.write_clustering(_run(), {"r1": 0, "r2": NOISE_CLUSTER, "r3": 0})

        assert (recorded.clusters, recorded.noise, recorded.records) == (1, 1, 3)
        assert dataset.info.clusterings == [recorded]
        assert Dataset(dataset.path).info.clusterings == [recorded]

    def test_a_run_written_again_replaces_its_entry(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.write_clustering(_run("job-1"), {"r1": 0, "r2": 1})
        dataset.write_clustering(_run("job-2"), {"r1": 0})

        dataset.write_clustering(_run("job-1"), {"r1": 0, "r2": 1, "r3": 2})

        assert [(run.run_id, run.clusters) for run in Dataset(dataset.path).info.clusterings] == [
            ("job-2", 1),
            ("job-1", 3),
        ]

    def test_an_entry_this_build_cannot_read_is_left_out_and_kept_as_written(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        info = _info_json(dataset)
        info["clusterings"] = [{"run_id": "old", "algorithm": "spectral"}]
        (dataset.path / "info.json").write_text(json.dumps(info), encoding="utf-8")
        dataset = Dataset(dataset.path)

        recorded = dataset.write_clustering(_run(), {"r1": 0})

        assert dataset.info.clusterings == [recorded]
        assert [entry["run_id"] for entry in _info_json(dataset)["clusterings"]] == ["old", "job-1"]

    def test_a_run_dropped_takes_its_rows_and_its_entry(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.write_clustering(_run("job-1"), {"r1": 0})
        dataset.write_clustering(_run("job-2"), {"r1": 1})

        dataset.drop_clustering("job-1")

        assert _rows(dataset) == [("job-2", "r1", 1)]
        assert [run.run_id for run in Dataset(dataset.path).info.clusterings] == ["job-2"]

    def test_a_run_dropped_from_a_dataset_without_clusters_changes_nothing(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)

        dataset.drop_clustering("job-1")

        assert (TABLE in Dataset(dataset.path).info.tables, Dataset(dataset.path).info.clusterings) == (False, [])

    def test_is_counted_from_its_groups(self) -> None:
        counted = _run().counted({"r1": 0, "r2": 1, "r3": NOISE_CLUSTER, "r4": 1})

        assert (counted.clusters, counted.noise, counted.records) == (2, 1, 4)

    def test_names_its_column_by_what_it_was_asked(self) -> None:
        hdbscan = _run().model_copy(
            update={"algorithm": ClusteringAlgorithm.HDBSCAN, "parameters": {"min_cluster_size": 10}}
        )

        assert _run().label == "Clusters — K-Means, 2 groups, 2026-11-06 15:40 UTC"
        assert hdbscan.label == "Clusters — HDBSCAN, groups of 10 or more, 2026-11-06 15:40 UTC"

    def test_names_a_run_of_hdbscan_that_found_no_group_so(self) -> None:
        nothing = _run().model_copy(
            update={
                "algorithm": ClusteringAlgorithm.HDBSCAN,
                "parameters": {"min_cluster_size": 10},
                "clusters": 0,
                "noise": 3,
            }
        )

        assert nothing.label == "Clusters — HDBSCAN, groups of 10 or more, no group found, 2026-11-06 15:40 UTC"

    def test_an_entry_without_its_size_is_named_without_it(self) -> None:
        hdbscan = _run().model_copy(update={"algorithm": ClusteringAlgorithm.HDBSCAN, "parameters": {}})

        assert hdbscan.label == "Clusters — HDBSCAN, 2026-11-06 15:40 UTC"

    def test_dates_its_column_in_utc_whatever_zone_it_was_given(self) -> None:
        paris = timezone(timedelta(hours=1))
        run = _run().model_copy(update={"computed_at": datetime(2026, 11, 6, 16, 40, tzinfo=paris)})

        assert run.label.endswith("2026-11-06 15:40 UTC")

    def test_refuses_a_time_without_its_zone(self) -> None:
        with pytest.raises(ValidationError):
            Clustering.model_validate({**_run().model_dump(), "computed_at": "2026-11-06T15:40:00"})


class TestComputedFromTheDataset:
    """Clusters are computed from a dataset, and computed again on another: nothing carries them."""

    def test_no_export_carries_the_runs(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.write_clustering(_run(), {"r1": 0})

        assert "clusterings" not in dataset.info.json_info_dump()

    def test_an_export_reads_no_cluster(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.write_clustering(_run(), {"r1": 0})

        bundles = list(RecordBundleReader().iter_bundles(Dataset(dataset.path)))

        assert bundles and all(TABLE not in bundle.components for bundle in bundles)

    def test_an_import_declares_no_clusters_table(self) -> None:
        spec = ImportSpec.model_validate(
            {
                "pixano": 2,
                "dataset": {"name": "d", "workspace": "image"},
                "format": "pixano_jsonl",
                "schema_manifest": {"record_clusters": {"base": "RecordClusters", "fields": {}}},
            }
        )

        with pytest.raises(SpecValidationError, match="computes from itself"):
            resolve_dataset_info(spec)

    def test_a_dataset_described_for_an_import_declares_no_clusters(self, tmp_path: Path) -> None:
        dataset = _dataset(tmp_path)
        dataset.ensure_record_clusters()

        spec = SchemaSpec.from_dataset_info(Dataset(dataset.path).info)

        assert spec.annotations == ["bbox"]
