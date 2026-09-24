# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""The API facing a schema another process changed under it.

A detection job gives a dataset's entities a `category` field while the API has the dataset
open. The API must see the field at once — to show the classes, and to accept entities that
carry one — not at the end of the job.
"""

import tempfile
from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.features import BBox, Entity, Image, Record


DATASET_ID = "entity_field_added_elsewhere"
BASE = f"/datasets/{DATASET_ID}"


@pytest.fixture
def dataset() -> Dataset:
    target = Path(tempfile.mkdtemp()) / DATASET_ID
    created = Dataset.create(
        target,
        DatasetInfo(id=DATASET_ID, name=DATASET_ID, record=Record, entity=Entity, bbox=BBox, views={"image": Image}),
    )
    created.add_records({"records": [Record(id="r1")]})
    created.add_data("entities", [Entity(id="e1", record_id="r1")], raise_or_warn="none")
    return created


@pytest.fixture
def client(dataset: Dataset) -> TestClient:
    models_dir = Path(tempfile.mkdtemp()) / "models"
    models_dir.mkdir()
    settings = Settings(library_dir=str(dataset.path.parent), models_dir=str(models_dir))

    @lru_cache
    def settings_override() -> Settings:
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = settings_override
    return TestClient(app)


def _worker_adds_the_field(dataset: Dataset) -> None:
    """What the worker does, in its own process: its own `Dataset`, and no hook reaching the API."""
    hooks = Dataset._cache_invalidation_hooks
    Dataset._cache_invalidation_hooks = []
    try:
        Dataset(dataset.path).ensure_entity_text_field("category")
    finally:
        Dataset._cache_invalidation_hooks = hooks


class TestEntityFieldAddedElsewhere:
    def test_the_new_field_is_read_at_once(self, dataset: Dataset, client: TestClient) -> None:
        assert client.get(f"{BASE}/entities").status_code == 200  # the API now holds the dataset

        _worker_adds_the_field(dataset)
        Dataset(dataset.path).update_data(
            "entities", [Dataset(dataset.path).info.entity(id="e1", record_id="r1", category="car")]
        )

        items = client.get(f"{BASE}/entities").json()["items"]
        assert [item.get("category") for item in items] == ["car"]

    def test_an_entity_can_be_created_meanwhile(self, dataset: Dataset, client: TestClient) -> None:
        """Independent review of lot 2, B3: `Append with different schema`, a 500, for the whole job."""
        assert client.get(f"{BASE}/entities").status_code == 200

        _worker_adds_the_field(dataset)
        resp = client.post(f"{BASE}/entities", json={"id": "e2", "record_id": "r1", "category": "dog"})

        assert resp.status_code in (200, 201), resp.text
        assert {entity.id: entity.category for entity in Dataset(dataset.path).get_data("entities")} == {
            "e1": "",
            "e2": "dog",
        }

    def test_an_entity_can_be_updated_meanwhile(self, dataset: Dataset, client: TestClient) -> None:
        assert client.get(f"{BASE}/entities").status_code == 200

        _worker_adds_the_field(dataset)
        resp = client.put(f"{BASE}/entities/e1", json={"category": "cat"})

        assert resp.status_code == 200, resp.text
        assert Dataset(dataset.path).get_data("entities", ids=["e1"])[0].category == "cat"
