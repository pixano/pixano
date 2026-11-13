# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""`GET /datasets/{id}/overview`: the overview of the records the explorer's filters keep."""

from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.routers import overview as overview_router
from pixano.api.settings import Settings, get_settings
from pixano.datasets import Dataset, DatasetInfo
from pixano.datasets.queries.computed_columns import InvalidRecordFilter
from pixano.datasets.statistic_choices import default_statistics
from pixano.schemas import Record
from pixano.statistics.definitions import define_statistic
from pixano.statistics.registry import StatisticRegistry
from tests.fixtures.overview import OVERVIEW_DATASET_ID, ClassedEntity, build_overview_dataset


OVERVIEW = f"/datasets/{OVERVIEW_DATASET_ID}/overview"


def _client(tmp_path: Path, raise_server_exceptions: bool = True) -> TestClient:
    library = tmp_path / "library"
    build_overview_dataset(library)
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    settings = Settings(library_dir=str(library), models_dir=str(models_dir))

    @lru_cache
    def settings_override() -> Settings:
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = settings_override
    return TestClient(app, raise_server_exceptions=raise_server_exceptions)


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    return _client(tmp_path)


def _overview(client: TestClient, **params) -> dict:  # noqa: ANN003 - query parameters
    response = client.get(OVERVIEW, params=params)
    assert response.status_code == 200, response.text
    return response.json()


def _card(overview: dict, card_id: str) -> dict:
    return next(card for card in overview["cards"] if card["id"] == card_id)


class TestTheOverview:
    def test_shows_every_record_and_its_cards(self, client: TestClient) -> None:
        overview = _overview(client)

        assert (overview["records"], overview["total_records"], overview["splits"]) == (4, 4, ["test", "train", "val"])
        weather = _card(overview, "field:weather")
        assert {value["value"]: value["count"] for value in weather["values"]} == {"rain": 2, "sun": 1}
        assert overview["statistics_to_compute"] == []

    def test_keeps_the_records_the_explorers_filters_keep(self, client: TestClient) -> None:
        overview = _overview(client, filter=["split:eq:train"])

        assert overview["records"] == 2
        assert {value["value"] for value in _card(overview, "object:class")["values"]} == {"dog", "cat"}

    def test_keeps_them_through_a_filter_on_a_statistic(self, client: TestClient) -> None:
        overview = _overview(client, filter=["record_statistics.entity_count:gte:2"])

        assert overview["records"] == 1

    def test_a_card_of_a_column_filtered_keeps_every_bar_and_tells_those_its_filter_keeps(
        self, client: TestClient
    ) -> None:
        overview = _overview(client, filter=["record_statistics.entity_count:gte:2", "split:eq:train"])

        objects = _card(overview, "statistic:entity_count")
        assert objects["filtered"] is True
        assert [(bar["start"], bar["count"], bar["selected"]) for bar in objects["bars"]] == [(1, 1, 0), (2, 1, 1)]
        split = _card(overview, "field:split")
        assert {value["value"]: value["selected"] for value in split["values"]} == {"train": 1}
        assert _card(overview, "field:weather")["population"] == 1

    def test_counts_per_split_when_asked(self, client: TestClient) -> None:
        overview = _overview(client, by_split="true")

        assert overview["splits"] == ["test", "train", "val"]
        assert _card(overview, "object:class")["counted_by_split"] == {"train": 3, "val": 1}

    @pytest.mark.parametrize(
        "params",
        [{"filter": ["nowhere:eq:1"]}, {"filter": ["record_statistics.nowhere:gte:1"]}, {"where": "nowhere = = 1"}],
        ids=["unknown column", "unknown statistic", "malformed raw clause"],
    )
    def test_refuses_a_filter_it_cannot_read(self, client: TestClient, params: dict) -> None:
        assert client.get(OVERVIEW, params=params).status_code == 400

    def test_blames_the_request_for_a_failed_read_only_when_a_raw_clause_may_be_at_fault(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A read failing for its own reasons is the server's: its message, which may name a path, stays in it."""

        def failing(*_args: object, **_kwargs: object) -> None:
            raise InvalidRecordFilter("/data/library/overview_ds/records.lance: no such file")

        monkeypatch.setattr(overview_router, "dataset_overview", failing)
        client = _client(tmp_path, raise_server_exceptions=False)

        assert client.get(OVERVIEW, params={"where": "split = 'train'"}).status_code == 400
        unfiltered = client.get(OVERVIEW)
        assert unfiltered.status_code == 500 and "records.lance" not in unfiltered.text

    def test_a_default_statistic_to_compute_keeps_the_label_the_library_gave_it(self, tmp_path: Path) -> None:
        client = _client(tmp_path)
        library = tmp_path / "library"
        fresh = Dataset.create(
            library / "fresh", DatasetInfo(id="fresh", name="fresh", record=Record, entity=ClassedEntity)
        )
        fresh.add_records({"records": [Record(id="r1")]})
        fresh.add_data("entities", [ClassedEntity(id="e1", record_id="r1")], raise_or_warn="none")
        (objects,) = default_statistics(fresh)
        StatisticRegistry(library).add(define_statistic(objects.choices, label="Animals"))

        response = client.get("/datasets/fresh/overview")

        assert response.status_code == 200, response.text
        assert [statistic["label"] for statistic in response.json()["statistics_to_compute"]] == ["Animals"]
