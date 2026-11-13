# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The explorer on the statistics a dataset computed: its columns, its sorts, its filters, its neighbors."""

import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import create_model

from pixano.api.main import create_app
from pixano.api.routers.explorer import _prefilter_record_ids
from pixano.api.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.features import BBox, Image, Record
from pixano.statistics.computed import ComputedStatistic
from pixano.statistics.definitions import (
    StatisticAggregation,
    StatisticChoices,
    StatisticLevel,
    StatisticMeasure,
    define_statistic,
)


DATASET_ID = "explorer_statistics"
SplitRecord = create_model("SplitRecord", __base__=Record, rank=(int, 0))

BOX_COUNT = define_statistic(
    StatisticChoices(level=StatisticLevel.RECORD, element="bbox", measure=StatisticMeasure.COUNT), label="Boxes"
)
MEAN_BOX_AREA = define_statistic(
    StatisticChoices(
        level=StatisticLevel.RECORD,
        element="bbox",
        measure=StatisticMeasure.AREA,
        aggregation=StatisticAggregation.MEAN,
    )
)
MODEL_BOX_COUNT = define_statistic(
    StatisticChoices(level=StatisticLevel.RECORD, element="bbox", measure=StatisticMeasure.COUNT, origin="model")
)
BOXES_PER_OBJECT = define_statistic(
    StatisticChoices(level=StatisticLevel.ENTITY, element="bbox", measure=StatisticMeasure.COUNT)
)
COUNT = f"record_statistics.{BOX_COUNT.name}"
AREA = f"record_statistics.{MEAN_BOX_AREA.name}"

#: r1 to r5, their split, and their statistics: r4's are none and r5 has no row.
SPLITS = {"r1": "train", "r2": "train", "r3": "val", "r4": "val", "r5": "train"}
VALUES = {
    "r1": {BOX_COUNT.name: 3, MEAN_BOX_AREA.name: 10.5},
    "r2": {BOX_COUNT.name: 1, MEAN_BOX_AREA.name: 4.0},
    "r3": {BOX_COUNT.name: 2, MEAN_BOX_AREA.name: None},
    "r4": {BOX_COUNT.name: None, MEAN_BOX_AREA.name: None},
}


def _computed(definition) -> ComputedStatistic:  # noqa: ANN001 - a StatisticDefinition
    return ComputedStatistic(
        definition=definition, job_id="job-1", computed_at=datetime(2026, 11, 4, tzinfo=timezone.utc)
    )


@pytest.fixture
def library(tmp_path: Path) -> Path:
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID,
        DatasetInfo(id=DATASET_ID, name=DATASET_ID, record=SplitRecord, bbox=BBox, views={"image": Image}),
    )
    dataset.add_records(
        {"records": [SplitRecord(id=record, split=split, rank=n) for n, (record, split) in enumerate(SPLITS.items())]}
    )
    return library


@pytest.fixture
def computed(library: Path) -> Dataset:
    """The dataset once it computed the number of boxes and their mean area per record."""
    dataset = Dataset.find(DATASET_ID, library)
    columns = {BOX_COUNT.name: "int", MEAN_BOX_AREA.name: "float"}
    dataset.ensure_statistic_columns(StatisticLevel.RECORD, columns)
    dataset.write_statistic_values(
        StatisticLevel.RECORD,
        [{"id": record, "record_id": record, **values} for record, values in VALUES.items()],
        columns,
    )
    dataset.ensure_statistic_columns(StatisticLevel.ENTITY, {BOXES_PER_OBJECT.name: "int"})
    dataset.record_computed_statistics([_computed(BOX_COUNT), _computed(MEAN_BOX_AREA), _computed(BOXES_PER_OBJECT)])
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


@pytest.mark.usefixtures("computed")
class TestColumns:
    def test_each_statistic_computed_per_record_is_a_column_named_by_its_label(self, client: TestClient) -> None:
        columns = {
            column["name"]: column
            for column in client.get(f"/datasets/{DATASET_ID}/filters").json()["columns"]
            if column["table"] == "record_statistics"
        }

        assert set(columns) == {COUNT, AREA}
        assert {key: columns[COUNT][key] for key in ("label", "type", "source", "sortable", "filterable")} == {
            "label": "Boxes",
            "type": "int",
            "source": "statistics",
            "sortable": True,
            "filterable": True,
        }
        assert (columns[AREA]["label"], columns[AREA]["unit"], columns[AREA]["type"]) == (
            MEAN_BOX_AREA.label,
            "px²",
            "float",
        )

    def test_a_page_shows_the_values_of_each_record_named_as_the_columns(self, client: TestClient) -> None:
        page = _records(client)

        assert {item["id"]: item["computed_values"] for item in page["items"]} == {
            "r1": {COUNT: 3, AREA: 10.5},
            "r2": {COUNT: 1, AREA: 4.0},
            "r3": {COUNT: 2, AREA: None},
            "r4": {COUNT: None, AREA: None},
            "r5": {COUNT: None, AREA: None},
        }

    def test_a_statistic_recorded_whose_column_is_missing_is_no_column(
        self, library: Path, client: TestClient
    ) -> None:
        Dataset.find(DATASET_ID, library).record_computed_statistics([_computed(MODEL_BOX_COUNT)])

        columns = client.get(f"/datasets/{DATASET_ID}/filters").json()["columns"]

        assert f"record_statistics.{MODEL_BOX_COUNT.name}" not in {column["name"] for column in columns}
        assert set(_records(client)["items"][0]["computed_values"]) == {COUNT, AREA}

    def test_a_statistics_table_that_cannot_be_read_offers_nothing_and_fails_nothing(
        self, library: Path, client: TestClient
    ) -> None:
        shutil.rmtree(library / DATASET_ID / "db" / "record_statistics.lance")

        columns = client.get(f"/datasets/{DATASET_ID}/filters").json()["columns"]

        assert [column["name"] for column in columns if column["table"] == "record_statistics"] == []
        assert len(_records(client)["items"]) == len(SPLITS)


class TestBeforeAnyComputation:
    def test_no_column_and_no_values(self, client: TestClient) -> None:
        columns = client.get(f"/datasets/{DATASET_ID}/filters").json()["columns"]

        assert [column for column in columns if column["table"] != "records"] == []
        assert all("computed_values" not in item for item in _records(client)["items"])

    def test_a_filter_on_a_statistic_is_refused(self, client: TestClient) -> None:
        response = client.get(f"/datasets/{DATASET_ID}/records", params={"filter": f"{COUNT}:gte:1"})

        assert response.status_code == 400
        assert "Unknown statistic" in response.json()["detail"]


@pytest.mark.usefixtures("computed")
class TestSort:
    def test_on_a_statistic_records_without_come_last(self, client: TestClient) -> None:
        assert _ids(_records(client, sort=COUNT, order="desc")) == ["r1", "r3", "r2", "r4", "r5"]
        assert _ids(_records(client, sort=COUNT)) == ["r2", "r3", "r1", "r4", "r5"]

    def test_pages_follow_one_another(self, client: TestClient) -> None:
        pages = [_records(client, sort=AREA, order="desc", limit=2, offset=offset) for offset in (0, 2, 4)]

        assert [_ids(page) for page in pages] == [["r1", "r2"], ["r3", "r4"], ["r5"]]
        assert {page["total"] for page in pages} == {5}

    def test_on_a_column_of_the_records_as_before(self, client: TestClient) -> None:
        assert _ids(_records(client, sort="rank", order="desc")) == ["r5", "r4", "r3", "r2", "r1"]

    def test_on_identifiers_descending_with_a_statistic_filtered_on(self, client: TestClient) -> None:
        page = _records(client, sort="id", order="desc", filter=f"{COUNT}:gte:1")

        assert _ids(page) == ["r3", "r2", "r1"]

    def test_on_a_column_of_the_records_with_a_statistic_filtered_on(self, client: TestClient) -> None:
        page = _records(client, sort="rank", order="desc", filter=f"{COUNT}:lte:2")

        assert (_ids(page), page["total"]) == (["r3", "r2"], 2)

    def test_a_page_past_the_end(self, client: TestClient) -> None:
        page = _records(client, sort=COUNT, offset=10)

        assert (page["items"], page["total"]) == ([], 5)


@pytest.mark.usefixtures("computed")
class TestFilter:
    def test_on_a_statistic(self, client: TestClient) -> None:
        page = _records(client, filter=f"{COUNT}:gte:2")

        assert (_ids(page), page["total"]) == (["r1", "r3"], 2)

    def test_on_a_statistic_and_on_a_column_of_the_records(self, client: TestClient) -> None:
        page = _records(client, filter=[f"{COUNT}:gte:1", "split:eq:train"], sort=COUNT)

        assert (_ids(page), page["total"]) == (["r2", "r1"], 2)

    @pytest.mark.parametrize(
        "token",
        [f"{COUNT}:contains:1", "record_statistics.mask_count:gt:1"],
        ids=["an operator its type does not take", "a statistic not computed"],
    )
    def test_refused(self, client: TestClient, token: str) -> None:
        assert client.get(f"/datasets/{DATASET_ID}/records", params={"filter": token}).status_code == 400

    def test_with_a_raw_where_clause_malformed(self, client: TestClient) -> None:
        response = client.get(f"/datasets/{DATASET_ID}/records", params={"sort": COUNT, "where": "split = = 'x'"})

        assert response.status_code == 400


@pytest.mark.usefixtures("computed")
class TestNeighbors:
    def test_in_an_order_on_a_statistic(self, client: TestClient) -> None:
        response = client.get(
            f"/datasets/{DATASET_ID}/records/r3/neighbors",
            params={"sort": COUNT, "order": "desc", "filter": "split:in:train,val"},
        )

        assert response.json() == {"prev": "r1", "next": "r2", "position": 2, "total": 5}

    def test_among_the_records_a_statistic_filters(self, client: TestClient) -> None:
        response = client.get(f"/datasets/{DATASET_ID}/records/r2/neighbors", params={"filter": f"{COUNT}:lte:2"})

        assert response.json() == {"prev": None, "next": "r3", "position": 1, "total": 2}


@pytest.mark.usefixtures("computed")
class TestSearchPrefilter:
    def test_a_statistic_narrows_the_records_searched(self, library: Path) -> None:
        dataset = Dataset.find(DATASET_ID, library)

        assert _prefilter_record_ids(dataset, [f"{COUNT}:gte:2"], None) == ["r1", "r3"]
        assert _prefilter_record_ids(dataset, [f"{COUNT}:gte:1"], "split = 'train'") == ["r1", "r2"]
