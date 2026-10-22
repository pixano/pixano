# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

"""An entity deleted only when no stored row names it.

`?prune_orphan_entity=true` on an annotation's delete or reassignment deletes the entity the
annotation named once nothing names it. The annotation interface sends it on both, since it sees
one record at a time: only the server sees every row that may name the entity.
"""

import tempfile
import threading
from functools import lru_cache
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from pixano.api.main import create_app
from pixano.api.service import BaseService
from pixano.api.settings import Settings, get_settings
from pixano.datasets import Dataset, DatasetInfo
from pixano.schemas import BBox, Classification, Entity, EntityDynamicState, Image, Message, Record, Relation


DATASET_ID = "conditional_delete_ds"
BASE = f"/datasets/{DATASET_ID}"
RECORD_ID = "rec1"
ENTITY_ID = "ent1"
OTHER_ENTITY_ID = "other"
PRUNE_ORPHAN_ENTITY = {"prune_orphan_entity": "true"}
HTTP_CONFLICT = 409

# One row of each kind that may name an entity, as the API creates it: (resource path, body).
NAMING_ROWS = {
    "box": (
        "bboxes",
        {
            "id": "box1",
            "record_id": RECORD_ID,
            "entity_id": ENTITY_ID,
            "coords": [0.0, 0.0, 0.1, 0.1],
            "format": "xywh",
            "is_normalized": True,
        },
    ),
    # Another annotation table: every table is asked, not only the boxes'.
    "classification": (
        "classifications",
        {"id": "cls1", "record_id": RECORD_ID, "entity_id": ENTITY_ID, "labels": ["car"], "confidences": [1.0]},
    ),
    "message_entity_list": (
        "messages",
        {
            "id": "msg1",
            "record_id": RECORD_ID,
            "view_id": "image",
            "conversation_id": "conv1",
            "number": 0,
            "user": "human",
            "type": "ANSWER",
            "content": "It is a car.",
            "entity_ids": [ENTITY_ID],
        },
    ),
    "child_entity": ("entities", {"id": "child1", "record_id": RECORD_ID, "parent_id": ENTITY_ID}),
    "entity_dynamic_state": (
        "entity-dynamic-states",
        {"id": "eds1", "record_id": RECORD_ID, "entity_id": ENTITY_ID},
    ),
}


@pytest.fixture()
def library() -> tuple[TestClient, Dataset]:
    """A dataset with one record and one entity no row names, and a client of its API."""
    library_dir = Path(tempfile.mkdtemp())
    info = DatasetInfo(
        id=DATASET_ID,
        name=DATASET_ID,
        record=Record,
        entity=Entity,
        entity_dynamic_state=EntityDynamicState,
        bbox=BBox,
        classification=Classification,
        message=Message,
        relation=Relation,
        views={"image": Image},
    )
    dataset = Dataset.create(library_dir / DATASET_ID, info)
    dataset.merge_records(
        {"records": Record(id=RECORD_ID), "entities": Entity(id=ENTITY_ID, record_id=RECORD_ID)},
        check_integrity="none",
    )

    settings = Settings(library_dir=str(library_dir), models_dir=str(library_dir))

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override
    return TestClient(app), dataset


def _entity_exists(client: TestClient, entity_id: str = ENTITY_ID) -> bool:
    return client.get(f"{BASE}/entities/{entity_id}").status_code == 200


# The box whose delete or reassignment may leave the entity unnamed: (resource path, body).
BOX_PATH, BOX = NAMING_ROWS["box"]


def _delete_the_box(client: TestClient) -> httpx.Response:
    """Delete the box naming the entity, as the annotation interface sends it."""
    return client.delete(f"{BASE}/{BOX_PATH}/{BOX['id']}", params=PRUNE_ORPHAN_ENTITY)


def _move_the_box_to_another_entity(client: TestClient) -> httpx.Response:
    """Reassign the box naming the entity to another one, as the annotation interface sends it."""
    created = client.post(f"{BASE}/entities", json={"id": OTHER_ENTITY_ID, "record_id": RECORD_ID})
    assert created.status_code == 201, created.text
    return client.put(
        f"{BASE}/{BOX_PATH}/{BOX['id']}",
        json={**BOX, "entity_id": OTHER_ENTITY_ID},
        params=PRUNE_ORPHAN_ENTITY,
    )


# Each gesture after which the box no longer names the entity, and the status it answers when stored.
PRUNING_GESTURES = {
    "delete": (_delete_the_box, 204),
    "reassignment": (_move_the_box_to_another_entity, 200),
}


def _name_the_entity_with_the_box(client: TestClient) -> None:
    created = client.post(f"{BASE}/{BOX_PATH}", json=BOX)
    assert created.status_code == 201, created.text


@pytest.mark.parametrize("gesture", list(PRUNING_GESTURES))
def test_pruning_deletes_an_entity_nothing_names_any_more(library, gesture: str):
    """The dataset holds a table of messages, which has no `entity_id` column: counting that
    column there failed the request with a 500 once the box's delete or update was stored."""
    client, _ = library
    send, stored_status = PRUNING_GESTURES[gesture]
    _name_the_entity_with_the_box(client)

    resp = send(client)

    assert resp.status_code == stored_status, resp.text
    assert not _entity_exists(client)


# An entity id that would end the check's string literal if it were not quoted.
ENTITY_ID_HOLDING_A_QUOTE = "o'brien"


@pytest.mark.parametrize("gesture", list(PRUNING_GESTURES))
def test_pruning_reads_an_entity_id_holding_a_quote(library, gesture: str):
    """The check quotes the id: unquoted, its quote ended the filter's string, which failed the
    request with a 500 once the box's delete or update was stored."""
    client, _ = library
    send, stored_status = PRUNING_GESTURES[gesture]
    created = client.post(f"{BASE}/entities", json={"id": ENTITY_ID_HOLDING_A_QUOTE, "record_id": RECORD_ID})
    assert created.status_code == 201, created.text
    named = client.post(f"{BASE}/{BOX_PATH}", json={**BOX, "entity_id": ENTITY_ID_HOLDING_A_QUOTE})
    assert named.status_code == 201, named.text

    resp = send(client)

    assert resp.status_code == stored_status, resp.text
    assert client.get(f"{BASE}/entities/{ENTITY_ID_HOLDING_A_QUOTE}").status_code == 404


@pytest.mark.parametrize("gesture", list(PRUNING_GESTURES))
@pytest.mark.parametrize("naming_row", [name for name in NAMING_ROWS if name != "box"])
def test_pruning_keeps_an_entity_another_row_names(library, gesture: str, naming_row: str):
    """A child entity, a dynamic state, a message's list or an annotation of another table still
    names the entity once the box leaves it: deleting it would leave that row naming nothing."""
    client, _ = library
    send, stored_status = PRUNING_GESTURES[gesture]
    path, body = NAMING_ROWS[naming_row]
    created = client.post(f"{BASE}/{path}", json=body)
    assert created.status_code == 201, created.text
    _name_the_entity_with_the_box(client)

    resp = send(client)

    assert resp.status_code == stored_status, resp.text
    assert _entity_exists(client)


@pytest.mark.parametrize("gesture", list(PRUNING_GESTURES))
@pytest.mark.parametrize("end", ["subject_id", "object_id"])
def test_pruning_keeps_an_entity_a_relation_end_names(library, gesture: str, end: str):
    """Stored by the Python API with its integrity check off (the REST API's check refuses it)."""
    client, dataset = library
    send, stored_status = PRUNING_GESTURES[gesture]
    relation = Relation(id="rel1", record_id=RECORD_ID, predicate="left_of", **{end: ENTITY_ID})
    dataset.add_data("relations", [relation], raise_or_warn="none")
    _name_the_entity_with_the_box(client)

    resp = send(client)

    assert resp.status_code == stored_status, resp.text
    assert _entity_exists(client)


@pytest.mark.parametrize("gesture", list(PRUNING_GESTURES))
def test_a_write_sent_between_the_prune_check_and_its_delete_is_refused_as_busy(library, monkeypatch, gesture: str):
    """The box's write, the check and the entity's delete hold one write lock: a classification
    naming the entity cannot land between the check and the delete, which would leave it naming a
    deleted entity."""
    client, _ = library
    send, stored_status = PRUNING_GESTURES[gesture]
    path, body = NAMING_ROWS["classification"]
    raced: dict[str, int] = {}
    check = BaseService._entity_is_named

    def check_then_race(self: BaseService, entity_id: str) -> bool:
        named = check(self, entity_id)

        def send_classification() -> None:
            raced["status"] = client.post(f"{BASE}/{path}", json=body).status_code

        writer = threading.Thread(target=send_classification)
        writer.start()
        writer.join()
        return named

    _name_the_entity_with_the_box(client)
    monkeypatch.setattr(BaseService, "_entity_is_named", check_then_race)

    resp = send(client)

    assert resp.status_code == stored_status, resp.text
    assert raced["status"] == HTTP_CONFLICT
    assert not _entity_exists(client)
    assert client.get(f"{BASE}/{path}/{body['id']}").status_code == 404
