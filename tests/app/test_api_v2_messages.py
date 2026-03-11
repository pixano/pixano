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
from pixano.datasets.builders.dataset_builder import DatasetBuilder
from pixano.datasets.dataset import Dataset, DatasetInfo
from pixano.datasets.workspaces import WorkspaceType
from pixano.features import Entity, Image, Message, Record


def _make_client(dataset: Dataset) -> TestClient:
    tmp = Path(tempfile.mkdtemp())
    models_dir = tmp / "models"
    models_dir.mkdir()

    settings = Settings(
        library_dir=str(dataset.path.parent),
        models_dir=str(models_dir),
    )

    @lru_cache
    def get_settings_override():
        return settings

    app = create_app(settings)
    app.dependency_overrides[get_settings] = get_settings_override
    return TestClient(app)


DATASET_ID = "message_dataset"


class MessageDatasetBuilder(DatasetBuilder):
    def __init__(self, target_dir: Path, info: DatasetInfo):
        base = info.model_dump(include={"id", "name", "description", "size", "preview", "workspace", "storage_mode"})
        info = DatasetInfo(
            **base,
            record=Record,
            views={"image": Image},
            entity=Entity,
            message=Message,
        )
        super().__init__(target_dir=target_dir, info=info)

    def generate_data(self):
        record_id = "record_0"
        image = Image(
            id="image_0",
            record_id=record_id,
            logical_name="image",
            uri="image_0.jpg",
            width=640,
            height=480,
            format="jpg",
        )
        entity = Entity(id="entity_0", record_id=record_id)
        message = Message(
            id="message_0",
            record_id=record_id,
            source_type="ground_truth",
            source_name="Ground Truth",
            view_id="image",
            conversation_id="conv_0",
            number=0,
            user="human",
            type="QUESTION",
            content="How many objects are visible?",
            choices=[],
            question_type="OPEN",
            entity_ids=["entity_0"],
        )

        yield {
            self.record_table_name: self.record_schema(id=record_id, split="train"),
            "images": image,
            "entities": [entity],
            "messages": [message],
        }


@pytest.fixture(scope="module")
def message_dataset() -> Dataset:
    tmp = Path(tempfile.mkdtemp())
    target = tmp / DATASET_ID
    info = DatasetInfo(
        id=DATASET_ID,
        name=DATASET_ID,
        description="Dataset for v2 messages API testing",
        workspace=WorkspaceType.IMAGE_VQA,
    )
    builder = MessageDatasetBuilder(target_dir=target, info=info)
    return builder.build(mode="overwrite", check_integrity="none")


@pytest.fixture(scope="module")
def message_client(message_dataset: Dataset) -> TestClient:
    return _make_client(message_dataset)


BASE = f"/datasets/{DATASET_ID}/messages"
CONVERSATIONS_BASE = f"/datasets/{DATASET_ID}/conversations"


def test_list_messages(message_client: TestClient):
    resp = message_client.get(BASE)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["conversation_id"] == "conv_0"
    assert body["items"][0]["entity_ids"] == ["entity_0"]


def test_list_conversations(message_client: TestClient):
    resp = message_client.get(CONVERSATIONS_BASE)
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 1
    assert body["items"][0]["conversation_id"] == "conv_0"
    assert len(body["items"][0]["messages"]) >= 1
    assert all(message["conversation_id"] == "conv_0" for message in body["items"][0]["messages"])


def test_get_conversation(message_client: TestClient):
    resp = message_client.get(f"{CONVERSATIONS_BASE}/conv_0")
    assert resp.status_code == 200
    body = resp.json()
    assert body["conversation_id"] == "conv_0"
    assert [message["number"] for message in body["messages"]] == sorted(
        message["number"] for message in body["messages"]
    )


def test_create_message(message_client: TestClient):
    resp = message_client.post(
        BASE,
        json={
            "id": "message_1",
            "record_id": "record_0",
            "source_type": "ground_truth",
            "source_name": "Ground Truth",
            "view_id": "image",
            "conversation_id": "conv_0",
            "number": 1,
            "user": "model",
            "type": "ANSWER",
            "content": "One object is referenced.",
            "choices": [],
            "entity_ids": ["entity_0"],
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["id"] == "message_1"
    assert body["type"] == "ANSWER"
    assert "attributes" not in body


def test_get_missing_conversation_returns_404(message_client: TestClient):
    resp = message_client.get(f"{CONVERSATIONS_BASE}/missing")
    assert resp.status_code == 404


def test_create_message_rejects_unknown_referenced_entity(message_client: TestClient):
    resp = message_client.post(
        BASE,
        json={
            "id": "message_invalid",
            "record_id": "record_0",
            "source_type": "ground_truth",
            "source_name": "Ground Truth",
            "view_id": "image",
            "conversation_id": "conv_1",
            "number": 0,
            "user": "human",
            "type": "QUESTION",
            "content": "What is this object?",
            "choices": [],
            "question_type": "OPEN",
            "entity_ids": ["does_not_exist"],
        },
    )
    assert resp.status_code == 400
    assert "does_not_exist" in resp.json()["detail"]


def test_create_question_requires_question_type(message_client: TestClient):
    resp = message_client.post(
        BASE,
        json={
            "id": "message_missing_question_type",
            "record_id": "record_0",
            "source_type": "ground_truth",
            "source_name": "Ground Truth",
            "view_id": "image",
            "conversation_id": "conv_2",
            "number": 0,
            "user": "human",
            "type": "QUESTION",
            "content": "What is shown?",
            "choices": [],
            "entity_ids": [],
        },
    )
    assert resp.status_code == 400
