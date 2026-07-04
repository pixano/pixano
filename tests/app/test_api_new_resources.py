# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import tempfile
from functools import lru_cache
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.settings import Settings, get_settings
from pixano.datasets import Dataset, DatasetInfo
from pixano.schemas import Classification, Entity, Image, Record, Relation


DATASET_ID = "classified_ds"


@pytest.fixture()
def client_with_classification_dataset() -> TestClient:
    library_dir = Path(tempfile.mkdtemp())
    info = DatasetInfo(
        id=DATASET_ID,
        name=DATASET_ID,
        record=Record,
        entity=Entity,
        classification=Classification,
        relation=Relation,
        views={"image": Image},
    )
    dataset = Dataset.create(library_dir / DATASET_ID, info)
    dataset.merge_records(
        {"records": Record(id="rec1"), "entities": Entity(id="ent1", record_id="rec1")},
        check_integrity="none",
    )

    settings = Settings(library_dir=str(library_dir), models_dir=str(library_dir))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override
    return TestClient(app)


def _crud_cycle(client: TestClient, path: str, create_payload: dict, update_payload: dict) -> None:
    base = f"/datasets/{DATASET_ID}/{path}"
    row_id = create_payload["id"]

    created = client.post(base, json=create_payload)
    assert created.status_code == 201, created.text

    fetched = client.get(f"{base}/{row_id}")
    assert fetched.status_code == 200, fetched.text
    for key, value in create_payload.items():
        if not isinstance(value, dict):
            assert fetched.json()[key] == value

    listed = client.get(base)
    assert listed.status_code == 200
    assert listed.json()["total"] == 1

    updated = client.put(f"{base}/{row_id}", json=update_payload)
    assert updated.status_code == 200, updated.text
    for key, value in update_payload.items():
        if not isinstance(value, dict):
            assert updated.json()[key] == value

    deleted = client.delete(f"{base}/{row_id}")
    assert deleted.status_code == 204
    assert client.get(f"{base}/{row_id}").status_code == 404


class TestNewResourceRouters:
    def test_classifications_crud(self, client_with_classification_dataset: TestClient):
        _crud_cycle(
            client_with_classification_dataset,
            "classifications",
            {
                "id": "cls1",
                "record_id": "rec1",
                "entity_id": "ent1",
                "labels": ["car"],
                "confidences": [0.9],
            },
            {"labels": ["truck"], "confidences": [0.7]},
        )

    def test_relations_crud(self, client_with_classification_dataset: TestClient):
        _crud_cycle(
            client_with_classification_dataset,
            "relations",
            {
                "id": "rel1",
                "record_id": "rec1",
                "entity_id": "ent1",
                "predicate": "left_of",
            },
            {"predicate": "right_of"},
        )

    def test_dataset_info_includes_new_slots(self, client_with_classification_dataset: TestClient):
        response = client_with_classification_dataset.get(f"/datasets/{DATASET_ID}/info")
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["classification"] == {"base": "Classification", "fields": {}}
        assert payload["relation"] == {"base": "Relation", "fields": {}}
