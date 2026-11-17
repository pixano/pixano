# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The API of statistics: composing one for the library, and what a dataset offers and takes of them."""

from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import create_model

from pixano.api.main import create_app
from pixano.api.routers import statistics as statistics_router
from pixano.api.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.features import BBox, Entity, Image, Record
from pixano.statistics import definitions as definitions_module
from pixano.statistics.definitions import MAX_LABEL_LENGTH, StatisticMeasure


DATASET_ID = "statistics_api"
VocEntity = create_model("VocEntity", __base__=Entity, category=(str, ""))

BOX_COUNT = {"level": "record", "element": "bbox", "measure": "count"}
MASK_AREA = {"level": "record", "element": "mask", "measure": "area", "aggregation": "mean"}


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    library = tmp_path / "library"
    dataset = Dataset.create(
        library / DATASET_ID,
        DatasetInfo(
            id=DATASET_ID, name=DATASET_ID, record=Record, entity=VocEntity, bbox=BBox, views={"image": Image}
        ),
    )
    dataset.add_records({"records": [Record(id="r1")]})
    dataset.add_data("entities", [VocEntity(id="e1", record_id="r1", category="dog")], raise_or_warn="none")
    models_dir = tmp_path / "models"
    models_dir.mkdir()
    settings = Settings(library_dir=str(library), models_dir=str(models_dir))

    @lru_cache
    def settings_override() -> Settings:
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = settings_override
    statistics_router._registries.clear()
    return TestClient(app)


class TestComposeStatistic:
    def test_a_statistic_composed_is_added_to_the_library(self, client: TestClient) -> None:
        response = client.post("/statistics/definitions", json={"choices": BOX_COUNT, "label": "Boxes"})

        assert response.status_code == 201
        assert {key: response.json()[key] for key in ("name", "label", "unit", "value_type", "version")} == {
            "name": "bbox_count",
            "label": "Boxes",
            "unit": "",
            "value_type": "int",
            "version": 1,
        }
        assert [definition["name"] for definition in client.get("/statistics/definitions").json()] == ["bbox_count"]

    def test_composing_it_again_answers_the_one_there(self, client: TestClient) -> None:
        first = client.post("/statistics/definitions", json={"choices": BOX_COUNT, "label": "Boxes"}).json()

        again = client.post("/statistics/definitions", json={"choices": BOX_COUNT, "label": "Other"})

        assert again.status_code == 200
        assert again.json() == first

    def test_a_name_held_by_other_choices_gets_a_column_of_its_own(self, client: TestClient) -> None:
        upper = client.post(
            "/statistics/definitions",
            json={"choices": BOX_COUNT | {"attribute": {"field": "category", "value": "Dog"}}},
        )

        lower = client.post(
            "/statistics/definitions",
            json={"choices": BOX_COUNT | {"attribute": {"field": "category", "value": "dog"}}},
        )

        assert (upper.status_code, lower.status_code) == (201, 201)
        assert upper.json()["name"] != lower.json()["name"]

    @pytest.mark.parametrize(
        "body",
        [
            {"choices": BOX_COUNT | {"aggregation": "mean"}},
            {"choices": BOX_COUNT, "label": "x" * (MAX_LABEL_LENGTH + 1)},
            {"choices": BOX_COUNT, "labl": "a misspelt key"},
        ],
        ids=["meaningless choices", "a label too long", "an unknown key"],
    )
    def test_refused(self, client: TestClient, body: dict) -> None:
        assert client.post("/statistics/definitions", json=body).status_code == 422


class TestDatasetStatistics:
    def test_what_the_dataset_offers(self, client: TestClient) -> None:
        choices = client.get(f"/datasets/{DATASET_ID}/statistics/choices").json()

        assert [(element["element"], element["reviewable"]) for element in choices["elements"]] == [
            ("entity", False),
            ("bbox", True),
        ]
        assert choices["attributes"] == [
            {"field": "category", "type": "str", "values": ["dog"], "values_complete": True}
        ]
        assert choices["origins"] == ["model", "not_model"]
        assert choices["review_statuses"] == ["pending", "accepted"]

    def test_the_statistics_of_the_library_that_apply_to_it(self, client: TestClient) -> None:
        assert client.post("/statistics/definitions", json={"choices": BOX_COUNT}).status_code == 201
        assert client.post("/statistics/definitions", json={"choices": MASK_AREA}).status_code == 201

        applying = client.get(f"/datasets/{DATASET_ID}/statistics/definitions").json()

        assert [definition["name"] for definition in applying] == ["bbox_count"]

    def test_the_library_lists_the_statistics_still_computed(self, client: TestClient, monkeypatch) -> None:
        assert client.post("/statistics/definitions", json={"choices": BOX_COUNT}).status_code == 201
        monkeypatch.setitem(definitions_module.MEASURE_VERSIONS, StatisticMeasure.COUNT, 2)
        assert client.post("/statistics/definitions", json={"choices": BOX_COUNT}).status_code == 201

        listed = client.get("/statistics/definitions").json()

        assert [(definition["name"], definition["version"]) for definition in listed] == [("bbox_count_v2", 2)]

    def test_not_one_whose_measure_changed_since(self, client: TestClient, monkeypatch) -> None:
        assert client.post("/statistics/definitions", json={"choices": BOX_COUNT}).status_code == 201
        monkeypatch.setitem(definitions_module.MEASURE_VERSIONS, StatisticMeasure.COUNT, 2)

        assert client.get(f"/datasets/{DATASET_ID}/statistics/definitions").json() == []

    @pytest.mark.parametrize("route", ["choices", "definitions"])
    def test_an_unknown_dataset_is_not_found(self, client: TestClient, route: str) -> None:
        assert client.get(f"/datasets/nowhere/statistics/{route}").status_code == 404
