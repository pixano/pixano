# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

from unittest.mock import patch

from fastapi.applications import FastAPI
from fastapi.encoders import jsonable_encoder
from starlette.testclient import TestClient

from pixano.app.models import AnnotationModel, EntityModel, TableInfo
from pixano.app.settings import Settings
from pixano.datasets.dataset import Dataset
from pixano.features import Conversation, Message, SchemaGroup


@patch("pixano.app.routers.inference.conditional_generation.text_image_conditional_generation")
def test_call_text_image_conditional_generation(
    mock_text_image_conditional_generation,
    app_and_settings_with_client_copy: tuple[FastAPI, Settings, TestClient],
    dataset_vqa: Dataset,
):
    app, settings, client = app_and_settings_with_client_copy

    conversation = EntityModel.from_row(
        Conversation(kind="test"),
        TableInfo(name="conversations", group=SchemaGroup.ENTITY.value, base_schema="Conversation"),
    )

    messages = [
        AnnotationModel.from_row(
            Message(content="test", number=0, user="system", type="SYSTEM"),
            TableInfo(name="messages", group=SchemaGroup.ANNOTATION.value, base_schema="Message"),
        ),
        AnnotationModel.from_row(
            Message(content="test", number=1, user="human", type="QUESTION"),
            TableInfo(name="messages", group=SchemaGroup.ANNOTATION.value, base_schema="Message"),
        ),
    ]

    expected_output = AnnotationModel.from_row(
        Message(content="test", number=1, user="pixano", type="ANSWER"),
        TableInfo(name="messages", group=SchemaGroup.ANNOTATION.value, base_schema="Message"),
    )
    mock_text_image_conditional_generation.return_value = Message(
        content="test", number=1, user="pixano", type="ANSWER"
    )

    json = jsonable_encoder(
        {
            "dataset_id": "dataset_vqa",
            "conversation": conversation,
            "messages": messages,
            "model": "model",
        }
    )

    url = "/inference/tasks/conditional_generation/text-image"

    response = client.post(url, json=json)
    assert response.status_code == 200
    assert expected_output.to_row(dataset_vqa).model_dump(
        exclude="id", exclude_timestamps=True
    ) == AnnotationModel.model_validate(response.json()).to_row(dataset_vqa).model_dump(
        exclude="id", exclude_timestamps=True
    )

    dataset = Dataset.find("dataset_vqa", directory=settings.library_dir, media_dir=settings.media_dir)
    sources = dataset.get_data("source", limit=10)
    assert len(sources) == 3

    # Execute again to check the source is not created again.
    response = client.post(url, json=json)
    assert response.status_code == 200
    assert expected_output.to_row(dataset_vqa).model_dump(
        exclude="id", exclude_timestamps=True
    ) == AnnotationModel.model_validate(response.json()).to_row(dataset_vqa).model_dump(
        exclude="id", exclude_timestamps=True
    )

    dataset = Dataset.find("dataset_vqa", directory=settings.library_dir, media_dir=settings.media_dir)
    sources = dataset.get_data("source", limit=10)
    assert len(sources) == 3


def test_call_text_image_conditional_generation_error(
    app_and_settings_with_client_copy: tuple[FastAPI, Settings, TestClient],
):
    app, settings, client = app_and_settings_with_client_copy
    url = "/inference/tasks/conditional_generation/text-image"

    json = jsonable_encoder(
        {
            "dataset_id": "dataset_vqa",
            "conversation": EntityModel.from_row(
                Conversation(kind="test"),
                TableInfo(name="messages", group=SchemaGroup.ENTITY.value, base_schema="Conversation"),
            ),
            "messages": [],
            "model": "model",
        }
    )

    response = client.post(url, json=json)
    assert response.status_code == 400
    assert response.json() == {"detail": "Conversation must be a conversation."}

    json = jsonable_encoder(
        {
            "dataset_id": "dataset_vqa",
            "conversation": EntityModel.from_row(
                Conversation(kind="test"),
                TableInfo(name="conversations", group=SchemaGroup.ENTITY.value, base_schema="Conversation"),
            ),
            "messages": [
                AnnotationModel.from_row(
                    Message(content="test", number=0, user="system", type="SYSTEM"),
                    TableInfo(name="messages", group=SchemaGroup.ANNOTATION.value, base_schema="Message"),
                ),
                AnnotationModel.from_row(
                    Message(content="test", number=1, user="human", type="QUESTION"),
                    TableInfo(name="messages2", group=SchemaGroup.ANNOTATION.value, base_schema="Message"),
                ),
            ],
            "model": "model",
        }
    )

    response = client.post(url, json=json)
    assert response.status_code == 400
    assert response.json() == {"detail": "Only one table for messages is allowed."}

    json = jsonable_encoder(
        {
            "dataset_id": "dataset_vqa",
            "conversation": EntityModel.from_row(
                Conversation(kind="test"),
                TableInfo(name="conversations", group=SchemaGroup.ENTITY.value, base_schema="Conversation"),
            ),
            "messages": [
                AnnotationModel.from_row(
                    Message(content="test", number=0, user="system", type="SYSTEM"),
                    TableInfo(name="conversations", group=SchemaGroup.ANNOTATION.value, base_schema="Message"),
                ),
                AnnotationModel.from_row(
                    Message(content="test", number=1, user="human", type="QUESTION"),
                    TableInfo(name="conversations", group=SchemaGroup.ANNOTATION.value, base_schema="Message"),
                ),
            ],
            "model": "model",
        }
    )

    response = client.post(url, json=json)
    assert response.status_code == 400
    assert response.json() == {"detail": "Messages must be a message."}
