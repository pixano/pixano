# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The explorer on the clusters a dataset's records were grouped into: a column per run, its sorts,
its filters, its neighbors."""

import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.routers.explorer import _prefilter_record_ids
from pixano.api.settings import Settings, get_settings
from pixano.clustering.runs import Clustering, ClusteringAlgorithm
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.features import Image, Record
from pixano.schemas import NOISE_CLUSTER


DATASET_ID = "explorer_clusters"
RECORDS = ["r1", "r2", "r3", "r4", "r5"]
#: A run of HDBSCAN: two groups, r4 in none, r5 not grouped — it had no embedding.
GROUPS = {"r1": 1, "r2": 0, "r3": 0, "r4": NOISE_CLUSTER}
RUN = Clustering(
    run_id="job-1",
    algorithm=ClusteringAlgorithm.HDBSCAN,
    parameters={"min_cluster_size": 2},
    model="clip",
    clusters=2,
    noise=1,
    records=len(GROUPS),
    computed_at=datetime(2026, 11, 6, 15, 40, tzinfo=timezone.utc),
)
COLUMN = f"record_clusters.{RUN.run_id}"


@pytest.fixture
def library(tmp_path: Path) -> Path:
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID, DatasetInfo(id=DATASET_ID, name=DATASET_ID, record=Record, views={"image": Image})
    )
    dataset.add_records({"records": [Record(id=record, split="train") for record in RECORDS]})
    return library


@pytest.fixture
def clustered(library: Path) -> Dataset:
    """The dataset once a run grouped its records."""
    dataset = Dataset.find(DATASET_ID, library)
    dataset.write_clustering(RUN, GROUPS)
    return dataset


@pytest.fixture
def client(library: Path, tmp_path: Path) -> TestClient:
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    settings = Settings(library_dir=str(library), models_dir=str(models_dir))

    @lru_cache
    def settings_override() -> Settings:
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = settings_override
    return TestClient(app)


def _records(client: TestClient, **params) -> dict:  # noqa: ANN003 - query parameters
    response = client.get(f"/datasets/{DATASET_ID}/records", params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _ids(page: dict) -> list[str]:
    return [item["id"] for item in page["items"]]


def _cluster_columns(client: TestClient) -> dict[str, dict]:
    columns = client.get(f"/datasets/{DATASET_ID}/filters").json()["columns"]
    return {column["name"]: column for column in columns if column["table"] == "record_clusters"}


@pytest.mark.usefixtures("clustered")
class TestColumns:
    def test_each_run_is_a_column_named_by_how_it_was_made(self, client: TestClient) -> None:
        column = _cluster_columns(client)[COLUMN]

        assert {key: column[key] for key in ("label", "type", "source", "sortable", "filterable")} == {
            "label": "Clusters — HDBSCAN, groups of 2 or more, 2026-11-06 15:40 UTC",
            "type": "int",
            "source": "clusters",
            "sortable": True,
            "filterable": True,
        }

    def test_its_groups_are_listed_noise_first_and_named(self, client: TestClient) -> None:
        column = _cluster_columns(client)[COLUMN]

        assert (column["values"], column["value_labels"]) == (["-1", "0", "1"], {"-1": "Noise"})

    def test_a_run_without_noise_names_no_value(self, library: Path, client: TestClient) -> None:
        Dataset.find(DATASET_ID, library).write_clustering(
            RUN.model_copy(update={"run_id": "job-2"}), {"r1": 0, "r2": 1}
        )

        column = _cluster_columns(client)["record_clusters.job-2"]

        assert (column["values"], column.get("value_labels")) == (["0", "1"], None)

    def test_a_page_shows_each_records_group(self, client: TestClient) -> None:
        page = _records(client)

        assert {item["id"]: item["computed_values"] for item in page["items"]} == {
            "r1": {COLUMN: 1},
            "r2": {COLUMN: 0},
            "r3": {COLUMN: 0},
            "r4": {COLUMN: NOISE_CLUSTER},
            "r5": {COLUMN: None},
        }

    def test_runs_appear_in_the_order_they_ran(self, library: Path, client: TestClient) -> None:
        Dataset.find(DATASET_ID, library).write_clustering(RUN.model_copy(update={"run_id": "job-0"}), GROUPS)

        assert list(_cluster_columns(client)) == [COLUMN, "record_clusters.job-0"]

    def test_a_clusters_table_that_cannot_be_read_offers_nothing_and_fails_nothing(
        self, library: Path, client: TestClient
    ) -> None:
        shutil.rmtree(library / DATASET_ID / "db" / "record_clusters.lance")

        page = _records(client)

        assert _cluster_columns(client) == {}
        assert [item.get("computed_values") for item in page["items"]] == [None] * len(RECORDS)


@pytest.mark.usefixtures("clustered")
class TestDescribedToAClient:
    """The routes that describe a dataset leave its clusters out: no client reads their rows."""

    def test_its_tables(self, client: TestClient) -> None:
        dataset = client.get(f"/datasets/{DATASET_ID}").json()

        assert "record_clusters" not in dataset["tables"]

    def test_its_description(self, client: TestClient) -> None:
        info = client.get(f"/datasets/{DATASET_ID}/info").json()

        assert {"record_clusters", "clusterings"}.isdisjoint(info)


class TestBeforeAnyClustering:
    def test_no_column(self, client: TestClient) -> None:
        assert _cluster_columns(client) == {}

    def test_a_filter_on_a_run_is_refused(self, client: TestClient) -> None:
        response = client.get(f"/datasets/{DATASET_ID}/records", params={"filter": f"{COLUMN}:eq:0"})

        assert response.status_code == 400
        assert "Unknown clustering" in response.json()["detail"]


@pytest.mark.usefixtures("clustered")
class TestSortAndFilter:
    def test_sorted_on_a_run_noise_first_and_records_it_did_not_group_last(self, client: TestClient) -> None:
        assert _ids(_records(client, sort=COLUMN)) == ["r4", "r2", "r3", "r1", "r5"]

    def test_filtered_on_a_group(self, client: TestClient) -> None:
        page = _records(client, filter=f"{COLUMN}:eq:0")

        assert (_ids(page), page["total"]) == (["r2", "r3"], 2)

    def test_filtered_on_noise(self, client: TestClient) -> None:
        assert _ids(_records(client, filter=f"{COLUMN}:eq:{NOISE_CLUSTER}")) == ["r4"]

    def test_filtered_on_a_group_and_a_column_of_the_records(self, client: TestClient) -> None:
        page = _records(client, filter=[f"{COLUMN}:in:0,1", "split:eq:train"], sort=COLUMN, order="desc")

        assert _ids(page) == ["r1", "r2", "r3"]

    def test_with_a_raw_where_clause_malformed(self, client: TestClient) -> None:
        response = client.get(f"/datasets/{DATASET_ID}/records", params={"sort": COLUMN, "where": "split = = 'x'"})

        assert response.status_code == 400

    def test_a_group_narrows_the_records_a_search_ranks(self, library: Path) -> None:
        dataset = Dataset.find(DATASET_ID, library)

        assert sorted(_prefilter_record_ids(dataset, [f"{COLUMN}:eq:0"], None)) == ["r2", "r3"]

    def test_neighbors_in_an_order_on_a_run(self, client: TestClient) -> None:
        response = client.get(
            f"/datasets/{DATASET_ID}/records/r2/neighbors", params={"sort": COLUMN, "filter": f"{COLUMN}:gte:0"}
        )

        assert response.json() == {"prev": None, "next": "r3", "position": 1, "total": 3}
