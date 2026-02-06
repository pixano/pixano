# =====================================
# Copyright: CEA-LIST/DIASI/SIALV/LVA
# Author : pixano@cea.fr
# License: CECILL-C
# =====================================

import os
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from fastapi.encoders import jsonable_encoder

from pixano.features import (
    BBox,
    Conversation,
    EntityRef,
    Image,
    ItemRef,
    Message,
    SchemaGroup,
    Source,
    SourceRef,
    ViewRef,
)
from pixano.inference.provider import InferenceProvider
from pixano.inference.text_image_conditional_generation import messages_to_prompt, text_image_conditional_generation
from pixano.inference.types import (
    TextImageConditionalGenerationOutput,
    TextImageConditionalGenerationResult,
    UsageInfo,
)


FILE_PATH = Path(os.path.dirname(os.path.realpath(__file__)))
ASSETS_PATH = FILE_PATH.parent / "assets"


@pytest.fixture(scope="module")
def item_ref() -> ItemRef:
    return ItemRef(id="item")


@pytest.fixture(scope="module")
def vqa_image_url(item_ref: ItemRef) -> Image:
    image = Image(
        id="image",
        item_ref=item_ref,
        url="http://www.fake_url.com/coco_dataset/image/val/000000000139.png",
        width=640,
        height=426,
        format="png",
    )
    image.table_name = "image"
    return image


@pytest.fixture(scope="module")
def vqa_image(item_ref: ItemRef) -> Image:
    image = Image(
        id="image",
        item_ref=item_ref,
        url="coco_dataset/image/val/000000000285.jpg",
        width=640,
        height=426,
        format="jpeg",
    )
    image.table_name = "image"
    return image


@pytest.fixture(scope="module")
def vqa_conversation(item_ref: ItemRef) -> Conversation:
    conversation = Conversation(id="conversation", kind="test_vqa", item_ref=item_ref)
    conversation.table_name = "conversation"

    return conversation


@pytest.fixture(scope="module")
def vqa_sources() -> tuple[Source, Source, Source]:
    system = Source(id="source_system", name="system", kind="other")
    model = Source(id="source_model", name="model", kind="model")
    human = Source(id="source_human", name="human", kind="human")
    return system, model, human


@pytest.fixture(scope="module")
def vqa_messages(
    vqa_image: Image, vqa_image_url: Image, vqa_conversation: Conversation, vqa_sources: tuple[Source, Source, Source]
) -> list[Message]:
    conversation_ref = EntityRef(id=vqa_conversation.id, name=vqa_conversation.table_name)
    image_ref = ViewRef(id="image", name=vqa_image.table_name)
    image_url_ref = ViewRef(id="image", name=vqa_image_url.table_name)

    system_source, model_source, human_source = vqa_sources
    system_source_ref = SourceRef(id=system_source.id)
    model_source_ref = SourceRef(id=model_source.id)
    human_source_ref = SourceRef(id=human_source.id)

    class MessageImage(Message):
        @property
        def view(self) -> Image:
            return vqa_image

    class MessageImageURL(Message):
        @property
        def view(self) -> Image:
            return vqa_image_url

    messages = [
        Message(
            id="message_0",
            number=0,
            content="Vous êtes une IA serviable",
            entity_ref=conversation_ref,
            item_ref=vqa_conversation.item_ref,
            source_ref=system_source_ref,
            type="SYSTEM",
            user=system_source.name,
        ),
        Message(
            id="message_1",
            number=1,
            content="Décris cette image: <image 1>",
            view_ref=image_ref,
            source_ref=human_source_ref,
            type="QUESTION",
            user=human_source.name,
        ),
        Message(
            id="message_2",
            number=1,
            content="C'est une image d'un salon.",
            view_ref=image_ref,
            entity_ref=conversation_ref,
            source_ref=model_source_ref,
            type="ANSWER",
            user=model_source.name,
        ),
        Message(
            id="message_3",
            number=2,
            content="Décris maintenant cette image: <image>",
            view_ref=image_url_ref,
            source_ref=human_source_ref,
            type="QUESTION",
            user=human_source.name,
        ),
        Message(
            id="message_4",
            number=2,
            content="Cette image est une tête d'ours.",
            view_ref=image_url_ref,
            source_ref=model_source_ref,
            type="ANSWER",
            user=model_source.name,
        ),
    ]

    return messages


@pytest.fixture(scope="module")
def mock_conversation():
    mock_conversation = MagicMock()
    mock_conversation.item_ref.id = "item_123"
    return mock_conversation


@pytest.fixture(scope="module")
def mock_dataset():
    mock_dataset = MagicMock()
    mock_dataset.schema.groups = {
        SchemaGroup.VIEW: ["image"],
        SchemaGroup.ENTITY: ["objects"],
    }
    mock_dataset.schema.schemas = {"bboxes": BBox}
    mock_image = MagicMock()
    mock_image.url = "http://www.fake_url.com/coco_dataset/image/val/000000000139.png"
    mock_entity = MagicMock()
    mock_entity.id = "entity_456"
    mock_entity.name = "car"
    mock_bbox = MagicMock()
    mock_bbox.coords = "[10, 20, 30, 40]"
    mock_dataset.get_data.side_effect = lambda table, item_ids, where=None: {
        "image": [mock_image] if item_ids == ["item_123"] else [],
        "objects": [mock_entity] if item_ids == ["item_123"] else [],
        "bboxes": [mock_bbox] if item_ids == ["item_123"] and where else [],
    }.get(table, [])
    return mock_dataset


@pytest.mark.parametrize(
    "num_messages,expected_output",
    [
        (
            1,
            [
                {
                    "role": "system",
                    "content": [
                        {
                            "image_url": {
                                "url": "vqa_image_url",
                            },
                            "type": "image_url",
                        },
                        {
                            "text": "a normalized bounding box [10, 20, 30, 40] with the name 'car'",
                            "type": "text",
                        },
                        {"type": "text", "text": "Vous êtes une IA serviable"},
                    ],
                }
            ],
        ),
        (
            2,
            [
                {
                    "role": "system",
                    "content": [
                        {"image_url": {"url": "vqa_image_url"}, "type": "image_url"},
                        {
                            "text": "a normalized bounding box [10, 20, 30, 40] with the name 'car'",
                            "type": "text",
                        },
                        {"type": "text", "text": "Vous êtes une IA serviable"},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": "vqa_image_url"},
                        {
                            "text": "a normalized bounding box [10, 20, 30, 40] with the name 'car'",
                            "type": "text",
                        },
                        {"type": "text", "text": "Décris cette image: <image 1>"},
                    ],
                },
            ],
        ),
        (
            3,
            [
                {
                    "role": "system",
                    "content": [
                        {"image_url": {"url": "vqa_image_url"}, "type": "image_url"},
                        {
                            "text": "a normalized bounding box [10, 20, 30, 40] with the name 'car'",
                            "type": "text",
                        },
                        {"type": "text", "text": "Vous êtes une IA serviable"},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"image_url": {"url": "vqa_image_url"}, "type": "image_url"},
                        {
                            "text": "a normalized bounding box [10, 20, 30, 40] with the name 'car'",
                            "type": "text",
                        },
                        {"type": "text", "text": "Décris cette image: <image 1>"},
                    ],
                },
                {
                    "role": "assistant",
                    "content": [
                        {"image_url": {"url": "vqa_image_url"}, "type": "image_url"},
                        {
                            "text": "a normalized bounding box [10, 20, 30, 40] with the name 'car'",
                            "type": "text",
                        },
                        {"type": "text", "text": "C'est une image d'un salon."},
                    ],
                },
            ],
        ),
        (
            4,
            [
                {
                    "role": "system",
                    "content": [
                        {"image_url": {"url": "vqa_image_url"}, "type": "image_url"},
                        {
                            "text": "a normalized bounding box [10, 20, 30, 40] with the name 'car'",
                            "type": "text",
                        },
                        {"type": "text", "text": "Vous êtes une IA serviable"},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": "vqa_image_url"},
                        {
                            "text": "a normalized bounding box [10, 20, 30, 40] with the name 'car'",
                            "type": "text",
                        },
                        {"type": "text", "text": "Décris cette image: <image 1>"},
                    ],
                },
                {
                    "role": "assistant",
                    "content": [
                        {"type": "image_url", "image_url": "vqa_image_url"},
                        {
                            "text": "a normalized bounding box [10, 20, 30, 40] with the name 'car'",
                            "type": "text",
                        },
                        {"type": "text", "text": "C'est une image d'un salon."},
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": "vqa_image_url"},
                        {
                            "text": "a normalized bounding box [10, 20, 30, 40] with the name 'car'",
                            "type": "text",
                        },
                        {"type": "text", "text": "Décris maintenant cette image: <image>"},
                    ],
                },
            ],
        ),
    ],
)
def test_messages_to_prompt(
    num_messages: int,
    mock_dataset: MagicMock,
    mock_conversation: MagicMock,
    expected_output: list[dict[str, Any]],
    vqa_messages: list[Message],
    vqa_image: Image,
    vqa_image_url: Image,
):
    media_dir = ASSETS_PATH

    prompt = messages_to_prompt(mock_dataset, mock_conversation, vqa_messages[:num_messages], media_dir=media_dir)
    for i, (p, e) in enumerate(zip(prompt, expected_output, strict=True)):
        for c in e["content"]:
            if c.get("type") == "image_url":
                c["image_url"] = {"url": vqa_image_url.url}
        assert p == e


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "num_messages,response,expected_output",
    [
        (
            1,
            TextImageConditionalGenerationResult(
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={
                    "test": 1,
                },
                data=TextImageConditionalGenerationOutput(
                    generated_text="test",
                    generation_config={"generate": "yes"},
                    usage=UsageInfo(prompt_tokens=10, completion_tokens=10, total_tokens=20),
                ),
            ),
            Message(
                type="QUESTION",
                number=1,
                content="test",
                user="model",
                source_ref=SourceRef(id="source_model"),
                entity_ref=EntityRef(id="conversation", name="conversation"),
                inference_metadata=jsonable_encoder(
                    {
                        "generation_config": {"generate": "yes"},
                        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                        "timestamp": datetime(year=2025, month=2, day=19).isoformat(),
                        "processing_time": 1.0,
                    }
                ),
                timestamp=datetime(year=2025, month=2, day=19),
            ),
        ),
        (
            2,
            TextImageConditionalGenerationResult(
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={
                    "test": 1,
                },
                data=TextImageConditionalGenerationOutput(
                    generated_text="test",
                    generation_config={"generate": "yes"},
                    usage=UsageInfo(prompt_tokens=10, completion_tokens=10, total_tokens=20),
                ),
            ),
            Message(
                type="ANSWER",
                number=1,
                content="test",
                user="model",
                source_ref=SourceRef(id="source_model"),
                entity_ref=EntityRef(id="conversation", name="conversation"),
                inference_metadata=jsonable_encoder(
                    {
                        "generation_config": {"generate": "yes"},
                        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                        "timestamp": datetime(year=2025, month=2, day=19).isoformat(),
                        "processing_time": 1.0,
                    }
                ),
                timestamp=datetime(year=2025, month=2, day=19),
            ),
        ),
        (
            3,
            TextImageConditionalGenerationResult(
                timestamp=datetime(year=2025, month=2, day=19),
                processing_time=1.0,
                metadata={
                    "test": 1,
                },
                data=TextImageConditionalGenerationOutput(
                    generated_text="test",
                    generation_config={"generate": "yes"},
                    usage=UsageInfo(prompt_tokens=10, completion_tokens=10, total_tokens=20),
                ),
            ),
            Message(
                type="QUESTION",
                number=2,
                content="test",
                user="model",
                source_ref=SourceRef(id="source_model"),
                entity_ref=EntityRef(id="conversation", name="conversation"),
                inference_metadata=jsonable_encoder(
                    {
                        "generation_config": {"generate": "yes"},
                        "usage": {"prompt_tokens": 10, "completion_tokens": 10, "total_tokens": 20},
                        "timestamp": datetime(year=2025, month=2, day=19).isoformat(),
                        "processing_time": 1.0,
                    }
                ),
                timestamp=datetime(year=2025, month=2, day=19),
            ),
        ),
    ],
)
async def test_text_image_conditional_generation(
    mock_dataset: MagicMock,
    num_messages: int,
    response: TextImageConditionalGenerationResult,
    expected_output: Message,
    vqa_conversation: Conversation,
    vqa_messages: list[Message],
    simple_inference_provider: InferenceProvider,
    vqa_sources: tuple[Source, Source, Source],
):
    simple_inference_provider.text_image_conditional_generation.return_value = response

    message = await text_image_conditional_generation(
        provider=simple_inference_provider,
        source=vqa_sources[1],
        dataset=mock_dataset,
        media_dir=ASSETS_PATH,
        messages=vqa_messages[:num_messages],
        conversation=vqa_conversation,
    )

    expected_output.item_ref = vqa_messages[:num_messages][-1].item_ref
    expected_output.view_ref = vqa_messages[:num_messages][-1].view_ref

    exclude_keys = ["id", "created_at", "updated_at"]
    assert message.model_dump(exclude=exclude_keys) == expected_output.model_dump(exclude=exclude_keys)
